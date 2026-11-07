import hashlib
import io
import re
from pathlib import Path
from datetime import timedelta
import boto3
from botocore.config import Config
from pymongo import MongoClient, ReturnDocument
from pypdf import PdfReader
from fastapi import HTTPException
from .db import uid, utcnow


def detect_file(name, body):
    ext = Path(name).suffix.lower()
    if not body or len(body) > 10 * 1024 * 1024:
        raise HTTPException(400, "Tệp phải có dung lượng từ 1 byte tới 10 MB")
    valid = {".pdf": (body.startswith(b"%PDF-"), "application/pdf"), ".png": (body.startswith(b"\x89PNG\r\n\x1a\n"), "image/png"), ".jpg": (body.startswith(b"\xff\xd8\xff"), "image/jpeg"), ".jpeg": (body.startswith(b"\xff\xd8\xff"), "image/jpeg")}
    if ext == ".txt":
        try:
            body.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(400, "TXT phải dùng UTF-8")
        if b"\x00" in body:
            raise HTTPException(400, "Tệp TXT không hợp lệ")
        return "text/plain"
    if ext not in valid or not valid[ext][0]:
        raise HTTPException(400, "Chỉ nhận PDF, PNG, JPG và TXT đúng định dạng")
    return valid[ext][1]


def extract(body, mime):
    if mime == "text/plain":
        return body.decode("utf-8-sig")[:200000], "ready"
    if mime == "application/pdf":
        reader = PdfReader(io.BytesIO(body))
        if reader.is_encrypted:
            raise ValueError("PDF được mã hóa; hãy tải bản không có mật khẩu")
        if len(reader.pages) > 100:
            raise ValueError("Chỉ xử lý PDF tối đa 100 trang")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)[:200000]
        return text, "ready" if text.strip() else "needs_ocr"
    return "", "needs_ocr"


class DocumentStore:
    def __init__(self, settings):
        self.settings = settings
        self.client = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=3000, tz_aware=True)
        self.db = self.client.toychain
        self.s3 = boto3.client("s3", endpoint_url=settings.s3_endpoint, aws_access_key_id=settings.s3_key, aws_secret_access_key=settings.s3_secret, region_name="us-east-1", config=Config(signature_version="s3v4", connect_timeout=3, read_timeout=10, retries={"max_attempts": 2}, s3={"addressing_style": "path"}, request_checksum_calculation="when_required", response_checksum_validation="when_required"))

    def initialize(self):
        self.db.documents.create_index([("branch_id", 1), ("product_id", 1)])
        self.db.documents.create_index([("status", 1)])
        self.db.feedback.create_index([("product_id", 1), ("branch_id", 1)])

    @staticmethod
    def public(row):
        if not row:
            return None
        return {("id" if k == "_id" else k): v.isoformat() if hasattr(v, "isoformat") else v for k, v in row.items() if k != "object_key"}

    def upload(self, filename, body, branch, product, order, author):
        mime = detect_file(filename, body)
        doc_id = uid()
        key = f"{branch}/{doc_id}/{Path(filename).name}"
        self.s3.put_object(Bucket=self.settings.s3_bucket, Key=key, Body=body, ContentType=mime)
        row = {"_id": doc_id, "filename": Path(filename).name, "object_key": key, "branch_id": branch, "product_id": product, "order_id": order, "author": author, "mime": mime, "size": len(body), "sha256": hashlib.sha256(body).hexdigest(), "text": "", "status": "pending", "error": "", "created_at": utcnow()}
        try:
            self.db.documents.insert_one(row)
        except Exception:
            self.s3.delete_object(Bucket=self.settings.s3_bucket, Key=key)
            raise
        return self.public(row)

    def query(self, branch=None, q="", product=None):
        query = {}
        if branch:
            query["branch_id"] = branch
        if product:
            query["product_id"] = product
        if q:
            regex = {"$regex": re.escape(q), "$options": "i"}
            query["$or"] = [{"text": regex}, {"filename": regex}]
        return [self.public(row) for row in self.db.documents.find(query).sort("created_at", -1).limit(200)]

    def get(self, doc_id, branch=None):
        row = self.db.documents.find_one({"_id": doc_id})
        if not row or branch and row["branch_id"] != branch:
            raise HTTPException(404, "Không tìm thấy tài liệu")
        return row

    def process_one(self):
        stale = utcnow() - timedelta(minutes=10)
        row = self.db.documents.find_one_and_update({"$or": [{"status": "pending"}, {"status": "processing", "processing_at": {"$lt": stale}}]}, {"$set": {"status": "processing", "processing_at": utcnow()}}, return_document=ReturnDocument.AFTER)
        if not row:
            return False
        try:
            response = self.s3.get_object(Bucket=self.settings.s3_bucket, Key=row["object_key"])
            body = response["Body"].read()
            response["Body"].close()
            text, status = extract(body, row["mime"])
            result = {"text": text, "status": status, "error": "", "processed_at": utcnow()}
        except Exception as exc:
            result = {"status": "error", "error": str(exc)[:1000], "processed_at": utcnow()}
        self.db.documents.update_one({"_id": row["_id"], "status": "processing", "processing_at": row["processing_at"]}, {"$set": result})
        return True
