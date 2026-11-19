import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "postgresql+asyncpg://dam:dam@localhost:5432/dam")
    )
    s3_endpoint_url: str = field(default_factory=lambda: _env("S3_ENDPOINT_URL", "http://localhost:9000"))
    s3_access_key: str = field(default_factory=lambda: _env("S3_ACCESS_KEY", "minioadmin"))
    s3_secret_key: str = field(default_factory=lambda: _env("S3_SECRET_KEY", "minioadmin"))
    s3_bucket: str = field(default_factory=lambda: _env("S3_BUCKET", "dam-assets"))
    s3_region: str = field(default_factory=lambda: _env("S3_REGION", "us-east-1"))
    opensearch_url: str = field(default_factory=lambda: _env("OPENSEARCH_URL", "http://localhost:9200"))
    celery_broker_url: str = field(
        default_factory=lambda: _env("CELERY_BROKER_URL", "redis://localhost:6379/0")
    )
    celery_result_backend: str = field(
        default_factory=lambda: _env("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    )
    jwt_secret: str = field(default_factory=lambda: _env("JWT_SECRET", "dev-only-secret-change-me-in-production-0123"))
    jwt_algorithm: str = "HS256"
    max_upload_bytes: int = 500 * 1024 * 1024
    idempotency_ttl_hours: int = 24


settings = Settings()
