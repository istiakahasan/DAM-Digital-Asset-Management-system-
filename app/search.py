from functools import lru_cache
from typing import Any

from opensearchpy import OpenSearch
from opensearchpy.exceptions import ConnectionError as OSConnectionError
from opensearchpy.exceptions import NotFoundError

from app.config import settings

INDEX = "dam-assets"

MAPPING: dict[str, Any] = {
    "settings": {
        "analysis": {"normalizer": {"lowercase_norm": {"type": "custom", "filter": ["lowercase"]}}}
    },
    "mappings": {
        "properties": {
            "title": {"type": "text"},
            "description": {"type": "text"},
            "tags": {"type": "keyword", "normalizer": "lowercase_norm"},
            "status": {"type": "keyword"},
            "owner_id": {"type": "keyword"},
            "original_filename": {"type": "keyword"},
            "created_at": {"type": "date"},
        }
    },
}


class SearchUnavailableError(Exception):
    """OpenSearch cannot be reached."""


@lru_cache
def get_client() -> OpenSearch:
    return OpenSearch(hosts=[settings.opensearch_url], timeout=5, max_retries=0)


def ensure_index() -> None:
    client = get_client()
    if not client.indices.exists(index=INDEX):
        client.indices.create(index=INDEX, body=MAPPING)


def index_document(doc_id: str, doc: dict[str, Any]) -> None:
    get_client().index(index=INDEX, id=doc_id, body=doc, refresh="wait_for")


def delete_document(doc_id: str) -> None:
    try:
        get_client().delete(index=INDEX, id=doc_id, refresh="wait_for")
    except NotFoundError:
        pass


def search_ids(
    q: str, tags: list[str] | None, visibility: dict[str, Any], page: int, page_size: int
) -> tuple[list[str], int]:
    """Return (asset ids for the page, total hits). Raises SearchUnavailableError."""
    filters: list[dict[str, Any]] = [visibility]
    if tags:
        filters.append({"terms": {"tags": [t.lower() for t in tags]}})
    body = {
        "from": (page - 1) * page_size,
        "size": page_size,
        "track_total_hits": True,
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": q,
                            "fields": ["title^2", "description", "tags^3"],
                        }
                    }
                ],
                "filter": filters,
            }
        },
    }
    try:
        result = get_client().search(index=INDEX, body=body)
    except (OSConnectionError, NotFoundError) as exc:
        raise SearchUnavailableError(str(exc)) from exc
    hits = result["hits"]
    return [h["_id"] for h in hits["hits"]], int(hits["total"]["value"])
