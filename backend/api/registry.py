"""Registry route: một nguồn duy nhất cho cả Starlette routing lẫn OpenAPI."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

ROUTES: list["RouteDef"] = []


@dataclass
class RouteDef:
    method: str
    path: str                       # dạng Starlette: /api/products/{id:int}
    fn: Callable
    summary: str
    tag: str
    body: type | None = None
    response: object = None         # Model | [Model] | None
    query: list = field(default_factory=list)   # [(name, type, description)]
    status: int = 200
    errors: tuple = ()
    auth: str = "admin"           # public | staff | admin | session | session_read | cart_session (mặc định đóng)

    @property
    def openapi_path(self) -> str:
        return re.sub(r"\{(\w+):\w+\}", r"{\1}", self.path)


def route(method: str, path: str, summary: str, tag: str, *, body=None, response=None, query=(), status=200, errors=(), auth="admin"):
    def deco(fn):
        ROUTES.append(RouteDef(method.upper(), path, fn, summary, tag, body, response, list(query), status, tuple(errors), auth))
        return fn
    return deco
