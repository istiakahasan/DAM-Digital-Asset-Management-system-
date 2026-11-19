# DAM: Digital Asset Management System

See [architecture.md](architecture.md) for the system design.

## Dependencies

The minimal production stack is listed below by ecosystem. Pick one.

| Concern | Python (FastAPI) | Node.js (NestJS) | Go |
|---|---|---|---|
| Web framework | `fastapi`, `uvicorn` | `@nestjs/core`, `@nestjs/platform-express` | `chi` or `echo` |
| Database ORM | `sqlalchemy`, `alembic` (migrations) | `prisma` or `typeorm` | `sqlc` or `gorm` |
| Object storage SDK | `boto3` (S3) | `@aws-sdk/client-s3` | `aws-sdk-go-v2` |
| Search client | `opensearch-py` | `@opensearch-project/opensearch` | `opensearch-go` |
| Task queue | `celery`, `redis` | `bullmq` | `asynq` or `river` |
| Validation | `pydantic` | `class-validator` | `go-playground/validator` |
| Auth | `python-jose`, `passlib` | `@nestjs/passport`, `passport-jwt` | `golang-jwt/jwt` |
| Testing | `pytest`, `httpx` | `jest`, `supertest` | `testify` |
| Linting/formatting | `ruff`, `black`, `mypy` | `eslint`, `prettier` | `golangci-lint` |

### Infrastructure (Docker Compose for local dev)

- PostgreSQL 15+
- Redis 7+
- OpenSearch 2.x
- MinIO (S3-compatible local storage)
