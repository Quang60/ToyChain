from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, JSON, Text, ForeignKey, UniqueConstraint, CheckConstraint
from .db import Base, uid, utcnow


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=uid)
    username = Column(String(80), unique=True, nullable=False)
    name = Column(String(160), nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(String(20), nullable=False)
    branch_id = Column(String(12), nullable=True)
    active = Column(Boolean, nullable=False, default=True)


class Product(Base):
    __tablename__ = "products"
    id = Column(String(36), primary_key=True, default=uid)
    sku = Column(String(60), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    category = Column(String(80), nullable=False)
    price = Column(BigInteger, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint("price >= 0"),)


class Stock(Base):
    __tablename__ = "stock"
    branch_id = Column(String(12), primary_key=True)
    product_id = Column(String(36), ForeignKey("products.id"), primary_key=True)
    quantity = Column(Integer, nullable=False, default=0)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String(36), primary_key=True, default=uid)
    branch_id = Column(String(12), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    lines = Column(JSON, nullable=False)
    total = Column(BigInteger, nullable=False)
    reference_id = Column(String(36), nullable=True, index=True)
    partner_id = Column(String(36), nullable=True)
    note = Column(Text, nullable=False, default="")
    actor = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    request_id = Column(String(80), nullable=False)
    request_hash = Column(String(64), nullable=False)
    __table_args__ = (UniqueConstraint("branch_id", "request_id"),)


class Movement(Base):
    __tablename__ = "movements"
    id = Column(String(36), primary_key=True, default=uid)
    branch_id = Column(String(12), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    delta = Column(Integer, nullable=False)
    reference_id = Column(String(36), nullable=False)
    kind = Column(String(30), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class Transfer(Base):
    __tablename__ = "transfers"
    id = Column(String(36), primary_key=True, default=uid)
    source = Column(String(12), nullable=False)
    destination = Column(String(12), nullable=False)
    lines = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False)
    actor = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    received_at = Column(DateTime(timezone=True))
    received_by = Column(String(80))
    request_id = Column(String(80), nullable=False)
    request_hash = Column(String(64), nullable=False)
    __table_args__ = (UniqueConstraint("source", "request_id"),)


class Partner(Base):
    __tablename__ = "partners"
    id = Column(String(36), primary_key=True, default=uid)
    branch_id = Column(String(12), nullable=False)
    kind = Column(String(20), nullable=False)
    name = Column(String(200), nullable=False)
    phone = Column(String(30), nullable=False, default="")


class Outbox(Base):
    __tablename__ = "outbox"
    id = Column(String(36), primary_key=True)
    target = Column(String(12), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    sent_at = Column(DateTime(timezone=True), index=True)


class Inbox(Base):
    __tablename__ = "inbox"
    id = Column(String(36), primary_key=True)
    source = Column(String(12), nullable=False)
    received_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class DeadLetter(Base):
    __tablename__ = "dead_letters"
    id = Column(String(36), primary_key=True, default=uid)
    payload = Column(JSON, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    retried_at = Column(DateTime(timezone=True))


class Control(Base):
    __tablename__ = "control"
    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    worker_seen_at = Column(DateTime(timezone=True))
    last_error = Column(Text, nullable=False, default="")


class Reconciliation(Base):
    __tablename__ = "reconciliations"
    id = Column(String(36), primary_key=True, default=uid)
    branch_id = Column(String(12), nullable=False)
    status = Column(String(20), nullable=False)
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
