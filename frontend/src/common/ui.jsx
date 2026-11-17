import { useEffect } from 'react';
import { ALERT_TYPE, CART_STATUS, CONN } from './format.js';
import { useStore } from '../state/store.jsx';

export function Badge({ tone = 'muted', children, ...rest }) {
  return <span className={`badge badge-${tone}`} {...rest}>{children}</span>;
}

export const StatusBadge = ({ status }) => <Badge tone={CART_STATUS[status]?.tone} data-testid="cart-status">{CART_STATUS[status]?.label || status}</Badge>;
export const ConnBadge = ({ status }) => (
  <Badge tone={CONN[status]?.tone} data-testid="conn-status"><i className={`dot dot-${status === 'ONLINE' ? 'ok' : 'off'}`} />{CONN[status]?.label || status}</Badge>
);
export const AlertChip = ({ type }) => (
  <Badge tone={ALERT_TYPE[type]?.tone} data-testid={`alert-chip-${type}`}>{ALERT_TYPE[type]?.icon} {ALERT_TYPE[type]?.label || type}</Badge>
);

export function Battery({ value }) {
  if (value == null) return <span className="muted">—</span>;
  const v = Math.max(0, Math.min(100, value));
  const tone = v < 20 ? 'danger' : v < 40 ? 'warn' : 'ok';
  return (
    <span className="battery" title={`Pin ${v.toFixed(0)}%`} data-testid="battery">
      <span className="battery-bar"><span className={`battery-fill fill-${tone}`} style={{ width: `${v}%` }} /></span>
      <b>{v.toFixed(0)}%</b>
    </span>
  );
}

export function Modal({ title, children, onClose, wide }) {
  useEffect(() => {
    const k = (e) => e.key === 'Escape' && onClose?.();
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className={`modal ${wide ? 'modal-wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function Toasts({ scope, cartId }) {
  const { state } = useStore();
  const visible = state.toasts.filter((t) => t.scope === 'all' || (t.scope === scope && (scope !== 'customer' || t.cart_id === cartId)));
  return (
    <div className="toasts" aria-live="polite">
      {visible.map((t) => <div key={t.id} className={`toast toast-${t.kind}`} data-testid="toast">{t.text}</div>)}
    </div>
  );
}

export function Empty({ icon = '🛒', title, hint }) {
  return (
    <div className="empty">
      <div className="empty-icon" aria-hidden="true">{icon}</div>
      <b>{title}</b>
      {hint && <p>{hint}</p>}
    </div>
  );
}

export function Loading({ text = 'Đang tải…' }) {
  return <div className="loading"><span className="spinner" />{text}</div>;
}

export function WsIndicator() {
  const { state, mock } = useStore();
  const m = mock ? { cls: 'info', t: 'Dữ liệu giả (mock)' } : { open: { cls: 'ok', t: 'Realtime' }, connecting: { cls: 'warn', t: 'Đang nối…' }, closed: { cls: 'danger', t: 'Mất realtime' } }[state.ws] || { cls: 'warn', t: state.ws };
  return <span className={`ws ws-${m.cls}`} data-testid="ws-status" title="Trạng thái kênh realtime (WebSocket)"><i className="dot" /> {m.t}</span>;
}

export function ErrorBanner({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="banner banner-danger" role="alert">
      <span>⚠️ {error}</span>
      {onRetry && <button className="btn btn-small" onClick={onRetry}>Thử lại</button>}
    </div>
  );
}
