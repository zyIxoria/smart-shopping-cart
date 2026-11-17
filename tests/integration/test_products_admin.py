"""Quản lý sản phẩm qua API: chỉ admin được thêm/sửa/ẩn; khách chỉ thấy sản phẩm đang bán."""
from __future__ import annotations

NEW = {"barcode": "8934588099999", "name": "Bánh quy bơ 100g", "price": 18000, "unit_weight": 100}


def test_only_admin_can_write(auth_stack):
    st = auth_stack
    assert st.anon.post("/api/products", NEW)[0] == 401
    assert st.viewer.post("/api/products", NEW)[0] == 403
    assert st.anon.put("/api/products/1", {"price": 1})[0] == 401
    assert st.viewer.put("/api/products/1", {"price": 1})[0] == 403


def test_create_update_hide_show(auth_stack):
    st = auth_stack
    code, p = st.admin.post("/api/products", NEW)
    assert code == 201 and p["active"] is True and p["id"] > 0 and p["price"] == 18000
    # khách quét được ngay bằng mã vạch mới
    assert st.anon.get(f"/api/products/barcode/{NEW['barcode']}")[1]["name"] == "Bánh quy bơ 100g"
    # trùng mã vạch
    code, r = st.admin.post("/api/products", NEW)
    assert code == 409 and r["error"]["code"] == "BARCODE_EXISTS"
    # sửa
    code, p2 = st.admin.put(f"/api/products/{p['id']}", {"price": 20000, "name": "  Bánh quy bơ 120g  ", "unit_weight": 120})
    assert code == 200 and p2["price"] == 20000 and p2["name"] == "Bánh quy bơ 120g" and p2["unit_weight"] == 120
    # đổi mã vạch sang mã đã có -> 409; sang mã mới -> ok
    assert st.admin.put(f"/api/products/{p['id']}", {"barcode": "8934588012341"})[0] == 409
    assert st.admin.put(f"/api/products/{p['id']}", {"barcode": "BQ-100-NEW"})[1]["barcode"] == "BQ-100-NEW"
    assert st.anon.get(f"/api/products/barcode/{NEW['barcode']}")[0] == 404
    # ẩn: khách không thấy, staff xem được bằng all=1
    assert st.admin.put(f"/api/products/{p['id']}", {"active": False})[1]["active"] is False
    assert all(x["id"] != p["id"] for x in st.anon.get("/api/products")[1])
    assert st.anon.get("/api/products/barcode/BQ-100-NEW")[0] == 404
    assert any(x["id"] == p["id"] for x in st.admin.get("/api/products?all=1")[1])
    assert all(x["id"] != p["id"] for x in st.anon.get("/api/products?all=1")[1])        # khách gửi all=1 vẫn không thấy ẩn
    assert any(x["id"] == p["id"] for x in st.viewer.get("/api/products?all=1")[1])
    # hiện lại
    assert st.admin.put(f"/api/products/{p['id']}", {"active": True})[1]["active"] is True
    assert st.anon.get("/api/products/barcode/BQ-100-NEW")[0] == 200


def test_validation_and_not_found(auth_stack):
    st = auth_stack
    bad = [
        {**NEW, "barcode": "ab"},                    # quá ngắn
        {**NEW, "barcode": "abc def"},               # ký tự không hợp lệ (firmware cũng loại)
        {**NEW, "name": "   "},                      # tên trống
        {**NEW, "price": -1},
        {**NEW, "unit_weight": 0},                   # CHECK unit_weight > 0 trong DB
        {**NEW, "price": "mười nghìn"},
        {"name": "thiếu trường"},
    ]
    for b in bad:
        code, r = st.admin.post("/api/products", b)
        assert code == 422 and r["error"]["code"] == "VALIDATION_ERROR", b
    assert st.admin.put("/api/products/99999", {"price": 1})[0] == 404
    assert st.admin.put("/api/products/1", {"price": -5})[0] == 422
    assert st.admin.put("/api/products/1", {"name": "  "})[0] == 422
    # không có sản phẩm nào bị tạo bởi các lần lỗi
    assert all(x["barcode"] != NEW["barcode"] for x in st.admin.get("/api/products?all=1")[1])


def test_sql_injection_in_fields_is_data_only(auth_stack):
    st = auth_stack
    evil = "x'); DROP TABLE products;--"
    code, p = st.admin.post("/api/products", {**NEW, "barcode": "INJ-0001", "name": evil})
    assert code == 201 and p["name"] == evil
    assert st.admin.put(f"/api/products/{p['id']}", {"name": evil + "2"})[1]["name"] == evil + "2"
    assert len(st.anon.get("/api/products")[1]) >= 15               # bảng vẫn còn nguyên dữ liệu mẫu


def test_new_product_usable_in_a_session(auth_stack):
    """Sản phẩm mới thêm bỏ vào giỏ được và tính đúng tiền; sản phẩm đã ẩn thì không bỏ vào giỏ được."""
    st = auth_stack
    code, p = st.admin.post("/api/products", {**NEW, "barcode": "SES-0001", "price": 5000})
    assert code == 201
    # chọn một xe sẵn sàng
    carts = [c for c in st.anon.get("/api/carts")[1] if c["cart_status"] == "AVAILABLE" and c["connection_status"] == "ONLINE"]
    assert carts, "cần ít nhất 1 xe giả lập ONLINE"
    code, sess = st.anon.post("/api/sessions", {"cart_id": carts[0]["cart_id"]})
    assert code == 201
    cust = st.anon.with_token(sess["token"])
    code, s2 = cust.post(f"/api/sessions/{sess['id']}/items", {"barcode": "SES-0001", "quantity": 2})
    assert code in (200, 201) and s2["total_amount"] == 10000
    st.admin.put(f"/api/products/{p['id']}", {"active": False})
    code, _ = cust.post(f"/api/sessions/{sess['id']}/items", {"barcode": "SES-0001"})
    assert code == 404
    assert cust.post(f"/api/sessions/{sess['id']}/cancel")[0] == 200
