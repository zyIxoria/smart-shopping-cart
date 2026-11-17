// Store toàn cục: context + reducer. Nạp dữ liệu qua REST, cập nhật qua WebSocket,
// tự đồng bộ lại sau khi nối lại và poll dự phòng khi WS mất.
import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef } from 'react';
import { api, connectEvents, USE_MOCK } from '../api/index.js';
import { authStore, useAuth, wsToken } from '../api/auth.js';

const initial = { carts: {}, alerts: [], eventLog: [], ws: 'connecting', loaded: false, error: null, toasts: [], rejects: 0 };

let eventSeq = 1;
function summarizeEvent(ev) {
  const ts = ev.timestamp || new Date().toISOString();
  const cid = ev.cart_id || ev.cart?.cart_id || 'SYSTEM';
  let summary = ev.type;
  if (ev.type === 'CART_UPDATED' && ev.cart) {
    const c = ev.cart;
    const items = c.session ? `${c.session.item_count} món · ${c.session.total_amount}đ` : 'chưa có phiên';
    summary = `${c.connection_status} · ${c.cart_status} · Pin ${Math.round(c.battery_percent ?? 0)}% · ${Math.round(c.current_weight ?? 0)}g (${items})`;
  } else if (ev.type === 'ALERT_TRIGGERED') {
    summary = `Mở cảnh báo ${ev.alert?.alert_type}: ${ev.alert?.detail || ''}`;
  } else if (ev.type === 'ALERT_RESOLVED') {
    summary = `Đóng cảnh báo ${ev.alert?.alert_type}`;
  } else if (ev.type === 'SCAN_REJECTED') {
    summary = `Từ chối quét (${ev.reason}): ${ev.message}`;
  } else if (ev.type === 'COMMAND_ACK') {
    summary = `Lệnh ${ev.command?.command_type} → ${ev.command?.status}`;
  } else if (ev.type === 'CART_EVENT') {
    summary = `${ev.event?.event_type || 'EVENT'}: ${ev.event?.description || ''}`;
  } else if (ev.type === 'CONNECTED') {
    summary = 'Kết nối kênh WebSocket thành công';
  } else if (ev.type === 'AUTHED') {
    summary = `Xác thực WebSocket thành công (${ev.role})`;
  }
  return { id: eventSeq++, type: ev.type, cart_id: cid, timestamp: ts, summary };
}

function reducer(s, a) {
  switch (a.type) {
    case 'carts': {
      const carts = {};
      a.carts.forEach((c) => { carts[c.cart_id] = c; });
      return { ...s, carts, loaded: true, error: null };
    }
    case 'cart': return { ...s, carts: { ...s.carts, [a.cart.cart_id]: a.cart } };
    case 'alerts': return { ...s, alerts: a.alerts };
    case 'alert_upsert': {
      const rest = s.alerts.filter((x) => x.id !== a.alert.id);
      return { ...s, alerts: [a.alert, ...rest].sort((x, y) => y.id - x.id) };
    }
    case 'log_event': {
      const entry = summarizeEvent(a.event);
      const prev = s.eventLog[0];
      // Gộp các nhịp heartbeat/CART_UPDATED giống hệt nhau liên tiếp để bảng log không bị trôi
      if (prev && entry.type === 'CART_UPDATED' && prev.type === 'CART_UPDATED' && prev.cart_id === entry.cart_id && prev.summary === entry.summary) {
        return s;
      }
      return { ...s, eventLog: [entry, ...s.eventLog].slice(0, 50) };
    }
    case 'ws': return { ...s, ws: a.status };
    case 'error': return { ...s, error: a.message, loaded: true };
    case 'toast': return { ...s, toasts: [...s.toasts, a.toast].slice(-4) };
    case 'toast_dismiss': return { ...s, toasts: s.toasts.filter((t) => t.id !== a.id) };
    default: return s;
  }
}

const Ctx = createContext(null);
let toastSeq = 1;

export function StoreProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initial);
  const wsRef = useRef('connecting');
  const auth = useAuth();
  // staff = đã đăng nhập, hoặc máy chủ không yêu cầu đăng nhập (DEV/mock). Khách chỉ lấy danh sách xe công khai.
  const staff = Boolean(auth.staff) || auth.required === false;
  const socketToken = wsToken();     // đổi khi đăng nhập/đăng xuất hoặc khách vào phiên của mình

  useEffect(() => {
    if (USE_MOCK) { authStore.setRequired(false); return; }
    api.authConfig().then((c) => authStore.setRequired(Boolean(c.auth_required))).catch(() => authStore.setRequired(false));
  }, []);

  // scope: 'all' (mọi màn hình) | 'admin' (chỉ quản trị) | 'customer' (chỉ khách đang dùng xe cart_id)
  const toast = useCallback((kind, text, { ttl = 4500, scope = 'all', cart_id } = {}) => {
    const id = toastSeq++;
    dispatch({ type: 'toast', toast: { id, kind, text, scope, cart_id } });
    setTimeout(() => dispatch({ type: 'toast_dismiss', id }), ttl);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [carts, alerts] = await Promise.all([api.getCarts(), staff ? api.getAlerts() : Promise.resolve([])]);
      dispatch({ type: 'carts', carts });
      dispatch({ type: 'alerts', alerts });
    } catch (e) {
      dispatch({ type: 'error', message: e.message });
    }
  }, [staff]);

  useEffect(() => {
    refresh();
    if (auth.required === null && !USE_MOCK) return undefined;   // chờ biết có cần đăng nhập không rồi mới nối WebSocket
    const stop = connectEvents(
      (ev) => {
        dispatch({ type: 'log_event', event: ev });
        switch (ev.type) {
          case 'CART_UPDATED': dispatch({ type: 'cart', cart: ev.cart }); break;
          case 'ALERT_TRIGGERED':
            dispatch({ type: 'alert_upsert', alert: ev.alert });
            toast('warn', `${ev.cart_id}: ${ev.alert.detail}`, { scope: 'admin' });
            break;
          case 'ALERT_RESOLVED': dispatch({ type: 'alert_upsert', alert: ev.alert }); break;
          case 'SCAN_REJECTED':
            toast('error', ev.message, { scope: 'customer', cart_id: ev.cart_id });
            toast('error', `${ev.cart_id}: quét bị từ chối – ${ev.message}`, { scope: 'admin' });
            break;
          case 'COMMAND_ACK': {
            const c = ev.command;
            const manual = c.command_type === 'LOCK_CART' || c.command_type === 'UNLOCK_CART';
            if (manual || c.status !== 'OK') toast(c.status === 'OK' ? 'ok' : 'error', `${ev.cart_id}: ${c.command_type} → ${c.status}`, { scope: 'admin' });
            break;
          }
          case 'CONNECTED': refresh(); break;
          default: break;
        }
      },
      (status) => {
        const prev = wsRef.current;
        wsRef.current = status;
        dispatch({ type: 'ws', status });
        if (status === 'open' && prev !== 'open' && prev !== 'connecting') refresh();
      },
    );
    // poll dự phòng khi WebSocket không mở
    const poll = setInterval(() => { if (wsRef.current !== 'open') refresh(); }, 5000);
    return () => { stop(); clearInterval(poll); };
  }, [refresh, toast, auth.required, socketToken]);   // đổi tài khoản => nối lại WebSocket để xác thực lại

  const value = useMemo(() => ({ state, dispatch, toast, refresh, mock: USE_MOCK }), [state, toast, refresh]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useStore = () => useContext(Ctx);

export function useNow(ms = 1000) {
  const [, force] = useReducer((x) => x + 1, 0);
  useEffect(() => { const t = setInterval(force, ms); return () => clearInterval(t); }, [ms]);
  return Date.now();
}
