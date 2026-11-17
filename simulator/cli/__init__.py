"""CLI tương tác để điều khiển các xe giả lập."""
from __future__ import annotations

import cmd

from simulator import scenarios as sc


class SimShell(cmd.Cmd):
    intro = "Smart Cart Simulator – gõ 'help' để xem lệnh, 'quit' để thoát."
    prompt = "sim> "

    def __init__(self, carts, auto=None):
        super().__init__()
        self.carts = {c.cart_id: c for c in carts}
        self.auto = auto

    # ---- tiện ích
    def _cart(self, token: str):
        cid = token.upper()
        if token.isdigit():
            cid = f"CART_{int(token):03d}"
        c = self.carts.get(cid)
        if not c:
            print(f"Không có xe '{token}'. Xe hiện có: {', '.join(self.carts)}")
        return c

    def _args(self, line: str, n: int, usage: str):
        parts = line.split()
        if len(parts) < n:
            print("Cách dùng:", usage)
            return None
        return parts

    # ---- lệnh
    def do_carts(self, line):
        """carts – liệt kê trạng thái tất cả xe"""
        for c in self.carts.values():
            print(c.status_line())

    do_status = do_carts

    def do_catalog(self, line):
        """catalog – danh sách sản phẩm (chỉ số, mã vạch, tên, gram)"""
        c = next(iter(self.carts.values()))
        for i, (b, p) in enumerate(c.catalog.items(), 1):
            print(f"{i:>2}. {b}  {p['unit_weight']:>7.0f} g  {p['price']:>7,} đ  {p['name']}")

    def _barcode(self, cart, token: str):
        if token.isdigit() and len(token) <= 3:
            keys = list(cart.catalog)
            i = int(token) - 1
            return keys[i] if 0 <= i < len(keys) else token
        return token

    def do_scan(self, line):
        """scan <xe> <mã vạch|số thứ tự> [remove] – quét sản phẩm"""
        p = self._args(line, 2, "scan <xe> <mã vạch|STT> [remove]")
        if not p:
            return
        c = self._cart(p[0])
        if c:
            print("->", c.scan(self._barcode(c, p[1]), "REMOVE" if len(p) > 2 and p[2].lower() == "remove" else "ADD"))

    def do_unknown(self, line):
        """unknown <xe> – quét mã không tồn tại"""
        p = self._args(line, 1, "unknown <xe>")
        c = p and self._cart(p[0])
        if c:
            print("->", sc.unknown_barcode(c))

    def do_low_battery(self, line):
        """low-battery <xe> [%] – giả lập pin yếu (mặc định 15%)"""
        p = self._args(line, 1, "low-battery <xe> [%]")
        c = p and self._cart(p[0])
        if c:
            sc.low_battery(c, float(p[1]) if len(p) > 1 else 15.0)

    def do_recharge(self, line):
        """recharge <xe> – sạc đầy pin"""
        p = self._args(line, 1, "recharge <xe>")
        c = p and self._cart(p[0])
        if c:
            sc.recharge(c)

    def do_weight(self, line):
        """weight <xe> <±gram> – thêm vật lạ (+) hoặc lấy bớt đồ (−) gây lệch cân"""
        p = self._args(line, 2, "weight <xe> <±gram>")
        c = p and self._cart(p[0])
        if c:
            sc.weight_mismatch(c, float(p[1]))

    def do_fix_weight(self, line):
        """fix-weight <xe> – bỏ vật lạ, cân khớp lại"""
        p = self._args(line, 1, "fix-weight <xe>")
        c = p and self._cart(p[0])
        if c:
            sc.fix_weight(c)

    def do_offline(self, line):
        """offline <xe> [giây] – mất kết nối (tự nối lại sau N giây nếu có)"""
        p = self._args(line, 1, "offline <xe> [giây]")
        c = p and self._cart(p[0])
        if c:
            sc.drop_connection(c, float(p[1]) if len(p) > 1 else None)

    def do_online(self, line):
        """online <xe> – kết nối lại"""
        p = self._args(line, 1, "online <xe>")
        c = p and self._cart(p[0])
        if c:
            sc.reconnect(c)

    def do_log(self, line):
        """log <xe> – nhật ký gần đây của xe"""
        p = self._args(line, 1, "log <xe>")
        c = p and self._cart(p[0])
        if c:
            print("\n".join(c.log[-15:]) or "(trống)")

    def do_quit(self, line):
        """quit – thoát"""
        return True

    do_exit = do_EOF = do_quit

    def default(self, line):
        print(f"Lệnh không hợp lệ: {line.split()[0]!r}. Gõ 'help' để xem danh sách lệnh.")

    def emptyline(self):
        pass

    def precmd(self, line):   # cho phép gõ "low-battery", "fix-weight"
        parts = line.strip().split(None, 1)
        if parts:
            parts[0] = parts[0].replace("-", "_").lower()
        return " ".join(parts)
