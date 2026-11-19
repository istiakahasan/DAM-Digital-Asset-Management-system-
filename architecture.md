# DAM Architecture

Architecture for a Digital Asset Management (DAM) system. It uses a layered design that separates metadata, binary storage and search. It avoids a monolithic script.

## 1. Core Layers

### API Layer (REST/GraphQL)
- Handles authentication, request validation and routing.
- Uses an OpenAPI spec as the contract.

### Asset Service (Business Logic)
- Manages asset lifecycle, versioning and permission checks.
- Stateless, so it can scale horizontally.

### Storage Abstraction
- Binaries go to object storage (S3, GCS or Azure Blob). Never store large files in the database.
- Generate presigned URLs for upload and download, so file traffic bypasses the API.

### Metadata & Search
- **Relational DB (PostgreSQL):** structured metadata (rights, expiration, tags).
- **Search index (OpenSearch/Elasticsearch):** full-text and faceted queries.
- Keep the index in sync through change data capture or an event queue.

### Processing Pipeline (Async)
- Background workers handle thumbnail generation, format conversion and metadata extraction (EXIF, PDF text).
- A queue (Redis/Celery, RabbitMQ or a cloud-native queue) decouples them from the request cycle.

### Event Bus (Optional but Recommended)
- Publish `asset.uploaded`, `asset.approved` and `asset.deleted` events.
- Events enable webhooks, audit logs and downstream integrations without tight coupling.

## 2. Non-Functional Requirements

| Requirement | Rule |
|---|---|
| **Idempotency** | Upload endpoints accept an idempotency key, so retries don't create duplicate assets. |
| **Audit trail** | Every state change (approval, metadata edit, deletion) writes an immutable log entry with actor, timestamp and diff. |
| **RBAC** | Role checks happen at the service layer, not just the UI. A viewer never receives a URL that bypasses permission checks. |

## 3. Request Flow (Upload)

1. The client calls the API with an idempotency key.
2. The Asset Service checks permissions and creates the asset record in PostgreSQL.
3. The service returns a presigned upload URL, and the client uploads straight to object storage.
4. The service emits an `asset.uploaded` event.
5. Workers generate thumbnails and extract metadata.
6. The search index is updated and an audit entry is written.

## 4. Technology Mapping

See the dependency table in [README.md](README.md).
