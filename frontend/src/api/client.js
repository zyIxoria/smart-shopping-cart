// Client REST thật. Base URL lấy từ VITE_API_BASE_URL (để trống = cùng origin).
import { authStore, tokenFor, wsToken } from './auth.js';

const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(status, code, message, extra) {
    super(message);
    this.status = status;
    this.code = code;
    this.extra = extra;
  }
}

async function req(method, path, body) {
  let res;
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const token = tokenFor(path);
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    res = await fetch(`${BASE}/api${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'NETWORK', 'Không kết nối được tới máy chủ');
  }
  let data = null;
  try { data = await res.json(); } catch { /* body rỗng */ }
  if (!res.ok) {
    const e = data?.error || {};
    // token hết hạn/bị thu hồi: bỏ token staff để giao diện quay về màn đăng nhập
    if (res.status === 401 && token && authStore.get().staff?.token === token) authStore.setStaff(null);
    throw new ApiError(res.status, e.code || 'HTTP_' + res.status, e.message || `Lỗi ${res.status}`, data);
  }
  return data;
}

export const realApi = {
  health: () => req('GET', '/health'),
  authConfig: () => req('GET', '/auth/config'),
  login: async (username, password) => {
    const r = await req('POST', '/auth/login', { username, password });
    authStore.setStaff(r);
    return r;
  },
  logout: async () => {
    try { await req('POST', '/auth/logout', {}); } catch { /* token đã hết hạn: vẫn đăng xuất cục bộ */ }
    authStore.setStaff(null);
  },
  getProducts: (q = '') => req('GET', `/products${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  getProductsAdmin: (q = '') => req('GET', `/products?all=1${q ? `&q=${encodeURIComponent(q)}` : ''}`),   // gồm cả sản phẩm đã ẩn (staff)
  createProduct: (p) => req('POST', '/products', p),
  updateProduct: (id, p) => req('PUT', `/products/${id}`, p),
  createCart: (cart_id, name) => req('POST', '/carts', name ? { cart_id, name } : { cart_id }),
  deleteCart: (id) => req('DELETE', `/carts/${id}`),
  getCarts: () => req('GET', '/carts'),
  getCart: (id) => req('GET', `/carts/${id}`),
  getTelemetry: (id, limit = 60) => req('GET', `/carts/${id}/telemetry?limit=${limit}`),
  getCartSession: (id) => req('GET', `/carts/${id}/session`),
  lockCart: (id) => req('POST', `/carts/${id}/lock`, {}),
  unlockCart: (id) => req('POST', `/carts/${id}/unlock`, {}),
  createSession: async (cart_id) => {
    const s = await req('POST', '/sessions', { cart_id });
    authStore.addCustomer(s);          // token của khách gắn với đúng phiên này
    return s;
  },
  getSession: (sid) => req('GET', `/sessions/${sid}`),
  addItem: (sid, payload) => req('POST', `/sessions/${sid}/items`, payload),
  removeItem: (sid, itemId) => req('DELETE', `/sessions/${sid}/items/${itemId}`),
  checkout: (sid) => req('POST', `/sessions/${sid}/checkout`, {}),
  cancelSession: (sid) => req('POST', `/sessions/${sid}/cancel`, {}),
  getAlerts: (status) => req('GET', `/alerts${status ? `?status=${status}` : ''}`),
  getCommands: (cartId, limit = 15) => req('GET', `/commands?limit=${limit}${cartId ? `&cart_id=${encodeURIComponent(cartId)}` : ''}`),
};

// ---- WebSocket realtime (mặc định dùng chung cổng FastAPI /ws; cổng thật lấy từ /api/health) ----
async function wsUrl() {
  const env = import.meta.env.VITE_WS_URL;
  if (env) return env;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  let host = location.hostname;
  if (BASE) { try { host = new URL(BASE).hostname; } catch { /* giữ host hiện tại */ } }
  let port = location.port || (location.protocol === 'https:' ? 443 : 80);
  try { port = (await realApi.health()).ws_port || port; } catch { /* Backend chưa sẵn sàng: dùng cổng hiện tại */ }
  return `${proto}://${host}:${port}/ws`;
}

export function connectSocket(onEvent, onStatus) {
  let ws; let closed = false; let retry = 800; let timer;
  const open = async () => {
    onStatus('connecting');
    try {
      const url = await wsUrl();
      if (closed) return;
      ws = new WebSocket(url);
    } catch { schedule(); return; }
    ws.onopen = () => {
      retry = 800;
      const token = wsToken();         // xác thực bằng tin nhắn đầu tiên – token không nằm trong URL
      if (token) ws.send(JSON.stringify({ type: 'AUTH', token }));
      onStatus('open');
    };
    ws.onmessage = (m) => { try { onEvent(JSON.parse(m.data)); } catch { /* bỏ qua */ } };
    ws.onclose = () => { onStatus('closed'); schedule(); };
    ws.onerror = () => { try { ws.close(); } catch { /* noop */ } };
  };
  const schedule = () => {
    if (closed) return;
    clearTimeout(timer);
    timer = setTimeout(open, retry);
    retry = Math.min(retry * 2, 8000);
  };
  open();
  return () => { closed = true; clearTimeout(timer); try { ws && ws.close(); } catch { /* noop */ } };
}
