from uuid import uuid5, NAMESPACE_URL
from sqlalchemy import select
from .config import BRANCHES
from .models import User, Product, Stock, Control, Transaction
from .security import hash_password
from .schemas import TransactionInput, Line
from .domain import transact

CATALOG = [
    ("LEGO-001", "LEGO Classic · Hộp sáng tạo", "Lắp ráp", 599000),
    ("LEGO-002", "LEGO City · Xe cứu hỏa", "Lắp ráp", 899000),
    ("WOOD-001", "Bộ xếp hình gỗ cầu vồng", "Giáo dục", 249000),
    ("STEM-001", "Bộ thí nghiệm khoa học", "Giáo dục", 459000),
    ("CAR-001", "Xe mô hình thể thao 1:32", "Mô hình", 189000),
    ("CAR-002", "Xe điều khiển địa hình", "Điều khiển", 749000),
    ("DOLL-001", "Búp bê và tủ quần áo", "Búp bê", 329000),
    ("DOLL-002", "Ngôi nhà búp bê gỗ", "Búp bê", 1250000),
    ("PLUSH-001", "Gấu bông mây mềm 35cm", "Thú bông", 219000),
    ("PLUSH-002", "Thỏ bông tai dài", "Thú bông", 179000),
    ("BOARD-001", "Cờ tỷ phú gia đình", "Board game", 289000),
    ("BOARD-002", "Bộ cờ vua gỗ", "Board game", 349000),
    ("ART-001", "Hộp màu sáng tạo 48 màu", "Mỹ thuật", 159000),
    ("ART-002", "Đất nặn sắc màu 12 hộp", "Mỹ thuật", 129000),
    ("OUT-001", "Bóng rổ trẻ em", "Vận động", 199000),
    ("OUT-002", "Xe trượt scooter", "Vận động", 890000),
]


def stable(value):
    return str(uuid5(NAMESPACE_URL, "toychain/" + value))


def seed(db, settings):
    if not db.get(Control, 1):
        db.add(Control(id=1, enabled=True, last_error=""))
    people = [("admin", "Quản trị toàn chuỗi", "admin", None)]
    for code, label in BRANCHES.items():
        people.extend([(f"ql.{code.lower()}", "Quản lý " + label, "manager", code), (f"nv.{code.lower()}", "Thu ngân " + label, "cashier", code)])
    for username, name, role, branch in people:
        if settings.node != "CENTRAL" and branch not in (settings.node, None):
            continue
        if not db.scalar(select(User).where(User.username == username)):
            db.add(User(id=stable(username), username=username, name=name, role=role, branch_id=branch, password_hash=hash_password(settings.demo_password)))
    for sku, name, category, price in CATALOG:
        pid = stable(sku)
        if not db.get(Product, pid):
            db.add(Product(id=pid, sku=sku, name=name, category=category, price=price))
            db.flush()
        for branch in BRANCHES if settings.node == "CENTRAL" else [settings.node]:
            if not db.get(Stock, (branch, pid)):
                db.add(Stock(branch_id=branch, product_id=pid, quantity=0))
    db.flush()
    if settings.node != "CENTRAL":
        key = "initial-stock-v1"
        if not db.scalar(select(Transaction).where(Transaction.request_id == key)):
            actor = db.scalar(select(User).where(User.username == "admin"))
            lines = [Line(product_id=stable(sku), quantity=20 + list(BRANCHES).index(settings.node) * 5 + i, unit_price=price * 6 // 10) for i, (sku, _, _, price) in enumerate(CATALOG)]
            transact(db, settings.node, actor, TransactionInput(kind="purchase", lines=lines, note="Nhập kho dữ liệu minh họa ban đầu"), key)
