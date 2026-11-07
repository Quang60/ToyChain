import hashlib
import json
from datetime import datetime
from sqlalchemy import select, update, func
from fastapi import HTTPException
from .config import BRANCHES
from .db import uid, utcnow
from .models import Product, Stock, Transaction, Movement, Transfer, Outbox, Partner


def dump(row):
    return {c.name: (v.isoformat() if isinstance(v := getattr(row, c.name), datetime) else v) for c in row.__table__.columns}


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def emit(db, source, kind, data, target="CENTRAL"):
    event_id = uid()
    payload = {"id": event_id, "source": source, "type": kind, "version": 1, "created_at": utcnow().isoformat(), "data": data}
    db.add(Outbox(id=event_id, target=target, payload=payload))
    return payload


def reject(message, status=400):
    raise HTTPException(status, message)


def request_key(key):
    if not key or len(key) > 80:
        reject("Cần Idempotency-Key dài 1–80 ký tự")


def repeat(existing, data_hash):
    if existing:
        if existing.request_hash != data_hash:
            reject("Mã yêu cầu đã được dùng với nội dung khác", 409)
        return existing


def lock_products(db, branch, lines):
    ids = [line.product_id for line in lines]
    if len(ids) != len(set(ids)):
        reject("Mỗi sản phẩm chỉ được xuất hiện một lần")
    stocks = {}
    for pid in sorted(ids):
        product = db.get(Product, pid)
        if not product:
            reject("Sản phẩm không tồn tại", 404)
        stock = db.scalar(select(Stock).where(Stock.branch_id == branch, Stock.product_id == pid).with_for_update())
        if stock is None:
            reject("Sản phẩm chưa được đồng bộ tới kho", 409)
        stocks[pid] = (product, stock)
    return stocks


def move(db, stock, delta, ref, kind):
    if stock.quantity + delta < 0:
        reject("Không đủ tồn kho", 409)
    stock.quantity += delta
    movement = Movement(id=uid(), branch_id=stock.branch_id, product_id=stock.product_id, delta=delta, reference_id=ref, kind=kind, created_at=utcnow())
    db.add(movement)
    return dump(movement)


def transact(db, node, actor, command, key):
    request_key(key)
    data_hash = fingerprint(command.model_dump())
    prior = repeat(db.scalar(select(Transaction).where(Transaction.branch_id == node, Transaction.request_id == key)), data_hash)
    if prior:
        return prior
    if actor.role == "cashier" and command.kind != "sale":
        reject("Chỉ quản lý được nhập, trả hoặc điều chỉnh hàng", 403)
    if command.kind == "adjustment" and not command.note.strip():
        reject("Điều chỉnh kho phải có lý do")
    if command.partner_id:
        partner = db.get(Partner, command.partner_id)
        expected = "supplier" if command.kind == "purchase" else "customer"
        if not partner or partner.branch_id != node or partner.kind != expected:
            reject("Đối tác không phù hợp với giao dịch")
    original = None
    returned = {}
    if command.kind == "refund":
        original = db.scalar(select(Transaction).where(Transaction.id == command.reference_id).with_for_update())
        if not original or original.branch_id != node or original.kind != "sale":
            reject("Cần đơn bán gốc của chi nhánh", 400)
        for old in db.scalars(select(Transaction).where(Transaction.kind == "refund", Transaction.reference_id == original.id)):
            for line in old.lines:
                returned[line["product_id"]] = returned.get(line["product_id"], 0) + line["quantity"]
    stocks = lock_products(db, node, command.lines)
    tx_id = uid()
    rows, movements, total = [], [], 0
    for line in command.lines:
        product, stock = stocks[line.product_id]
        if not product.active and command.kind == "sale":
            reject("Sản phẩm đã ngừng bán")
        price = product.price
        if command.kind == "purchase":
            if line.unit_price is None:
                reject("Cần giá nhập cho mỗi sản phẩm")
            price = line.unit_price
        elif command.kind == "refund":
            sold = next((v for v in original.lines if v["product_id"] == product.id), None)
            if not sold or returned.get(product.id, 0) + line.quantity > sold["quantity"]:
                reject("Số lượng trả vượt số lượng đã mua", 409)
            price = sold["unit_price"]
        elif command.kind == "adjustment":
            price = 0
        direction = -1 if command.kind == "sale" or (command.kind == "adjustment" and command.adjustment_direction == "out") else 1
        movements.append(move(db, stock, direction * line.quantity, tx_id, command.kind))
        rows.append({"product_id": product.id, "sku": product.sku, "name": product.name, "quantity": line.quantity, "unit_price": price})
        total += line.quantity * price
    tx = Transaction(id=tx_id, branch_id=node, kind=command.kind, lines=rows, total=total, reference_id=command.reference_id if original else None, partner_id=command.partner_id, note=command.note, actor=actor.username, created_at=utcnow(), request_id=key, request_hash=data_hash)
    db.add(tx)
    db.flush()
    emit(db, node, "transaction.created", {"transaction": dump(tx), "movements": movements})
    return tx


def dispatch(db, node, actor, command, key):
    request_key(key)
    data_hash = fingerprint(command.model_dump())
    prior = repeat(db.scalar(select(Transfer).where(Transfer.source == node, Transfer.request_id == key)), data_hash)
    if prior:
        return prior
    if command.destination == node:
        reject("Chi nhánh nhận phải khác chi nhánh xuất")
    stocks = lock_products(db, node, command.lines)
    transfer_id, rows, movements = uid(), [], []
    for line in command.lines:
        product, stock = stocks[line.product_id]
        movements.append(move(db, stock, -line.quantity, transfer_id, "transfer.out"))
        rows.append({"product_id": product.id, "sku": product.sku, "name": product.name, "quantity": line.quantity})
    transfer = Transfer(id=transfer_id, source=node, destination=command.destination, lines=rows, status="in_transit", actor=actor.username, created_at=utcnow(), request_id=key, request_hash=data_hash)
    db.add(transfer)
    db.flush()
    emit(db, node, "transfer.dispatched", {"transfer": dump(transfer), "movements": movements})
    return transfer


def receive(db, node, transfer_id, actor):
    transfer = db.scalar(select(Transfer).where(Transfer.id == transfer_id).with_for_update())
    if not transfer or transfer.destination != node:
        reject("Không tìm thấy phiếu điều chuyển tới chi nhánh", 404)
    if transfer.status == "received":
        return transfer
    from .schemas import Line
    lines = [Line(product_id=v["product_id"], quantity=v["quantity"]) for v in transfer.lines]
    stocks = lock_products(db, node, lines)
    movements = [move(db, stocks[v.product_id][1], v.quantity, transfer.id, "transfer.in") for v in lines]
    transfer.status, transfer.received_at = "received", utcnow()
    transfer.received_by = actor.username
    db.flush()
    emit(db, node, "transfer.received", {"transfer": dump(transfer), "movements": movements})
    return transfer


def snapshot(db, branch):
    stocks = {s.product_id: s.quantity for s in db.scalars(select(Stock).where(Stock.branch_id == branch))}
    count = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.branch_id == branch))
    rows = db.scalars(select(Transaction).where(Transaction.branch_id == branch, Transaction.kind.in_(["sale", "refund"])))
    revenue = sum(t.total * (-1 if t.kind == "refund" else 1) for t in rows)
    return {"stock": stocks, "transaction_count": count, "net_revenue": revenue}
