"""Pydantic schemas (request body + mô tả OpenAPI)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    cart_id: str = Field(..., examples=["CART_001"])


class CartCreate(BaseModel):
    cart_id: str = Field(..., pattern=r"^[A-Za-z0-9_-]{1,32}$", examples=["CART_004"])
    name: str | None = Field(None, max_length=60, examples=["Xe phần cứng ESP32"])


class ItemAdd(BaseModel):
    product_id: int | None = Field(None, examples=[1])
    barcode: str | None = Field(None, examples=["8934588012341"])
    quantity: int = Field(1, ge=1, le=99)


class Product(BaseModel):
    id: int
    barcode: str
    name: str
    price: int = Field(..., description="VND")
    unit_weight: float = Field(..., description="gram")
    image: str = ""
    active: bool = True


class ProductCreate(BaseModel):
    barcode: str = Field(..., pattern=r"^[0-9A-Za-z-]{4,64}$", description="4–64 ký tự [0-9A-Za-z-] (khớp bộ lọc của firmware)", examples=["8934588099999"])
    name: str = Field(..., min_length=1, max_length=120, examples=["Bánh quy bơ 100g"])
    price: int = Field(..., ge=0, le=1_000_000_000, description="VND", examples=[18000])
    unit_weight: float = Field(..., gt=0, le=100_000, description="gram (> 0)", examples=[100])
    image: str = Field("", max_length=500)


class ProductUpdate(BaseModel):
    """Chỉ gửi các trường cần đổi. Không xoá hẳn sản phẩm (giữ lịch sử giỏ hàng): đặt active=false để ẩn."""
    barcode: str | None = Field(None, pattern=r"^[0-9A-Za-z-]{4,64}$")
    name: str | None = Field(None, min_length=1, max_length=120)
    price: int | None = Field(None, ge=0, le=1_000_000_000)
    unit_weight: float | None = Field(None, gt=0, le=100_000)
    image: str | None = Field(None, max_length=500)
    active: bool | None = None


class Cart(BaseModel):
    cart_id: str
    name: str
    cart_status: str
    connection_status: str
    battery_percent: float | None
    current_weight: float
    last_seen: str | None
    active_alerts: list[str]
    session: dict | None


class Alert(BaseModel):
    id: int
    cart_id: str
    alert_type: str
    status: str
    detail: str
    created_at: str
    resolved_at: str | None


class CartItem(BaseModel):
    id: int
    product_id: int
    barcode: str
    name: str
    quantity: int
    unit_price: int
    unit_weight: float
    line_total: int


class Session(BaseModel):
    id: int
    cart_id: str
    status: str
    started_at: str
    ended_at: str | None
    total_amount: int
    note: str
    items: list[CartItem]
    item_count: int
    expected_weight: float
    actual_weight: float


class Command(BaseModel):
    command_id: str
    cart_id: str
    command_type: str
    parameters: dict
    status: str = Field(..., description="PENDING | OK | FAILED | TIMEOUT")
    message: str


class ErrorBody(BaseModel):
    error: dict


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, examples=["admin"])
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_in: int = Field(..., description="giây")
    role: str
    username: str


class AuthConfig(BaseModel):
    auth_required: bool = Field(..., description="false = máy chủ chạy AUTH_ENABLED=0 (chỉ dùng DEV)")


class Me(BaseModel):
    role: str
    username: str = ""
    session_id: int | None = None
    cart_id: str | None = None


class SessionStarted(Session):
    token: str = Field("", description="Token của khách cho phiên này (Authorization: Bearer ...); rỗng nếu AUTH tắt")
    token_expires_in: int = 0


class SimAction(BaseModel):
    model_config = ConfigDict(extra="allow")
