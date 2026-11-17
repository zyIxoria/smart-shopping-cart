"""Khởi tạo ứng dụng FastAPI: APIRouter, CORS, bảo mật, lifespan (MQTT, WS, monitor), WebSocket trực tiếp và phục vụ frontend."""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse

from backend.api import routes as _routes  # noqa: F401  (đăng ký route)
from backend.api.openapi import SWAGGER_HTML, build_spec
from backend.api.registry import ROUTES
from backend.auth import ROOT_PRINCIPAL, allowed
from backend.config import Settings
from backend.database.db import Database
from backend.database.seed import seed
from backend.mqtt.gateway import Gateway
from backend.mqtt.monitor import HeartbeatMonitor
from backend.realtime.hub import Hub
from backend.realtime.ws_server import WsServer
from backend.services.context import AppContext
from backend.services.errors import ApiError
from shared.contract import iso

log = logging.getLogger("app")


def _err(status: int, code: str, message: str, **extra) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}, **extra}, status_code=status)


MAX_BODY = 64 * 1024


def _endpoint(rd):
    async def endpoint(request: Request):
        ctx = request.app.state.ctx
        principal = ctx.auth.authenticate_request(request)
        request.state.principal = principal
        if not allowed(rd.auth, principal, request.path_params):
            if not principal.authenticated:
                return JSONResponse({"error": {"code": "UNAUTHENTICATED", "message": "Cần đăng nhập"}}, status_code=401,
                                    headers={"WWW-Authenticate": 'Bearer realm="smartcart"'})
            return _err(403, "FORBIDDEN", "Bạn không có quyền thực hiện thao tác này")
        body = None
        if rd.body:
            if int(request.headers.get("content-length") or 0) > MAX_BODY:
                return _err(413, "PAYLOAD_TOO_LARGE", f"Body tối đa {MAX_BODY} byte")
            try:
                raw = await request.json()
            except Exception:  # noqa: BLE001
                return _err(400, "INVALID_JSON", "Body không phải JSON hợp lệ")
            try:
                body = rd.body.model_validate(raw)
            except ValidationError as e:
                msg = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
                return _err(422, "VALIDATION_ERROR", msg)
        out = await run_in_threadpool(rd.fn, request, body)
        status, data = out if isinstance(out, tuple) else (rd.status, out)
        return JSONResponse(data, status_code=status)
    endpoint.__name__ = rd.fn.__name__
    return endpoint


class SecurityHeadersMiddleware:
    """Header an toàn cho mọi phản hồi (I1 – giao diện web): chống sniff MIME, nhúng iframe, lộ referrer, cache dữ liệu API."""

    CSP = ("default-src 'self'; img-src * data:; connect-src *; style-src 'self' 'unsafe-inline'; "
           "script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        is_api = scope["path"].startswith("/api/") and scope["path"] not in ("/api/docs",)

        async def wrapped(message):
            if message["type"] == "http.response.start":
                h = {k.lower(): v for k, v in message.get("headers", [])}
                extra = [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"),
                         (b"referrer-policy", b"no-referrer")]
                if is_api:
                    extra.append((b"cache-control", b"no-store"))
                elif scope["path"] not in ("/api/docs", "/docs", "/redoc"):
                    extra.append((b"content-security-policy", self.CSP.encode()))
                message["headers"] = list(message.get("headers", [])) + [e for e in extra if e[0] not in h]
            await send(message)

        await self.app(scope, receive, wrapped)


class FastAPIWsConnection:
    """Adapter cho kết nối WebSocket của FastAPI tương thích giao diện WsConnection của Hub."""

    def __init__(self, ws: WebSocket, principal):
        self.ws = ws
        self.principal = principal
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)

    def send_text(self, text: str) -> None:
        try:
            self._queue.put_nowait(text)
        except (asyncio.QueueFull, Exception):
            pass


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    db = Database.from_settings(settings)
    db.init_schema()
    if settings.seed_on_start:
        seed(db)
    hub = Hub()
    ctx = AppContext(settings, db, hub)
    use_standalone_ws = settings.ws_port not in (0, settings.port)
    ws = WsServer(hub, "0.0.0.0", settings.ws_port, auth=ctx.auth, allowed_origins=settings.cors_origins)
    if not use_standalone_ws:
        ws.port = settings.port
    if settings.mqtt_enabled:
        ctx.gateway = Gateway(ctx)
    monitor = HeartbeatMonitor(ctx)

    @asynccontextmanager
    async def lifespan(app):
        hub.loop = asyncio.get_running_loop()
        if use_standalone_ws:
            await ws.start()
        if ctx.gateway:
            ctx.gateway.start()
        monitor.start()
        app.state.ws_port = ws.port
        log.info(
            "Backend sẵn sàng: http://%s:%s (DB=%s, WS=/ws trên cổng %s%s)",
            settings.host, settings.port, "postgres" if db.is_postgres else "sqlite",
            settings.port, f" + {ws.port}" if use_standalone_ws else "",
        )
        try:
            yield
        finally:
            monitor.stop()
            if ctx.gateway:
                await asyncio.to_thread(ctx.gateway.stop)
            if use_standalone_ws:
                await ws.stop()
            db.close()

    async def openapi_json(request):
        return JSONResponse(build_spec())

    async def docs(request):
        return HTMLResponse(SWAGGER_HTML)

    dist = Path(settings.frontend_dist)

    async def spa(request: Request):
        rel = request.path_params.get("path", "")
        if rel.startswith("api/"):
            return _err(404, "NOT_FOUND", f"Không có endpoint {request.url.path}")
        no_cache = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
        if dist.is_dir():
            target = (dist / rel).resolve()
            if rel and target.is_file() and dist.resolve() in target.parents:
                return FileResponse(target, media_type=mimetypes.guess_type(str(target))[0], headers=no_cache)
            index = dist / "index.html"
            if index.is_file():
                return FileResponse(index, headers=no_cache)
        return JSONResponse({"service": "Smart Shopping Cart API", "docs": "/docs", "frontend": "chưa build (cd frontend && npm run build)"})

    async def api_not_found(request, exc=None):
        return _err(404, "NOT_FOUND", f"Không có endpoint {request.url.path}")

    async def api_error(request, exc: ApiError):
        r = _err(exc.status, exc.code, exc.message)
        for k, v in (exc.headers or {}).items():
            r.headers[k] = v
        return r

    async def unhandled(request, exc: Exception):
        log.exception("Lỗi không mong đợi")
        return _err(500, "INTERNAL_ERROR", "Lỗi nội bộ máy chủ")

    async def websocket_endpoint(websocket: WebSocket):
        origin = websocket.headers.get("origin")
        allowed_origins = [o for o in (settings.cors_origins or []) if o != "*"]
        if allowed_origins and origin and origin not in allowed_origins:
            await websocket.close(code=1008)
            return
        if len(hub.clients) >= WsServer.MAX_CLIENTS:
            await websocket.close(code=1013)
            return

        await websocket.accept()
        initial_p = ctx.auth.authenticate_token(None) if ctx.auth else ROOT_PRINCIPAL
        conn = FastAPIWsConnection(websocket, initial_p)
        hub.clients.add(conn)
        conn.send_text(json.dumps({"type": "CONNECTED", "timestamp": iso()}))

        async def sender():
            try:
                while True:
                    msg = await conn._queue.get()
                    await websocket.send_text(msg)
            except Exception:
                pass

        sender_task = asyncio.create_task(sender())
        try:
            while True:
                data = await websocket.receive_text()
                if len(data) <= 4096:
                    try:
                        msg = json.loads(data)
                        if not isinstance(msg, dict):
                            continue
                        mtype = msg.get("type")
                        if mtype == "PING":
                            conn.send_text(json.dumps({"type": "PONG", "timestamp": iso()}))
                        elif mtype == "AUTH" and ctx.auth:
                            tok = msg.get("token")
                            p = ctx.auth.authenticate_token(tok if isinstance(tok, str) else None)
                            if p.authenticated:
                                conn.principal = p
                                conn.send_text(json.dumps({"type": "AUTHED", "role": p.role, "timestamp": iso()}))
                            else:
                                conn.principal = ctx.auth.authenticate_token(None)
                                conn.send_text(json.dumps({"type": "AUTH_FAILED", "timestamp": iso()}))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        pass
        except (WebSocketDisconnect, Exception):
            pass
        finally:
            sender_task.cancel()
            hub.clients.discard(conn)

    app = FastAPI(
        title="Smart Shopping Cart API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        exception_handlers={ApiError: api_error, Exception: unhandled},
        middleware=[
            Middleware(CORSMiddleware, allow_origins=settings.cors_origins or ["*"],
                       allow_methods=["*"], allow_headers=["*"]),
            Middleware(SecurityHeadersMiddleware),
        ],
    )
    app.openapi = build_spec

    # Gom nhóm và đăng ký các route API qua FastAPI APIRouter theo từng phân hệ
    routers_by_tag: dict[str, APIRouter] = defaultdict(APIRouter)
    for rd in ROUTES:
        r = routers_by_tag[rd.tag]
        r.add_api_route(rd.path, _endpoint(rd), methods=[rd.method], summary=rd.summary, tags=[rd.tag], include_in_schema=False)
    for router in routers_by_tag.values():
        app.include_router(router)

    # Swagger / OpenAPI tương thích ngược
    app.add_route("/api/openapi.json", openapi_json, methods=["GET"])
    app.add_route("/api/docs", docs, methods=["GET"])

    # WebSocket trực tiếp trên cổng FastAPI (/ws)
    app.add_websocket_route("/ws", websocket_endpoint)

    # 404 cho API chưa đăng ký & fallback SPA
    app.add_route("/api/{rest:path}", api_not_found, methods=["GET", "POST", "PUT", "DELETE"])
    app.add_route("/{path:path}", spa, methods=["GET"])

    app.state.ctx = ctx
    app.state.ws = ws
    return app
