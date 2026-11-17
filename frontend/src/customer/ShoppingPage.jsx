import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/index.js';
import { AlertChip, Battery, ConnBadge, Empty, Loading, Modal, StatusBadge } from '../common/ui.jsx';
import { vnd, weight } from '../common/format.js';
import { Link, navigate } from '../router.jsx';
import { useStore } from '../state/store.jsx';
import CustomerLayout from './CustomerLayout.jsx';

function useSession(sid) {
  const { state } = useStore();
  const [session, setSession] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(async () => {
    try { setSession(await api.getSession(sid)); setError(null); } catch (e) { setError(e); }
  }, [sid]);
  useEffect(() => { setSession(null); load(); }, [load]);
  const cart = session ? state.carts[session.cart_id] : null;
  useEffect(() => {          // cart đổi (WebSocket) -> nạp lại giỏ hàng, có debounce
    if (!session || session.status !== 'ACTIVE') return undefined;
    const t = setTimeout(load, 150);
    return () => clearTimeout(t);
  }, [cart]); // eslint-disable-line react-hooks/exhaustive-deps
  return { session, setSession, error, reload: load };
}

function StatusWidget({ s }) {
  return (
    <section className="card status-widget" data-testid="status-widget">
      <div className="status-main">
        <div>
          <span className="muted">Xe đang dùng</span>
          <h2 data-testid="cart-id">{s.cart_id}</h2>
        </div>
        <div className="status-badges"><StatusBadge status={s.cart_status} /><ConnBadge status={s.connection_status} /></div>
      </div>
      <dl className="kv kv-row">
        <div><dt>Pin</dt><dd><Battery value={s.battery_percent} /></dd></div>
        <div><dt>Cân thực tế</dt><dd data-testid="actual-weight">{weight(s.actual_weight)}</dd></div>
        <div><dt>Cân dự kiến</dt><dd data-testid="expected-weight">{weight(s.expected_weight)}</dd></div>
      </dl>
      {s.active_alerts.length > 0 && (
        <div className="chips" data-testid="session-alerts">{s.active_alerts.map((t) => <AlertChip key={t} type={t} />)}</div>
      )}
    </section>
  );
}

function ManualAdd({ sid, onDone, disabled }) {
  const { toast } = useStore();
  const [code, setCode] = useState('');
  const [products, setProducts] = useState([]);
  useEffect(() => { api.getProducts().then(setProducts).catch(() => {}); }, []);
  async function add(e) {
    e.preventDefault();
    if (!code.trim()) return;
    try {
      const s = await api.addItem(sid, { barcode: code.trim(), quantity: 1 });
      onDone(s); setCode('');
    } catch (err) { toast('error', err.message); }
  }
  return (
    <details className="card manual">
      <summary>Thêm sản phẩm thủ công</summary>
      <form onSubmit={add} className="manual-form">
        <input list="products-list" value={code} onChange={(e) => setCode(e.target.value)} placeholder="Nhập hoặc chọn mã vạch" aria-label="Mã vạch" data-testid="manual-barcode" disabled={disabled} />
        <datalist id="products-list">{products.map((p) => <option key={p.id} value={p.barcode}>{p.name}</option>)}</datalist>
        <button className="btn" disabled={disabled || !code.trim()} data-testid="manual-add">Thêm</button>
      </form>
      <p className="muted small">Thêm thủ công không làm thay đổi cân của xe nên có thể gây cảnh báo lệch cân.</p>
    </details>
  );
}

function Receipt({ s, onClose }) {
  return (
    <div className="done" data-testid="completed">
      <div className="done-icon" aria-hidden="true">✓</div>
      <h1>Shopping Completed</h1>
      <p className="done-thanks">Thank you!</p>
      <p className="muted">Cảm ơn bạn đã mua sắm cùng Smart Cart.</p>
      <div className="card receipt">
        <h3>Hoá đơn #{s.id} · {s.cart_id}</h3>
        <table className="table">
          <tbody>
            {s.items.map((i) => (
              <tr key={i.id}><td>{i.name} <span className="muted">× {i.quantity}</span></td><td className="num">{vnd(i.line_total)}</td></tr>
            ))}
          </tbody>
          <tfoot><tr><th>Tổng cộng</th><th className="num" data-testid="receipt-total">{vnd(s.total_amount)}</th></tr></tfoot>
        </table>
        {s.note && <p className="hint-warn">{s.note}</p>}
      </div>
      <button className="btn btn-primary" onClick={onClose} data-testid="done-close">Hoàn tất</button>
    </div>
  );
}

export default function ShoppingPage({ params }) {
  const sid = Number(params.sid);
  const { toast } = useStore();
  const { session: s, setSession, error } = useSession(sid);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  if (error && !s) {
    return (
      <CustomerLayout>
        <Empty icon="🧾" title={error.status === 401 || error.status === 403 ? 'Không có quyền xem phiên này' : 'Không tìm thấy phiên mua hàng'} hint={error.status === 401 || error.status === 403 ? 'Phiên này thuộc về thiết bị khác hoặc đã hết hạn. Hãy chọn xe và bắt đầu phiên mới.' : error.message} />
        <p className="center"><Link to="/customer" className="btn btn-primary">Chọn xe khác</Link></p>
      </CustomerLayout>
    );
  }
  if (!s) return <CustomerLayout><Loading text="Đang tải giỏ hàng…" /></CustomerLayout>;
  if (done || s.status === 'COMPLETED') return <CustomerLayout><Receipt s={done || s} onClose={() => navigate('/customer')} /></CustomerLayout>;

  const locked = s.cart_status === 'LOCKED';
  const empty = s.items.length === 0;

  async function remove(item) {
    try { setSession(await api.removeItem(sid, item.id)); } catch (e) { toast('error', e.message); }
  }
  async function checkout() {
    setBusy(true);
    try { setDone(await api.checkout(sid)); setConfirm(false); } catch (e) { toast('error', e.message); setConfirm(false); } finally { setBusy(false); }
  }
  async function cancel() {
    if (!window.confirm('Huỷ phiên mua hàng này? Toàn bộ giỏ hàng sẽ bị xoá.')) return;
    try { await api.cancelSession(sid); navigate('/customer'); } catch (e) { toast('error', e.message); }
  }

  return (
    <CustomerLayout cartId={s.cart_id}>
      {locked && <div className="banner banner-danger" role="alert" data-testid="locked-banner">🔒 Xe đang bị khoá bởi quản trị viên. Vui lòng liên hệ nhân viên để được hỗ trợ.</div>}
      {s.connection_status === 'OFFLINE' && <div className="banner banner-warn" data-testid="offline-banner">📡 Xe đang mất kết nối — sản phẩm quét mới có thể chưa được ghi nhận.</div>}
      <div className="shopping">
        <div className="col-main">
          <StatusWidget s={s} />
          <section className="card" data-testid="items-card">
            <div className="card-head"><h3>Giỏ hàng</h3><span className="muted" data-testid="item-count">{s.item_count} sản phẩm</span></div>
            {empty ? (
              <Empty icon="📷" title="Giỏ hàng đang trống" hint="Quét mã vạch sản phẩm bằng máy quét trên xe để thêm vào giỏ." />
            ) : (
              <div className="table-wrap">
                <table className="table" data-testid="items-table">
                  <thead><tr><th>Sản phẩm</th><th className="num">Đơn giá</th><th className="num">SL</th><th className="num">Thành tiền</th><th /></tr></thead>
                  <tbody>
                    {s.items.map((i) => (
                      <tr key={i.id} data-testid="item-row">
                        <td><b>{i.name}</b><div className="muted mono small">{i.barcode}</div></td>
                        <td className="num">{vnd(i.unit_price)}</td>
                        <td className="num" data-testid="item-qty">{i.quantity}</td>
                        <td className="num"><b>{vnd(i.line_total)}</b></td>
                        <td className="num"><button className="btn btn-ghost btn-small" onClick={() => remove(i)} disabled={locked} aria-label={`Xoá ${i.name}`}>Xoá</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <ManualAdd sid={sid} onDone={setSession} disabled={locked} />
        </div>
        <aside className="col-side">
          <section className="card summary" data-testid="order-summary">
            <h3>Tóm tắt đơn hàng</h3>
            <dl className="kv">
              <div><dt>Số mặt hàng</dt><dd>{s.items.length}</dd></div>
              <div><dt>Tổng số lượng</dt><dd>{s.item_count}</dd></div>
              <div><dt>Khối lượng dự kiến</dt><dd>{weight(s.expected_weight)}</dd></div>
            </dl>
            <div className="total"><span>Tổng cộng</span><b data-testid="total">{vnd(s.total_amount)}</b></div>
            <button className="btn btn-primary btn-block btn-lg" disabled={empty || locked} onClick={() => setConfirm(true)} data-testid="checkout-btn">Thanh toán</button>
            <button className="btn btn-link btn-block" onClick={cancel} data-testid="cancel-btn">Huỷ phiên mua hàng</button>
          </section>
        </aside>
      </div>
      {confirm && (
        <Modal title="Xác nhận thanh toán" onClose={() => !busy && setConfirm(false)}>
          <table className="table"><tbody>
            {s.items.map((i) => <tr key={i.id}><td>{i.name} <span className="muted">× {i.quantity}</span></td><td className="num">{vnd(i.line_total)}</td></tr>)}
          </tbody></table>
          <div className="total"><span>Tổng thanh toán</span><b data-testid="confirm-total">{vnd(s.total_amount)}</b></div>
          {s.active_alerts.length > 0 && <p className="hint-warn">Xe đang có cảnh báo ({s.active_alerts.length}). Cảnh báo sẽ được ghi vào hoá đơn để nhân viên kiểm tra.</p>}
          <div className="modal-actions">
            <button className="btn" onClick={() => setConfirm(false)} disabled={busy}>Quay lại</button>
            <button className="btn btn-primary" onClick={checkout} disabled={busy} data-testid="confirm-checkout">{busy ? 'Đang xử lý…' : 'Xác nhận thanh toán'}</button>
          </div>
        </Modal>
      )}
    </CustomerLayout>
  );
}
