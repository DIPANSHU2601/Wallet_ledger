from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal

from app.database import engine, Base, get_db
from app.models import Wallet, IdempotencyRecord, LedgerTransaction, TransactionType
from app.schemas import WalletCreate, TransactionRequest

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Idempotent Wallet Ledger API", lifespan=lifespan)

@app.post("/wallets", status_code=201)
async def create_wallet(payload: WalletCreate, db: AsyncSession = Depends(get_db)):
    wallet = Wallet(user_id=payload.user_id, balance=payload.initial_balance)
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)
    return {"wallet_id": str(wallet.id), "user_id": wallet.user_id, "balance": float(wallet.balance)}

@app.post("/wallet/deposit")
async def deposit(
    payload: TransactionRequest,
    response: Response,
    idempotency_key: str = Header(..., alias="X-Idempotency-Key"),
    db: AsyncSession = Depends(get_db)
):
    # 1. Check Idempotency Key first
    existing = await db.get(IdempotencyRecord, idempotency_key)
    if existing:
        response.status_code = int(existing.response_code)
        return existing.response_body

    # 2. Execute within database transaction with row-level lock
    async with db.begin():
        # SELECT ... FOR UPDATE prevents concurrent modifications on this wallet row
        result = await db.execute(
            select(Wallet).where(Wallet.id == payload.wallet_id).with_for_update()
        )
        wallet = result.scalar_one_or_none()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        wallet.balance += payload.amount
        
        tx = LedgerTransaction(
            wallet_id=wallet.id,
            amount=payload.amount,
            type=TransactionType.DEPOSIT
        )
        db.add(tx)

        resp_data = {"status": "success", "new_balance": float(wallet.balance)}

        # Save idempotency record inside the same transaction
        idemp_record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            response_code="200",
            response_body=resp_data
        )
        db.add(idemp_record)

    return resp_data

@app.post("/wallet/withdraw")
async def withdraw(
    payload: TransactionRequest,
    response: Response,
    idempotency_key: str = Header(..., alias="X-Idempotency-Key"),
    db: AsyncSession = Depends(get_db)
):
    existing = await db.get(IdempotencyRecord, idempotency_key)
    if existing:
        response.status_code = int(existing.response_code)
        return existing.response_body

    async with db.begin():
        result = await db.execute(
            select(Wallet).where(Wallet.id == payload.wallet_id).with_for_update()
        )
        wallet = result.scalar_one_or_none()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        if wallet.balance < payload.amount:
            raise HTTPException(status_code=400, detail="Insufficient funds")

        wallet.balance -= payload.amount
        
        tx = LedgerTransaction(
            wallet_id=wallet.id,
            amount=payload.amount,
            type=TransactionType.WITHDRAW
        )
        db.add(tx)

        resp_data = {"status": "success", "new_balance": float(wallet.balance)}

        idemp_record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            response_code="200",
            response_body=resp_data
        )
        db.add(idemp_record)

    return resp_data
