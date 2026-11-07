from uuid import uuid4
from sqlalchemy import select, func
from app.models import Outbox, Stock, Transaction
from conftest import auth


def first(client, headers):
    return client.get("/api/products", headers=headers).json()[0]


def qty(client, headers, product):
    return next(s["quantity"] for s in client.get("/api/stock", headers=headers).json() if s["product_id"] == product)


def create(client, headers, product, quantity=1, key=None, **extra):
    return client.post("/api/transactions", headers={**headers, "Idempotency-Key": key or str(uuid4())}, json={"kind": "sale", "lines": [{"product_id": product, "quantity": quantity}], **extra})


def test_requires_auth_and_branch_scope(branch, central):
    client, _, headers = branch
    assert client.get("/api/stock").status_code == 401
    assert client.get("/api/stock?branch=TAY", headers=headers).status_code == 403
    c, _, _ = central
    staff = auth(c, "ql.dong")
    assert c.get("/api/stock?branch=BAC", headers=staff).status_code == 403
    assert {s["branch_id"] for s in c.get("/api/stock", headers=staff).json()} == {"DONG"}
    assert c.get("/api/users", headers=staff).status_code == 403


def test_sale_price_and_replay(branch):
    c, _, h = branch
    product = first(c, h)
    before = qty(c, h, product["id"])
    key = str(uuid4())
    body = {"kind": "sale", "lines": [{"product_id": product["id"], "quantity": 2, "unit_price": 1}]}
    a = c.post("/api/transactions", json=body, headers={**h, "Idempotency-Key": key})
    b = c.post("/api/transactions", json=body, headers={**h, "Idempotency-Key": key})
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] == b.json()["id"]
    assert a.json()["total"] == product["price"] * 2
    assert qty(c, h, product["id"]) == before - 2
    assert create(c, h, product["id"], 3, key).status_code == 409


def test_oversell_rolls_back_all_lines_and_outbox(branch):
    c, app, h = branch
    products = c.get("/api/products", headers=h).json()[:2]
    before = c.get("/api/stock", headers=h).json()
    with app.state.factory() as db:
        count = db.scalar(select(func.count()).select_from(Outbox))
    response = c.post("/api/transactions", headers={**h, "Idempotency-Key": str(uuid4())}, json={"kind": "sale", "lines": [{"product_id": products[0]["id"], "quantity": 1}, {"product_id": products[1]["id"], "quantity": 99999}]})
    assert response.status_code == 409
    assert c.get("/api/stock", headers=h).json() == before
    with app.state.factory() as db:
        assert db.scalar(select(func.count()).select_from(Outbox)) == count


def test_validation_and_duplicate_lines(branch):
    c, _, h = branch
    pid = first(c, h)["id"]
    for bad in [0, -1, 1.5, "2"]:
        assert create(c, h, pid, bad).status_code == 422
    response = c.post("/api/transactions", headers={**h,"Idempotency-Key":"double"}, json={"kind":"sale","lines":[{"product_id":pid,"quantity":1},{"product_id":pid,"quantity":1}]})
    assert response.status_code == 400
    assert c.post("/api/transactions", headers=h, json={"kind":"sale","lines":[{"product_id":pid,"quantity":1}]}).status_code == 400


def test_refund_cannot_exceed_original(branch):
    c, _, h = branch
    pid = first(c, h)["id"]
    before = qty(c, h, pid)
    sale = create(c, h, pid, 2).json()
    assert create(c, h, pid, 1, kind="refund", reference_id=sale["id"]).status_code == 201
    assert create(c, h, pid, 2, kind="refund", reference_id=sale["id"]).status_code == 409
    assert qty(c, h, pid) == before - 1


def test_cashier_only_sells(branch):
    c, _, _ = branch
    h = auth(c, "nv.dong")
    pid = first(c, h)["id"]
    assert create(c,h,pid).status_code == 201
    for kind in ["purchase","adjustment","refund"]:
        assert create(c,h,pid,kind=kind).status_code == 403
    assert c.post("/api/sync/control",json={"enabled":False},headers=h).status_code == 403
    assert c.post("/api/transfers",json={"destination":"TAY","lines":[{"product_id":pid,"quantity":1}]},headers={**h,"Idempotency-Key":"x"}).status_code == 403


def test_sale_while_sync_paused(branch):
    c, _, h = branch
    assert c.post("/api/sync/control",json={"enabled":False},headers=h).status_code == 200
    before = c.get("/api/sync",headers=h).json()["pending"]
    assert create(c,h,first(c,h)["id"]).status_code == 201
    state = c.get("/api/sync",headers=h).json()
    assert state["pending"] == before + 1 and not state["control"]["enabled"]


def test_central_rejects_local_transaction(central):
    c, _, h = central
    assert create(c,h,first(c,h)["id"]).status_code == 400


def test_adjustment_requires_reason(branch):
    c, _, h = branch
    pid = first(c,h)["id"]
    assert create(c,h,pid,kind="adjustment").status_code == 400
    assert create(c,h,pid,kind="adjustment",note="Kiểm kê",adjustment_direction="out").status_code == 201


def test_supplier_and_customer_validation(branch):
    c, _, h = branch
    supplier = c.post('/api/partners',headers=h,json={"kind":"supplier","name":"Đồ chơi Việt","phone":"0900000000"}).json()
    pid=first(c,h)["id"]
    assert create(c,h,pid,partner_id=supplier["id"]).status_code == 400
    response=create(c,h,pid,kind="purchase",partner_id=supplier["id"],lines=[{"product_id":pid,"quantity":2,"unit_price":100000}])
    assert response.status_code == 201
