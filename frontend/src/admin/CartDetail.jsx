import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/index.js';
import { canWrite, useAuth } from '../api/auth.js';
import { LineChart } from '../common/charts.jsx';
import { AlertChip, Battery, ConnBadge, Empty, Loading, Modal, StatusBadge } from '../common/ui.jsx';
import { ALERT_STATUS, ago, dateTime, timeOnly, vnd, weight } from '../common/format.js';
import { Badge } from '../common/ui.jsx';
import { Link } from '../router.jsx';
import { useNow, useStore } from '../state/store.jsx';
import AdminLayout from './AdminLayout.jsx';

export default function CartDetail({ params }) {
  const id = params.id;
  const { state, toast } = useStore();
  const auth = useAuth();
  const now = useNow(1000);
  const cart = state.carts[id];
  const [telemetry, setTelemetry] = useState([]);
  const [session, setSession] = useState(null);
  const [commands, setCommands] = useState([]);
  const [confirm, setConfirm] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [busy, setBusy] = useState(false);

  const loadTelemetry = useCallback(() => api.getTelemetry(id, 60).then(setTelemetry).catch(() => {}), [id]);
  useEffect(() => { loadTelemetry(); const t = setInterval(loadTelemetry, 5000); return () => clearInterval(t); }, [loadTelemetry]);

  const loadSession = useCallback(() => api.getCartSession(id).then(setSession).catch(() => setSession(null)), [id]);
  const loadCommands = useCallback(() => api.getCommands(id, 8).then(setCommands).catch(() => setCommands([])), [id]);
  useEffect(() => { const t = setTimeout(() => { loadSession(); loadCommands(); }, 150); return () => clearTimeout(t); }, [loadSession, loadCommands, cart]);

  if (!state.loaded) return <AdminLayout><Loading /></AdminLayout>;
  if (!cart) {
    return <AdminLayout><Empty icon="❓" title={`Không tìm thấy xe ${id}`} hint="Kiểm tra lại mã xe." /><p className="center"><Link to="/admin" className="btn">← Về tổng quan</Link></p></AdminLayout>;
  }

  const locked = cart.cart_status === 'LOCKED';
  const alerts = state.alerts.filter((a) => a.cart_id === id);

  async function toggleLock() {
    setBusy(true);
    try {
      await (locked ? api.unlockCart(id) : api.lockCart(id));   // toast thành công đến từ sự kiện COMMAND_ACK
    } catch (e) {
      toast('error', e.code === 'COMMAND_TIMEOUT' ? 'Xe không phản hồi (hết thời gian chờ ACK)' : e.message);
    } finally { setBusy(false); setConfirm(false); }
  }

  async function cancelSession() {
    setBusy(true);
    try {
      await api.cancelSession(session.id);
      toast('ok', `Đã huỷ phiên #${session.id} của ${id}`, { scope: 'admin' });
      setSession(null); loadSession();
    } catch (e) { toast('error', e.message, { scope: 'admin' }); } finally { setBusy(false); setConfirmCancel(false); }
  }

  const pts = (key) => telemetry.map((t) => ({ y: t[key], t: t.timestamp }));

  return (
    <AdminLayout>
      <div className="crumbs"><Link to="/admin">Tổng quan</Link> / <b>{id}</b></div>
      <div className="detail-head">
        <div>
          <h1 className="page-title" data-testid="detail-title">{cart.name} <span className="muted mono">({cart.cart_id})</span></h1>
          <div className="status-badges"><StatusBadge status={cart.cart_status} /><ConnBadge status={cart.connection_status} /></div>
        </div>
        <button className={`btn ${locked ? 'btn-primary' : 'btn-danger'}`} onClick={() => setConfirm(true)} disabled={busy || cart.connection_status !== 'ONLINE' || !canWrite(auth)} data-testid="lock-toggle" title={!canWrite(auth) ? 'Tài khoản chỉ xem – cần quyền quản trị để khoá/mở khoá' : cart.connection_status !== 'ONLINE' ? 'Xe đang offline, không thể gửi lệnh' : ''}>
          {busy ? 'Đang chờ xe xác nhận…' : locked ? '🔓 Mở khoá xe' : '🔒 Khoá xe'}
        </button>
      </div>

      <div className="detail-grid">
        <section className="card">
          <h3>Thông tin thiết bị</h3>
          <dl className="kv">
            <div><dt>Pin</dt><dd><Battery value={cart.battery_percent} /></dd></div>
            <div><dt>Cân nặng hiện tại</dt><dd data-testid="detail-weight">{weight(cart.current_weight)}</dd></div>
            <div><dt>Thấy lần cuối</dt><dd>{ago(cart.last_seen, now)} <span className="muted small">({dateTime(cart.last_seen)})</span></dd></div>
            <div><dt>Cảnh báo đang bật</dt><dd>{cart.active_alerts.length ? <span className="chips">{cart.active_alerts.map((t) => <AlertChip key={t} type={t} />)}</span> : <span className="muted">Không có</span>}</dd></div>
          </dl>
        </section>
        <section className="card" data-testid="detail-session">
          <h3>Phiên mua hàng hiện tại</h3>
          {!session ? <p className="muted">Không có phiên đang diễn ra.</p> : (
            <>
              <dl className="kv">
                <div><dt>Phiên</dt><dd>#{session.id} · bắt đầu {ago(session.started_at, now)}</dd></div>
                <div><dt>Tạm tính</dt><dd><b>{vnd(session.total_amount)}</b> ({session.item_count} món)</dd></div>
                <div><dt>Cân dự kiến</dt><dd>{weight(session.expected_weight)}</dd></div>
              </dl>
              <ul className="plain-list">{session.items.map((i) => <li key={i.id}>{i.name} <span className="muted">× {i.quantity}</span></li>)}</ul>
              {canWrite(auth) && <button className="btn btn-small btn-danger" onClick={() => setConfirmCancel(true)} disabled={busy} data-testid="cancel-session">Huỷ phiên này</button>}
            </>
          )}
        </section>
      </div>

      <section className="charts" data-testid="charts">
        <LineChart title="Pin" unit="%" points={pts('battery_percent')} min={0} max={100} color="var(--ok)" testid="chart-battery" />
        <LineChart title="Cân nặng" unit="g" points={pts('actual_weight')} min={0} minSpan={100} color="var(--info)" testid="chart-weight" />
      </section>

      <div className="detail-grid">
        <section className="card">
          <h3>Cảnh báo của xe</h3>
          {alerts.length === 0 ? <p className="muted">Chưa có cảnh báo nào.</p> : (
            <ul className="plain-list" data-testid="detail-alerts">
              {alerts.slice(0, 8).map((a) => (
                <li key={a.id}><AlertChip type={a.alert_type} /> <Badge tone={ALERT_STATUS[a.status].tone}>{ALERT_STATUS[a.status].label}</Badge> <span className="muted small">{a.detail} · {dateTime(a.created_at)}</span></li>
              ))}
            </ul>
          )}
        </section>
        <section className="card">
          <h3>Telemetry gần đây</h3>
          {telemetry.length === 0 ? <p className="muted">Chưa có dữ liệu.</p> : (
            <table className="table small" data-testid="telemetry-table">
              <thead><tr><th>Thời gian</th><th className="num">Pin</th><th className="num">Cân</th></tr></thead>
              <tbody>{telemetry.slice(-8).reverse().map((t) => (
                <tr key={t.id}><td>{timeOnly(t.timestamp)}</td><td className="num">{Number(t.battery_percent).toFixed(1)}%</td><td className="num">{weight(t.actual_weight)}</td></tr>
              ))}</tbody>
            </table>
          )}
        </section>
      </div>

      <section className="card" style={{ marginTop: '16px' }}>
        <h3>Lịch sử lệnh điều khiển gần đây</h3>
        {commands.length === 0 ? <p className="muted">Chưa có lệnh nào được gửi tới xe này.</p> : (
          <table className="table small" data-testid="commands-table">
            <thead><tr><th>Thời gian</th><th>Loại lệnh</th><th>Trạng thái</th><th>Ghi chú</th></tr></thead>
            <tbody>{commands.map((c) => (
              <tr key={c.command_id}>
                <td>{timeOnly(c.created_at)}</td>
                <td className="mono">{c.command_type}</td>
                <td><Badge tone={c.status === 'OK' ? 'ok' : c.status === 'PENDING' ? 'warn' : 'danger'}>{c.status}</Badge></td>
                <td className="muted small">{c.message || '—'}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </section>

      {confirmCancel && session && (
        <Modal title="Huỷ phiên mua hàng?" onClose={() => !busy && setConfirmCancel(false)}>
          <p>Phiên #{session.id} ({session.item_count} món, {vnd(session.total_amount)}) sẽ bị huỷ và <b>giỏ hàng bị xoá</b>. Xe {id} trở về trạng thái sẵn sàng. Không thể hoàn tác.</p>
          <div className="modal-actions">
            <button className="btn" onClick={() => setConfirmCancel(false)} disabled={busy}>Giữ phiên</button>
            <button className="btn btn-danger" onClick={cancelSession} disabled={busy} data-testid="cancel-session-confirm">{busy ? 'Đang huỷ…' : 'Huỷ phiên'}</button>
          </div>
        </Modal>
      )}

      {confirm && (
        <Modal title={locked ? 'Mở khoá xe?' : 'Khoá xe?'} onClose={() => !busy && setConfirm(false)}>
          <p>{locked ? `Xe ${id} sẽ hoạt động trở lại.` : `Xe ${id} sẽ ngừng ghi nhận sản phẩm và khách không thể thanh toán cho đến khi được mở khoá.`}</p>
          <p className="muted small">Lệnh được gửi qua MQTT; trạng thái chỉ đổi sau khi xe gửi ACK.</p>
          <div className="modal-actions">
            <button className="btn" onClick={() => setConfirm(false)} disabled={busy}>Huỷ</button>
            <button className={`btn ${locked ? 'btn-primary' : 'btn-danger'}`} onClick={toggleLock} disabled={busy} data-testid="lock-confirm">{busy ? 'Đang gửi…' : 'Xác nhận'}</button>
          </div>
        </Modal>
      )}
    </AdminLayout>
  );
}

