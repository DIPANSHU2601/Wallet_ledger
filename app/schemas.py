from pydantic import BaseModel, Field
from decimal import Decimal
import uuid

class WalletCreate(BaseModel):
    user_id: str
    initial_balance: Decimal = Field(ge=0, default=0.00)

class TransactionRequest(BaseModel):
    wallet_id: uuid.UUID
    amount: Decimal = Field(gt=0, description="Amount must be greater than zero")
