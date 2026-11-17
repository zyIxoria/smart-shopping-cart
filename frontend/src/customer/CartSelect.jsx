import { useState } from 'react';
import { api } from '../api/index.js';
import { hasSessionAccess, useAuth } from '../api/auth.js';
import { Battery, ConnBadge, Empty, Loading, StatusBadge } from '../common/ui.jsx';
import { vnd } from '../common/format.js';
import { navigate } from '../router.jsx';
import { useStore } from '../state/store.jsx';
import CustomerLayout from './CustomerLayout.jsx';

function reason(c) {
  if (c.connection_status !== 'ONLINE') return 'Xe đang mất kết nối';
  if (c.cart_status === 'LOCKED') return 'Xe đang bị khoá';
  return null;
}

export default function CartSelect() {
  const { state, toast } = useStore();
  const [busy, setBusy] = useState(null);
  const auth = useAuth();
  // phiên đang chạy chỉ "tiếp tục" được nếu trình duyệt này giữ token của phiên đó (hoặc là nhân viên)
  const mine = (c) => c.session && (!auth.required || hasSessionAccess(auth, c.session.id));
  const carts = Object.values(state.carts).sort((a, b) => a.cart_id.localeCompare(b.cart_id));

  async function choose(c) {
    setBusy(c.cart_id);
    try {
      const sid = c.cart_status === 'IN_USE' && mine(c) ? c.session.id : (await api.createSession(c.cart_id)).id;
      navigate(`/customer/cart/${sid}`);
    } catch (e) {
      toast('error', e.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <CustomerLayout>
      <section className="hero">
        <h1>Chọn xe đẩy của bạn</h1>
        <p>Chọn một xe đang sẵn sàng để bắt đầu mua sắm. Quét sản phẩm bằng máy quét trên xe, giỏ hàng sẽ tự cập nhật.</p>
      </section>
      {!state.loaded ? <Loading text="Đang tải danh sách xe…" /> : carts.length === 0 ? (
        <Empty icon="🛒" title="Chưa có xe nào" hint="Hãy khởi động Simulator hoặc thêm xe trong cơ sở dữ liệu." />
      ) : (
        <div className="grid cart-grid" data-testid="cart-select-grid">
          {carts.map((c) => {
            const why = reason(c);
            const resume = c.cart_status === 'IN_USE' && mine(c) && !why;
            const disabled = Boolean(why) || (c.cart_status === 'IN_USE' && !mine(c)) || busy === c.cart_id;
            return (
              <article key={c.cart_id} className={`card cart-card status-${c.cart_status}`} data-testid={`cart-card-${c.cart_id}`}>
                <div className="card-head">
                  <div><h3>{c.name}</h3><span className="muted mono">{c.cart_id}</span></div>
                  <StatusBadge status={c.cart_status} />
                </div>
                <dl className="kv">
                  <div><dt>Kết nối</dt><dd><ConnBadge status={c.connection_status} /></dd></div>
                  <div><dt>Pin</dt><dd><Battery value={c.battery_percent} /></dd></div>
                  {resume && c.session.item_count != null && <div><dt>Giỏ hiện tại</dt><dd>{c.session.item_count} món · {vnd(c.session.total_amount)}</dd></div>}
                </dl>
                <button className="btn btn-primary btn-block" disabled={disabled} onClick={() => choose(c)} data-testid={`choose-${c.cart_id}`}>
                  {busy === c.cart_id ? 'Đang xử lý…' : resume ? 'Tiếp tục phiên' : 'Bắt đầu mua sắm'}
                </button>
                {why && <p className="hint-warn">{why}</p>}
                {c.cart_status === 'IN_USE' && !mine(c) && !why && <p className="hint-warn">Xe đang được sử dụng</p>}
              </article>
            );
          })}
        </div>
      )}
    </CustomerLayout>
  );
}
