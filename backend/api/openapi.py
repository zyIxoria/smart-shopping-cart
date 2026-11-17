"""Sinh OpenAPI 3.0 từ registry + pydantic; trang /api/docs dùng Swagger UI qua CDN."""
from __future__ import annotations

from backend.api.registry import ROUTES

SWAGGER_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Smart Cart API</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css"></head>
<body><div id="ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url:'/api/openapi.json',dom_id:'#ui'});</script></body></html>"""

ACCESS_TEXT = {
    "admin": "Quyền: **admin**.",
    "staff": "Quyền: **admin** hoặc **viewer** (nhân viên).",
    "authenticated": "Quyền: bất kỳ người đã đăng nhập (admin/viewer/khách).",
    "session": "Quyền: **admin** hoặc **khách của chính phiên này** (token nhận được từ POST /api/sessions).",
    "session_read": "Quyền: **staff** hoặc **khách của chính phiên này**.",
    "cart_session": "Quyền: **staff** hoặc khách đang dùng xe này.",
}
ERR = {"description": "Lỗi", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorBody"}}}}


def _ref(model, schemas):
    sch = model.model_json_schema(ref_template="#/components/schemas/{model}")
    for name, d in sch.pop("$defs", {}).items():
        schemas[name] = d
    schemas[model.__name__] = sch
    return {"$ref": f"#/components/schemas/{model.__name__}"}


def build_spec() -> dict:
    from backend.schemas.models import ErrorBody

    schemas: dict = {}
    _ref(ErrorBody, schemas)
    paths: dict = {}
    for r in ROUTES:
        op = {"summary": r.summary, "tags": [r.tag], "operationId": r.fn.__name__, "parameters": [], "responses": {}}
        for name in _path_params(r.openapi_path):
            op["parameters"].append({"name": name, "in": "path", "required": True, "schema": {"type": "string"}})
        for name, typ, desc in r.query:
            op["parameters"].append({"name": name, "in": "query", "required": False, "description": desc, "schema": {"type": typ}})
        if r.body:
            op["requestBody"] = {"required": True, "content": {"application/json": {"schema": _ref(r.body, schemas)}}}
        ok: dict = {"description": "Thành công"}
        resp = r.response
        if resp is not None:
            sch = {"type": "array", "items": _ref(resp[0], schemas)} if isinstance(resp, list) else _ref(resp, schemas)
            ok["content"] = {"application/json": {"schema": sch}}
        op["responses"][str(r.status)] = ok
        if r.auth != "public":
            op["security"] = [{"bearerAuth": []}]
            op["description"] = ACCESS_TEXT.get(r.auth, "")
            for code in (401, 403):
                op["responses"].setdefault(str(code), ERR)
        for code in r.errors:
            op["responses"][str(code)] = ERR
        paths.setdefault(r.openapi_path, {})[r.method.lower()] = op
    return {
        "openapi": "3.0.3",
        "info": {"title": "Smart Shopping Cart API", "version": "1.0.0",
                 "description": "REST API cho Customer UI & Admin Dashboard. Realtime: ws://HOST:8081/ws."},
        "paths": paths,
        "components": {"schemas": schemas, "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer", "description": "Token từ POST /api/auth/login (quản trị) hoặc POST /api/sessions (khách)"}}},
    }


def _path_params(path: str):
    import re
    return re.findall(r"\{(\w+)\}", path)
