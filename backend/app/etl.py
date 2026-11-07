from datetime import datetime
from sqlalchemy import select, update
from .config import BRANCHES
from .db import utcnow
from .models import Inbox, Product, Stock, Transaction, Movement, Transfer, User, Partner
from .domain import emit


def parse_row(data, dates):
    result = dict(data)
    for field in dates:
        if result.get(field):
            result[field] = datetime.fromisoformat(result[field])
    return result


def apply_movements(db, source, rows):
    for data in rows:
        if data["branch_id"] != source or type(data["delta"]) is not int:
            raise ValueError("Nguồn biến động kho không hợp lệ")
        if db.get(Movement, data["id"]):
            continue
        stock = db.get(Stock, (source, data["product_id"]))
        if not stock:
            raise ValueError("Chưa có danh mục sản phẩm tại trung tâm")
        db.execute(update(Stock).where(Stock.branch_id == source, Stock.product_id == data["product_id"]).values(quantity=Stock.quantity + data["delta"]))
        db.add(Movement(**parse_row(data, ["created_at"])))


def validate_event(event):
    # Validate the envelope before accessing fields or passing IDs to SQLAlchemy.
    # ValueError is permanent message failure; database outages still propagate.
    if not isinstance(event, dict):
        raise ValueError("Sự kiện phải là một JSON object")
    if type(event.get("version")) is not int or event["version"] != 1 or event.get("source") not in ["CENTRAL", *BRANCHES]:
        raise ValueError("Phiên bản hoặc nguồn sự kiện không hợp lệ")
    event_id = event.get("id")
    if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 36:
        raise ValueError("Mã sự kiện phải là chuỗi dài 1–36 ký tự")
    if not isinstance(event.get("type"), str) or not event["type"].strip():
        raise ValueError("Loại sự kiện không hợp lệ")
    if not isinstance(event.get("data"), dict):
        raise ValueError("Dữ liệu sự kiện phải là một JSON object")


def apply_event(db, node, event):
    validate_event(event)
    if db.get(Inbox, event["id"]):
        return False
    source, kind, data = event["source"], event["type"], event["data"]
    if node == "CENTRAL":
        if source not in BRANCHES:
            raise ValueError("Trung tâm chỉ nhận giao dịch từ chi nhánh")
        if kind == "transaction.created":
            tx = data["transaction"]
            if tx["branch_id"] != source:
                raise ValueError("Giao dịch sai chi nhánh nguồn")
            if not db.get(Transaction, tx["id"]):
                db.add(Transaction(**parse_row(tx, ["created_at"])))
            apply_movements(db, source, data["movements"])
        elif kind in ("transfer.dispatched", "transfer.received"):
            raw = data["transfer"]
            expected = raw["source"] if kind == "transfer.dispatched" else raw["destination"]
            if expected != source or raw["destination"] not in BRANCHES:
                raise ValueError("Điều chuyển sai chi nhánh")
            existing = db.get(Transfer, raw["id"])
            if kind == "transfer.received" and not existing:
                raise ValueError("Chưa có phiếu xuất điều chuyển")
            if not existing:
                db.add(Transfer(**parse_row(raw, ["created_at", "received_at"])))
            elif kind == "transfer.received":
                existing.status = "received"
                existing.received_at = datetime.fromisoformat(raw["received_at"])
                existing.received_by = raw["received_by"]
            apply_movements(db, source, data["movements"])
            emit(db, "CENTRAL", kind, {"transfer": raw}, raw["destination"] if kind == "transfer.dispatched" else raw["source"])
        elif kind == "partner.created":
            if data["branch_id"] != source:
                raise ValueError("Đối tác sai chi nhánh")
            if not db.get(Partner, data["id"]):
                db.add(Partner(**data))
        else:
            raise ValueError("Loại sự kiện không được hỗ trợ tại trung tâm")
    else:
        if source != "CENTRAL":
            raise ValueError("Chi nhánh chỉ nhận sự kiện từ trung tâm")
        if kind == "product.updated":
            row = db.get(Product, data["id"])
            if not row:
                row = Product(**data)
                db.add(row)
                db.flush()
                db.add(Stock(branch_id=node, product_id=row.id, quantity=0))
            elif data["version"] > row.version:
                for key, value in data.items():
                    setattr(row, key, value)
        elif kind == "user.created":
            if data["role"] != "admin" and data["branch_id"] != node:
                raise ValueError("Tài khoản sai chi nhánh")
            if not db.get(User, data["id"]):
                db.add(User(**data))
        elif kind == "transfer.dispatched":
            raw = data["transfer"]
            if raw["destination"] != node:
                raise ValueError("Sai chi nhánh nhận")
            if not db.get(Transfer, raw["id"]):
                db.add(Transfer(**parse_row(raw, ["created_at", "received_at"])))
        elif kind == "transfer.received":
            raw = data["transfer"]
            row = db.get(Transfer, raw["id"])
            if not row or row.source != node:
                raise ValueError("Không có phiếu điều chuyển nguồn")
            row.status, row.received_at = "received", datetime.fromisoformat(raw["received_at"])
            row.received_by = raw["received_by"]
        else:
            raise ValueError("Loại sự kiện không được hỗ trợ tại chi nhánh")
    db.add(Inbox(id=event["id"], source=source))
    db.flush()
    return True
