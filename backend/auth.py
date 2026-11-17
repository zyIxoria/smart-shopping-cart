"""Xác thực & phân quyền cho REST API và WebSocket.

Vai trò (xem docs/SECURITY.md):
  admin     – toàn quyền (đăng ký xe, khoá/mở khoá, huỷ phiên...)
  viewer    – chỉ xem (dashboard, cảnh báo, telemetry); tạo bằng VIEWER_USERNAME/VIEWER_PASSWORD
  customer  – token cấp khi bắt đầu phiên, chỉ thao tác trên ĐÚNG phiên/xe của mình
  anonymous – danh mục sản phẩm, danh sách xe đã che thông tin phiên, đăng nhập, bắt đầu phiên

Token là chuỗi HMAC-SHA256 có hạn (shared.security.make_token), gửi bằng `Authorization: Bearer <token>`.
Đăng xuất thu hồi token qua danh sách jti trong bộ nhớ (hết hạn thì tự dọn).
"""
from __future__ import annotations

import logging
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass

from shared import security

log = logging.getLogger("auth")

STAFF = ("admin", "viewer")


@dataclass(frozen=True)
class Principal:
    role: str                        # admin | viewer | customer | anonymous
    name: str = ""
    session_id: int | None = None
    cart_id: str | None = None
    jti: str | None = None
    exp: float = 0

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF

    @property
    def authenticated(self) -> bool:
        return self.role != "anonymous"


ANONYMOUS = Principal("anonymous")
ROOT_PRINCIPAL = Principal("admin", "(auth tắt)")      # khi AUTH_ENABLED=0 mọi request là admin


class RateLimitError(Exception):
    def __init__(self, retry_after: float):
        super().__init__("quá nhiều yêu cầu")
        self.retry_after = max(1, int(retry_after + 0.999))


class AuthService:
    def __init__(self, settings):
        s = settings
        self.enabled = s.auth_enabled
        self.s = s
        if s.token_secret:
            self.secret = s.token_secret.encode("utf-8")
            if len(s.token_secret) < 16:
                log.warning("TOKEN_SECRET quá ngắn (<16 ký tự)")
        else:
            self.secret = secrets.token_bytes(32)
            if self.enabled:
                log.warning("TOKEN_SECRET chưa đặt: dùng khoá ngẫu nhiên, mọi token mất hiệu lực khi Backend khởi động lại")
        self.users: dict[str, tuple[str, str]] = {}     # username -> (password_hash, role)
        self.generated_admin_password: str | None = None
        if self.enabled:
            self._load_users()
        self._dummy = security.hash_password("dummy-password", iterations=1000)
        self._lock = threading.Lock()
        self._fails: dict[tuple[str, str], list[float]] = {}
        self._locked_until: dict[tuple[str, str], float] = {}
        self._revoked: dict[str, float] = {}             # jti -> exp
        self._hits: dict[tuple[str, str], deque] = {}

    # --- người dùng ------------------------------------------------------------
    def _load_users(self) -> None:
        s = self.s
        if s.admin_password_hash:
            h = s.admin_password_hash
        else:
            pw = s.admin_password
            if not pw:
                pw = self.generated_admin_password = secrets.token_urlsafe(12)
                log.warning("ADMIN_PASSWORD chưa đặt – mật khẩu tạm thời cho lần chạy này: %s  (user: %s)", pw, s.admin_username)
            elif len(pw) < 8:
                log.warning("ADMIN_PASSWORD ngắn hơn 8 ký tự – nên dùng mật khẩu mạnh hơn")
            h = security.hash_password(pw)
        self.users[s.admin_username] = (h, "admin")
        if s.viewer_username and s.viewer_password:
            self.users[s.viewer_username] = (security.hash_password(s.viewer_password), "viewer")

    # --- đăng nhập + khoá tạm -------------------------------------------------------
    def login(self, username: str, password: str, ip: str) -> tuple[str, Principal, int]:
        """-> (token, principal, expires_in). Ném PermissionError (sai) hoặc RateLimitError (đang bị khoá)."""
        key = (ip, username.lower())
        now = time.time()
        with self._lock:
            until = self._locked_until.get(key, 0)
            if until > now:
                raise RateLimitError(until - now)
        rec = self.users.get(username)
        ok = security.verify_password(password, rec[0] if rec else self._dummy) and rec is not None
        if not ok:
            with self._lock:
                f = [t for t in self._fails.get(key, []) if now - t < max(self.s.login_lockout_s, 60)]
                f.append(now)
                self._fails[key] = f
                if len(f) >= self.s.login_max_attempts:
                    self._locked_until[key] = now + self.s.login_lockout_s
                    self._fails.pop(key, None)
                    log.warning("Khoá đăng nhập %ss: user=%r ip=%s (quá %d lần sai)", self.s.login_lockout_s, username, ip, self.s.login_max_attempts)
            raise PermissionError("Sai tên đăng nhập hoặc mật khẩu")
        with self._lock:
            self._fails.pop(key, None)
        role = rec[1]
        ttl = self.s.admin_token_ttl_s
        jti = secrets.token_hex(8)
        token = security.make_token(self.secret, {"role": role, "sub": username, "jti": jti}, ttl)
        return token, Principal(role, username, jti=jti, exp=now + ttl), int(ttl)

    def issue_session_token(self, session_id: int, cart_id: str) -> tuple[str, int]:
        ttl = self.s.session_token_ttl_s
        jti = secrets.token_hex(8)
        tok = security.make_token(self.secret, {"role": "customer", "sid": session_id, "cart": cart_id, "jti": jti}, ttl)
        return tok, int(ttl)

    # --- kiểm tra token ----------------------------------------------------------------
    def authenticate_token(self, token: str | None) -> Principal:
        if not self.enabled:
            return ROOT_PRINCIPAL
        if not token:
            return ANONYMOUS
        c = security.verify_token(self.secret, token)
        if not c:
            return ANONYMOUS
        jti = c.get("jti")
        with self._lock:
            if jti in self._revoked:
                return ANONYMOUS
        role = c.get("role")
        if role in STAFF:
            # người dùng bị xoá khỏi cấu hình => token vô hiệu
            if c.get("sub") not in self.users:
                return ANONYMOUS
            return Principal(role, c["sub"], jti=jti, exp=c["exp"])
        if role == "customer" and isinstance(c.get("sid"), int) and isinstance(c.get("cart"), str):
            return Principal("customer", "customer", session_id=c["sid"], cart_id=c["cart"], jti=jti, exp=c["exp"])
        return ANONYMOUS

    def authenticate_request(self, request) -> Principal:
        h = request.headers.get("authorization", "")
        if h[:7].lower() == "bearer ":
            return self.authenticate_token(h[7:].strip())
        return ROOT_PRINCIPAL if not self.enabled else ANONYMOUS

    def revoke(self, p: Principal) -> None:
        if not p.jti:
            return
        now = time.time()
        with self._lock:
            self._revoked = {j: e for j, e in self._revoked.items() if e > now}
            self._revoked[p.jti] = p.exp or now + 3600

    # --- giới hạn tần suất (cho endpoint công khai tốn tài nguyên) ----------------------
    def rate_limit(self, bucket: str, ip: str, limit: int, per_s: float) -> None:
        if not self.enabled or limit <= 0:
            return
        now = time.time()
        with self._lock:
            q = self._hits.setdefault((bucket, ip), deque())
            while q and now - q[0] > per_s:
                q.popleft()
            if len(q) >= limit:
                raise RateLimitError(per_s - (now - q[0]))
            q.append(now)
            if len(self._hits) > 5000:      # chống phình bộ nhớ khi bị quét IP
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > per_s][:2500]:
                    self._hits.pop(k, None)


# --- quy tắc truy cập theo route -------------------------------------------------------
def allowed(policy: str, p: Principal, path_params: dict) -> bool:
    """policy: public | staff | admin | session | session_read | cart_session (xem tài liệu từng loại bên dưới)."""
    if policy == "public":
        return True
    if policy == "authenticated":
        return p.authenticated
    if policy == "staff":
        return p.is_staff
    if policy == "admin":
        return p.role == "admin"
    if policy == "session":          # ghi: admin hoặc chính khách của phiên
        return p.role == "admin" or (p.role == "customer" and p.session_id == path_params.get("id"))
    if policy == "session_read":     # đọc: staff hoặc chính khách của phiên
        return p.is_staff or (p.role == "customer" and p.session_id == path_params.get("id"))
    if policy == "cart_session":
        return p.is_staff or (p.role == "customer" and p.cart_id == path_params.get("cart_id"))
    return False            # chính sách lạ => từ chối (fail closed)
