from tests.conftest import wait_until


def test_three_carts_online(stack):
    code, carts = stack.api.get("/api/carts")
    assert code == 200 and [c["cart_id"] for c in carts] == ["CART_001", "CART_002", "CART_003"]
    assert all(c["connection_status"] == "ONLINE" and c["cart_status"] == "AVAILABLE" for c in carts)
