import { useState } from 'react';
import { api } from '../api/index.js';
import { canWrite, useAuth } from '../api/auth.js';
import { AlertChip, Battery, ConnBadge, Empty, Loading, Modal, StatusBadge } from '../common/ui.jsx';
import { ago, vnd, weight } from '../common/format.js';
import { Link } from '../router.jsx';
import { useNow, useStore } from '../state/store.jsx';
import AdminLayout from './AdminLayout.jsx';
import SupermarketSimulation from '../simulation/SupermarketSimulation.jsx';

const FILTERS = [
  { id: 'ALL', label: 'Tất cả', test: () => true },
  { id: 'AVAILABLE', label: 'Sẵn sàng', test: (c) => c.cart_status === 'AVAILABLE' },
  { id: 'IN_USE', label: 'Đang dùng', test: (c) => c.cart_status === 'IN_USE' },
  { id: 'LOCKED', label: 'Đã khoá', test: (c) => c.cart_status === 'LOCKED' },
  { id: 'OFFLINE', label: 'Offline', test: (c) => c.connection_status === 'OFFLINE' },
];

function Stat({ label, value, tone, testid }) {
  return <div className={`stat stat-${tone || 'plain'}`}><span>{label}</span><b data-testid={testid}>{value}</b></div>;
}

function AddCartModal({ onClose, onDone }) {
  const [id, setId] = useState('');
  const [name, setName] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const valid = /^[A-Za-z0-9_-]{1,32}$/.test(id);
  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErr('');
    try { const c = await api.createCart(id.trim(), name.trim()); onDone(c); } catch (x) { setErr(x.message); } finally { setBusy(false); }
  }
  return (
    <Modal title="Đăng ký xe mới" onClose={() => !busy && onClose()}>
      <form onSubmit={submit} className="form-grid" data-testid="cart-form">
        <label>Mã xe
          <input value={id} onChange={(e) => setId(e.target.value)} placeholder="vd. CART_004" maxLength={32} autoFocus data-testid="cf-id" aria-invalid={id !== '' && !valid} />
        </label>
        <label>Tên hiển thị (tuỳ chọn)
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="vd. Xe ảo Wokwi" maxLength={60} data-testid="cf-name" />
        </label>
        <p className="muted small">Mã xe phải <b>trùng đúng</b> <code>CART_ID</code> trong firmware (xe thật hoặc xe ảo Wokwi). Chỉ gồm chữ, số, <code>_</code> và <code>-</code>. Xe hiện <b>Offline</b> cho tới khi gửi tin nhắn đầu tiên.</p>
        {err && <p className="form-error" role="alert" data-testid="cf-error">⚠️ {err}</p>}
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose} disabled={busy}>Huỷ</button>
          <button type="submit" className="btn btn-primary" disabled={busy || !valid} data-testid="cf-save">{busy ? 'Đang lưu…' : 'Đăng ký'}</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Dashboard() {
  const { state, toast, refresh } = useStore();
  const auth = useAuth();
  const [adding, setAdding] = useState(false);
  const now = useNow(1000);
  const [filter, setFilter] = useState('ALL');
  const carts = Object.values(state.carts).sort((a, b) => a.cart_id.localeCompare(b.cart_id));
  const active = state.alerts.filter((a) => a.status === 'ACTIVE');
  const shown = carts.filter(FILTERS.find((f) => f.id === filter).test);
  const n = (fn) => carts.filter(fn).length;

  return (
    <AdminLayout>
      <div className="page-head">
        <h1 className="page-title">Tổng quan hệ thống</h1>
        {canWrite(auth) && <button className="btn btn-primary" onClick={() => setAdding(true)} data-testid="add-cart">＋ Đăng ký xe</button>}
      </div>
      {adding && <AddCartModal onClose={() => setAdding(false)} onDone={(c) => { setAdding(false); toast('ok', `Đã đăng ký xe ${c.cart_id}. Xe sẽ ONLINE khi gửi tin nhắn đầu tiên.`, { scope: 'admin' }); refresh(); }} />}
      {!state.loaded ? <Loading /> : (
        <>
          <section className="stats" data-testid="stats">
            <Stat label="Tổng số xe" value={carts.length} testid="stat-total" />
            <Stat label="Online" value={n((c) => c.connection_status === 'ONLINE')} tone="ok" testid="stat-online" />
            <Stat label="Offline" value={n((c) => c.connection_status === 'OFFLINE')} tone="muted" testid="stat-offline" />
            <Stat label="Đang sử dụng" value={n((c) => c.cart_status === 'IN_USE')} tone="info" testid="stat-in-use" />
            <Stat label="Đã khoá" value={n((c) => c.cart_status === 'LOCKED')} tone="danger" testid="stat-locked" />
            <Stat label="Cảnh báo" value={active.length} tone={active.length ? 'danger' : 'ok'} testid="stat-alerts" />
          </section>

          <section className={`alert-bar ${active.length ? 'has' : ''}`} data-testid="alert-bar">
            {active.length === 0 ? <span>✅ Không có cảnh báo nào đang hoạt động.</span> : (
              <>
                <b>⚠️ {active.length} cảnh báo đang hoạt động</b>
                <ul>
                  {active.slice(0, 4).map((a) => (
                    <li key={a.id} data-testid="alert-bar-item">
                      <AlertChip type={a.alert_type} /> <Link to={`/admin/carts/${a.cart_id}`}>{a.cart_id}</Link>
                      <span className="muted"> · {a.detail} · {ago(a.created_at, now)}</span>
                    </li>
                  ))}
                </ul>
                <Link to="/admin/alerts" className="link-strong">Xem tất cả →</Link>
              </>
            )}
          </section>

          <SupermarketSimulation />

          <div className="filters" role="tablist" aria-label="Lọc theo trạng thái">
            {FILTERS.map((f) => (
              <button key={f.id} role="tab" aria-selected={filter === f.id} className={`chip-btn ${filter === f.id ? 'on' : ''}`} onClick={() => setFilter(f.id)} data-testid={`filter-${f.id}`}>
                {f.label} <span className="chip-count">{carts.filter(f.test).length}</span>
              </button>
            ))}
          </div>

          {shown.length === 0 ? <Empty icon="🔍" title="Không có xe phù hợp bộ lọc" /> : (
            <div className="grid cart-grid" data-testid="admin-cart-grid">
              {shown.map((c) => (
                <Link key={c.cart_id} to={`/admin/carts/${c.cart_id}`} className={`card cart-card link-card status-${c.cart_status} ${c.connection_status === 'OFFLINE' ? 'is-offline' : ''}`} data-testid={`admin-cart-${c.cart_id}`}>
                  <div className="card-head">
                    <div><h3>{c.cart_id}</h3><span className="muted">{c.name}</span></div>
                    <StatusBadge status={c.cart_status} />
                  </div>
                  <dl className="kv">
                    <div><dt>Kết nối</dt><dd><ConnBadge status={c.connection_status} /></dd></div>
                    <div><dt>Pin</dt><dd><Battery value={c.battery_percent} /></dd></div>
                    <div><dt>Cân nặng</dt><dd>{weight(c.current_weight)}</dd></div>
                    <div><dt>Thấy lần cuối</dt><dd className="muted">{ago(c.last_seen, now)}</dd></div>
                    {c.session && <div><dt>Giỏ hàng</dt><dd>{c.session.item_count} món · {vnd(c.session.total_amount)}</dd></div>}
                  </dl>
                  {c.active_alerts.length > 0 && <div className="chips">{c.active_alerts.map((t) => <AlertChip key={t} type={t} />)}</div>}
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </AdminLayout>
  );
}

