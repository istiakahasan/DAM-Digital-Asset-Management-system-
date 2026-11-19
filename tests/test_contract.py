from pathlib import Path

import yaml
from fastapi.routing import APIRoute
from openapi_spec_validator import validate

from app.main import app
from app.routers import assets

SPEC_PATH = Path(__file__).resolve().parent.parent / "openapi.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def load_spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def test_openapi_spec_is_valid() -> None:
    validate(load_spec())


def test_all_declared_routes_exist() -> None:
    declared = {
        (method.upper(), path)
        for path, item in load_spec()["paths"].items()
        for method in item
        if method in HTTP_METHODS
    }
    # Use the generated schema: FastAPI nests included routers lazily in app.routes.
    implemented = {
        (method.upper(), path)
        for path, item in app.openapi()["paths"].items()
        for method in item
        if method in HTTP_METHODS
    }
    assert declared <= implemented, f"Missing routes: {declared - implemented}"


def test_every_route_has_permission_dependency() -> None:
    for route in assets.router.routes:
        if isinstance(route, APIRoute):
            names = {d.call.__name__ for d in route.dependant.dependencies if d.call}
            assert "checker" in names, f"{route.path} lacks a permission check"
