from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Strict):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class ProductInput(Strict):
    sku: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=80)
    price: int = Field(ge=0, le=1000000000, strict=True)
    active: bool = True


class Line(Strict):
    product_id: str = Field(min_length=1, max_length=36)
    quantity: int = Field(ge=1, le=100000, strict=True)
    unit_price: int | None = Field(default=None, ge=0, le=1000000000, strict=True)


class TransactionInput(Strict):
    kind: Literal["sale", "purchase", "refund", "adjustment"]
    lines: list[Line] = Field(min_length=1, max_length=100)
    reference_id: str | None = None
    partner_id: str | None = None
    note: str = Field(default="", max_length=1000)
    adjustment_direction: Literal["in", "out"] = "in"


class TransferInput(Strict):
    destination: Literal["DONG", "TAY", "NAM", "BAC"]
    lines: list[Line] = Field(min_length=1, max_length=100)


class PartnerInput(Strict):
    kind: Literal["customer", "supplier"]
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(default="", max_length=30)


class UserInput(Strict):
    username: str = Field(pattern=r"^[a-zA-Z0-9_.-]{3,80}$")
    name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=10, max_length=200)
    role: Literal["admin", "manager", "cashier"]
    branch_id: Literal["DONG", "TAY", "NAM", "BAC"] | None = None


class Toggle(Strict):
    enabled: bool


class DocumentReview(Strict):
    text: str = Field(max_length=200000)


class FeedbackInput(Strict):
    product_id: str
    branch_id: Literal["DONG", "TAY", "NAM", "BAC"]
    text: str = Field(min_length=1, max_length=10000)
    rating: int = Field(ge=1, le=5, strict=True)
