import os
from dataclasses import dataclass, field

BRANCHES = {"DONG": "Chi nhánh Đông", "TAY": "Chi nhánh Tây", "NAM": "Chi nhánh Nam", "BAC": "Chi nhánh Bắc"}
NODES = {"CENTRAL": "Trung tâm", **BRANCHES}


@dataclass
class Settings:
    node: str = field(default_factory=lambda: os.getenv("NODE_ID", "CENTRAL"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./toychain.db"))
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    demo_password: str = field(default_factory=lambda: os.getenv("DEMO_PASSWORD", ""))
    internal_secret: str = field(default_factory=lambda: os.getenv("INTERNAL_SECRET", ""))
    mongo_url: str = field(default_factory=lambda: os.getenv("MONGO_URL", "mongodb://localhost:27017"))
    rabbit_url: str = field(default_factory=lambda: os.getenv("RABBIT_URL", "amqp://guest:guest@localhost:5672/"))
    s3_endpoint: str = field(default_factory=lambda: os.getenv("S3_ENDPOINT", "http://localhost:9000"))
    s3_key: str = field(default_factory=lambda: os.getenv("S3_ACCESS_KEY", ""))
    s3_secret: str = field(default_factory=lambda: os.getenv("S3_SECRET_KEY", ""))
    s3_bucket: str = "toychain-documents"
    test_mode: bool = False

    def validate(self):
        if self.node not in NODES:
            raise ValueError("NODE_ID không hợp lệ")
        if len(self.jwt_secret) < 32 or len(self.internal_secret) < 24:
            raise ValueError("Cần JWT_SECRET >= 32 ký tự và INTERNAL_SECRET >= 24 ký tự")
        if not self.demo_password or len(self.demo_password) < 10:
            raise ValueError("Cần DEMO_PASSWORD >= 10 ký tự")
