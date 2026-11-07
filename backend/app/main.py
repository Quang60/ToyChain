import hmac
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote
from datetime import datetime
import jwt
from fastapi import FastAPI, Depends, Header, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, or_, text
from sqlalchemy.exc import IntegrityError
from pymongo.errors import PyMongoError
from botocore.exceptions import BotoCoreError, ClientError
from .config import Settings, NODES, BRANCHES
from .db import Base, make_db, uid, utcnow
from .models import User, Product, Stock, Transaction, Transfer, Partner, Outbox, Inbox, DeadLetter, Control, Reconciliation
from .security import check_password, token_for, hash_password
from . import schemas
from .domain import dump, emit, transact, dispatch, receive, snapshot, reject
from .seed import seed
from .documents import DocumentStore


def public_user(user):
    return {k: v for k, v in dump(user).items() if k != "password_hash"}


def create_app(settings=None):
    settings = settings or Settings()
    engine, factory = make_db(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        settings.validate()
        if settings.test_mode:
            Base.metadata.create_all(engine)
            with factory.begin() as db:
                seed(db, settings)
        yield
        if getattr(app.state, "documents", None):
            app.state.documents.client.close()
        engine.dispose()

    app = FastAPI(title="ToyChain · Hệ thống quản lý chuỗi cửa hàng đồ chơi", version="1.0.0", lifespan=lifespan)
    app.state.factory, app.state.settings = factory, settings
    app.state.documents = None

    @app.exception_handler(IntegrityError)
    async def integrity_error(_, exc):
        return JSONResponse(status_code=409, content={"detail": "Dữ liệu trùng hoặc yêu cầu đồng thời. Với giao dịch, gửi lại cùng mã yêu cầu để kiểm tra kết quả."})

    async def storage_error(_, exc):
        return JSONResponse(status_code=503, content={"detail": "Kho tài liệu chưa sẵn sàng. Kiểm tra MongoDB/S3 và thử lại."})
    for error in (PyMongoError, BotoCoreError, ClientError):
        app.add_exception_handler(error, storage_error)

    def db_session():
        with factory.begin() as db:
            yield db

    def current_user(authorization: str = Header(default=""), db=Depends(db_session)):
        try:
            if not authorization.startswith("Bearer "):
                raise ValueError()
            claims = jwt.decode(authorization[7:], settings.jwt_secret, algorithms=["HS256"], issuer="toychain")
            user = db.get(User, claims["sub"])
            if not user or not user.active:
                raise ValueError()
        except (jwt.PyJWTError, ValueError, KeyError):
            raise HTTPException(401, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
        if settings.node != "CENTRAL" and user.role != "admin" and user.branch_id != settings.node:
            reject("Bạn không có quyền tại chi nhánh này", 403)
        return user

    def manager(user=Depends(current_user)):
        if user.role == "cashier" or settings.node == "CENTRAL" and user.role != "admin":
            reject("Chức năng dành cho quản lý của nút này", 403)
        return user

    def central_admin(user=Depends(current_user)):
        if settings.node != "CENTRAL" or user.role != "admin":
            reject("Thao tác tại trung tâm bằng tài khoản quản trị", 403)
        return user

    def branch_required():
        if settings.node == "CENTRAL":
            reject("Mở nút chi nhánh để thực hiện giao dịch", 400)

    def scope(user, branch=None):
        if branch and branch not in BRANCHES:
            reject("Chi nhánh không hợp lệ")
        allowed = settings.node if settings.node != "CENTRAL" else user.branch_id if user.role != "admin" else None
        if allowed and branch and allowed != branch:
            reject("Không có quyền xem chi nhánh này", 403)
        return allowed or branch

    def docs_store():
        if settings.node != "CENTRAL":
            reject("Kho tài liệu đặt tại nút trung tâm", 400)
        if app.state.documents is None:
            app.state.documents = DocumentStore(settings)
        return app.state.documents

    @app.get("/api/health")
    def health(db=Depends(db_session)):
        db.execute(text("SELECT 1"))
        return {"status": "ok", "node": settings.node}

    @app.get("/api/info")
    def info():
        return {"node": settings.node, "name": NODES[settings.node], "branches": BRANCHES, "ocr_enabled": False}

    @app.post("/api/auth/login")
    def login(data: schemas.Login, db=Depends(db_session)):
        user = db.scalar(select(User).where(User.username == data.username))
        if not user or not user.active or not check_password(data.password, user.password_hash):
            reject("Tên đăng nhập hoặc mật khẩu không đúng", 401)
        if settings.node != "CENTRAL" and user.role != "admin" and user.branch_id != settings.node:
            reject("Tài khoản thuộc chi nhánh khác", 403)
        return {"access_token": token_for(user, settings), "user": public_user(user)}

    @app.get("/api/auth/me")
    def me(user=Depends(current_user)):
        return public_user(user)

    @app.get("/api/products")
    def products(q: str = Query(default="", max_length=200), user=Depends(current_user), db=Depends(db_session)):
        stmt = select(Product).order_by(Product.sku)
        if q:
            stmt = stmt.where(or_(Product.name.ilike(f"%{q}%"), Product.sku.ilike(f"%{q}%")))
        return [dump(p) for p in db.scalars(stmt.limit(500))]

    def save_product(db, data, existing=None):
        if existing:
            for k, v in data.model_dump().items():
                setattr(existing, k, v)
            existing.version += 1
            product = existing
        else:
            product = Product(id=uid(), **data.model_dump(), version=1)
            db.add(product)
            db.flush()
            for branch in BRANCHES:
                db.add(Stock(branch_id=branch, product_id=product.id, quantity=0))
        db.flush()
        for branch in BRANCHES:
            emit(db, "CENTRAL", "product.updated", dump(product), branch)
        return dump(product)

    @app.post("/api/products", status_code=201)
    def add_product(data: schemas.ProductInput, user=Depends(central_admin), db=Depends(db_session)):
        return save_product(db, data)

    @app.put("/api/products/{product_id}")
    def edit_product(product_id: str, data: schemas.ProductInput, user=Depends(central_admin), db=Depends(db_session)):
        product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
        if not product:
            reject("Không tìm thấy sản phẩm", 404)
        return save_product(db, data, product)

    @app.get("/api/stock")
    def stock(branch: str | None = None, user=Depends(current_user), db=Depends(db_session)):
        selected = scope(user, branch)
        stmt = select(Stock, Product).join(Product, Product.id == Stock.product_id).order_by(Stock.branch_id, Product.sku)
        if selected:
            stmt = stmt.where(Stock.branch_id == selected)
        return [{**dump(s), "sku": p.sku, "name": p.name, "category": p.category, "price": p.price} for s, p in db.execute(stmt)]

    @app.get("/api/transactions")
    def transactions(branch: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), user=Depends(current_user), db=Depends(db_session)):
        selected = scope(user, branch)
        stmt = select(Transaction).order_by(Transaction.created_at.desc())
        if selected:
            stmt = stmt.where(Transaction.branch_id == selected)
        return [dump(t) for t in db.scalars(stmt.offset(offset).limit(limit))]

    @app.post("/api/transactions", status_code=201)
    def create_transaction(data: schemas.TransactionInput, idempotency_key: str = Header(default=""), user=Depends(current_user), db=Depends(db_session)):
        branch_required()
        return dump(transact(db, settings.node, user, data, idempotency_key))

    @app.get("/api/transfers")
    def transfers(user=Depends(current_user), db=Depends(db_session)):
        selected = scope(user)
        stmt = select(Transfer).order_by(Transfer.created_at.desc())
        if selected:
            stmt = stmt.where(or_(Transfer.source == selected, Transfer.destination == selected))
        return [dump(t) for t in db.scalars(stmt.limit(200))]

    @app.post("/api/transfers", status_code=201)
    def create_transfer(data: schemas.TransferInput, idempotency_key: str = Header(default=""), user=Depends(manager), db=Depends(db_session)):
        branch_required()
        return dump(dispatch(db, settings.node, user, data, idempotency_key))

    @app.post("/api/transfers/{transfer_id}/receive")
    def receive_transfer(transfer_id: str, user=Depends(manager), db=Depends(db_session)):
        branch_required()
        return dump(receive(db, settings.node, transfer_id, user))

    @app.get("/api/partners")
    def partners(user=Depends(current_user), db=Depends(db_session)):
        stmt = select(Partner).order_by(Partner.name)
        selected = scope(user)
        if selected:
            stmt = stmt.where(Partner.branch_id == selected)
        return [dump(p) for p in db.scalars(stmt.limit(500))]

    @app.post("/api/partners", status_code=201)
    def add_partner(data: schemas.PartnerInput, user=Depends(current_user), db=Depends(db_session)):
        branch_required()
        if data.kind == "supplier" and user.role == "cashier":
            reject("Chỉ quản lý được thêm nhà cung cấp", 403)
        partner = Partner(id=uid(), branch_id=settings.node, **data.model_dump())
        db.add(partner)
        db.flush()
        emit(db, settings.node, "partner.created", dump(partner))
        return dump(partner)

    @app.get("/api/users")
    def users(user=Depends(central_admin), db=Depends(db_session)):
        return [public_user(u) for u in db.scalars(select(User).order_by(User.username))]

    @app.post("/api/users", status_code=201)
    def add_user(data: schemas.UserInput, user=Depends(central_admin), db=Depends(db_session)):
        if data.role != "admin" and not data.branch_id:
            reject("Nhân viên cần chi nhánh")
        row = User(id=uid(), username=data.username, name=data.name, role=data.role, branch_id=data.branch_id if data.role != "admin" else None, password_hash=hash_password(data.password), active=True)
        db.add(row)
        db.flush()
        for branch in BRANCHES if row.role == "admin" else [row.branch_id]:
            emit(db, "CENTRAL", "user.created", dump(row), branch)
        return public_user(row)

    @app.get("/api/dashboard")
    def dashboard(branch: str | None = None, user=Depends(current_user), db=Depends(db_session)):
        selected = scope(user, branch)
        summaries = []
        for code in [selected] if selected else BRANCHES:
            snap = snapshot(db, code)
            last = db.scalar(select(func.max(Inbox.received_at)).where(Inbox.source == code))
            summaries.append({"branch_id": code, "name": BRANCHES[code], "net_revenue": snap["net_revenue"], "transaction_count": snap["transaction_count"], "stock_units": sum(snap["stock"].values()), "low_stock": sum(1 for v in snap["stock"].values() if v < 10), "last_synced_at": last.isoformat() if last else None})
        return {"branches": summaries, "product_count": db.scalar(select(func.count()).select_from(Product)), "in_transit": sum(1 for t in db.scalars(select(Transfer).where(Transfer.status == "in_transit")) if not selected or selected in (t.source, t.destination))}

    @app.get("/api/sync")
    def sync_status(user=Depends(manager), db=Depends(db_session)):
        control = db.get(Control, 1)
        return {"control": dump(control), "pending": db.scalar(select(func.count()).select_from(Outbox).where(Outbox.sent_at.is_(None))), "processed": db.scalar(select(func.count()).select_from(Inbox)), "last_received_at": db.scalar(select(func.max(Inbox.received_at))), "failed": [{"id": v.id, "reason": v.reason, "created_at": v.created_at, "retried_at": v.retried_at} for v in db.scalars(select(DeadLetter).order_by(DeadLetter.created_at.desc()).limit(50))], "reconciliations": [dump(v) for v in db.scalars(select(Reconciliation).order_by(Reconciliation.created_at.desc()).limit(20))]}

    @app.post("/api/sync/control")
    def sync_control(data: schemas.Toggle, user=Depends(manager), db=Depends(db_session)):
        control = db.get(Control, 1)
        control.enabled = data.enabled
        return {"enabled": data.enabled}

    @app.post("/api/sync/retry/{item_id}")
    def retry_event(item_id: str, user=Depends(manager), db=Depends(db_session)):
        item = db.scalar(select(DeadLetter).where(DeadLetter.id == item_id).with_for_update())
        if not item:
            reject("Không tìm thấy sự kiện lỗi", 404)
        from .etl import apply_event
        try:
            apply_event(db, settings.node, item.payload)
        except (ValueError, KeyError, TypeError) as exc:
            reject(str(exc), 409)
        item.retried_at = utcnow()
        return {"status": "processed"}

    @app.get("/api/internal/snapshot")
    def internal_snapshot(x_internal_key: str = Header(default=""), db=Depends(db_session)):
        if not hmac.compare_digest(x_internal_key, settings.internal_secret):
            reject("Không được phép", 403)
        branch_required()
        return {**snapshot(db, settings.node), "pending": db.scalar(select(func.count()).select_from(Outbox).where(Outbox.sent_at.is_(None)))}

    @app.get("/api/documents")
    def documents(q: str = Query("", max_length=200), product_id: str | None = None, user=Depends(current_user)):
        return docs_store().query(scope(user), q, product_id)

    @app.post("/api/documents", status_code=201)
    def upload_document(file: UploadFile = File(...), branch_id: str = Form(...), product_id: str = Form(...), order_id: str = Form(""), user=Depends(current_user), db=Depends(db_session)):
        scope(user, branch_id)
        if branch_id not in BRANCHES or not db.get(Product, product_id):
            reject("Chi nhánh hoặc sản phẩm không tồn tại")
        if order_id:
            order = db.get(Transaction, order_id)
            if not order or order.branch_id != branch_id or product_id not in [v["product_id"] for v in order.lines]:
                reject("Chứng từ phải liên kết giao dịch có sản phẩm này tại đúng chi nhánh")
        body = file.file.read(10 * 1024 * 1024 + 1)
        return docs_store().upload(file.filename or "file", body, branch_id, product_id, order_id or None, user.username)

    @app.get("/api/documents/{doc_id}/download")
    def download(doc_id: str, user=Depends(current_user)):
        store = docs_store()
        row = store.get(doc_id, scope(user))
        obj = store.s3.get_object(Bucket=settings.s3_bucket, Key=row["object_key"])
        def chunks():
            try:
                yield from obj["Body"].iter_chunks(chunk_size=65536)
            finally:
                obj["Body"].close()
        return StreamingResponse(chunks(), media_type=row["mime"], headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(row["filename"], safe=""), "X-Content-Type-Options": "nosniff"})

    @app.put("/api/documents/{doc_id}/review")
    def review(doc_id: str, data: schemas.DocumentReview, user=Depends(current_user)):
        if user.role == "cashier":
            reject("Chỉ quản lý được xác nhận nội dung", 403)
        store = docs_store()
        store.get(doc_id, scope(user))
        store.db.documents.update_one({"_id": doc_id}, {"$set": {"text": data.text, "status": "verified", "reviewed_by": user.username, "reviewed_at": utcnow(), "error": ""}})
        return store.public(store.get(doc_id, scope(user)))

    @app.post("/api/documents/{doc_id}/retry")
    def retry_document(doc_id: str, user=Depends(current_user)):
        store = docs_store()
        row = store.get(doc_id, scope(user))
        if row["status"] != "error":
            reject("Chỉ xử lý lại tài liệu đang lỗi")
        store.db.documents.update_one({"_id": doc_id, "status": "error"}, {"$set": {"status": "pending", "error": ""}})
        return {"status": "pending"}

    @app.get("/api/search")
    def unified_search(q: str = Query(min_length=1, max_length=200), user=Depends(current_user), db=Depends(db_session)):
        import re
        store = docs_store()
        docs = store.query(scope(user), q)
        feedback_filter = {"text": {"$regex": re.escape(q), "$options": "i"}}
        if scope(user):
            feedback_filter["branch_id"] = scope(user)
        feedback_rows = [store.public(row) for row in store.db.feedback.find(feedback_filter).limit(100)]
        linked = [v["product_id"] for v in docs + feedback_rows]
        found = db.scalars(select(Product).where(or_(Product.name.ilike(f"%{q}%"), Product.sku.ilike(f"%{q}%"), Product.id.in_(linked))).limit(100)).all()
        result = []
        for p in found:
            stock_query = select(Stock).where(Stock.product_id == p.id)
            if scope(user):
                stock_query = stock_query.where(Stock.branch_id == scope(user))
            result.append({**dump(p), "stock": [dump(s) for s in db.scalars(stock_query)], "documents": [d for d in docs if d["product_id"] == p.id], "feedback": [f for f in feedback_rows if f["product_id"] == p.id]})
        return {"products": result, "documents": docs, "feedback": feedback_rows}

    @app.get("/api/feedback")
    def feedback(user=Depends(current_user)):
        store = docs_store()
        return [store.public(row) for row in store.db.feedback.find({"branch_id": scope(user)} if scope(user) else {}).sort("created_at", -1).limit(100)]

    @app.post("/api/feedback", status_code=201)
    def add_feedback(data: schemas.FeedbackInput, user=Depends(current_user), db=Depends(db_session)):
        scope(user, data.branch_id)
        if not db.get(Product, data.product_id):
            reject("Sản phẩm không tồn tại", 404)
        store = docs_store()
        row = {"_id": uid(), **data.model_dump(), "author": user.username, "created_at": utcnow()}
        store.db.feedback.insert_one(row)
        return store.public(row)

    static = Path(__file__).resolve().parents[1] / "static"
    if static.is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")
        @app.get("/", include_in_schema=False)
        def frontend():
            return FileResponse(static / "index.html")
    return app


app = create_app()
