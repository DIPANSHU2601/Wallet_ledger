import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
import enum

class TransactionType(enum.Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"
    TRANSFER = "TRANSFER"

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, unique=True, nullable=False)
    balance = Column(Numeric(precision=12, scale=2), default=0.00, nullable=False)

class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"

    idempotency_key = Column(String, primary_key=True, index=True)
    response_code = Column(String, nullable=False)
    response_body = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    amount = Column(Numeric(precision=12, scale=2), nullable=False)
    type = Column(SQLEnum(TransactionType), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
