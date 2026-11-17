// Backend giả (trong bộ nhớ) cho phép phát triển UI khi chưa có Backend thật:
//   VITE_USE_MOCK=true  hoặc thêm ?mock=1 vào URL.
// Cùng hình dạng dữ liệu & quy tắc cảnh báo với Backend thật (xem docs/api).
import seed from '../../../data/products_seed.json';
import { ApiError } from './client.js';

const BATTERY_LOW = 20;
const TOLERANCE_G = 100;
const delay = (ms = 120) => new Promise((r) => setTimeout(r, ms));
const now = () => new Date().toISOString().replace(/\.\d+Z$/, 'Z');

const products = seed.map((p, i) => ({ id: i + 1, ...p }));
const carts = {};
const sessions = {};
const telemetry = {};
let alerts = [];
let seq = { session: 1, item: 1, alert: 1 };
const listeners = new Set();

const emit = (type, payload) => listeners.forEach((fn) => fn({ type, timestamp: now(), ...payload }));

function mkCart(id, n, o = {}) {
  carts[id] = {
    cart_id: id, name: `Xe đẩy ${n}`, cart_status: 'AVAILABLE', connection_status: 'ONLINE',
    battery_percent: 90, current_weight: 0, last_seen: now(), created_at: now(), updated_at: now(), ...o,
  };
  telemetry[id] = [];
}

function items(sid) { return sessions[sid].items; }
const expected = (sid) => items(sid).reduce((s, i) => s + i.quantity * i.unit_weight, 0);
const total = (sid) => items(sid).reduce((s, i) => s + i.quantity * i.unit_price, 0);
const activeSession = (cid) => Object.values(sessions).find((s) => s.cart_id === cid && s.status === 'ACTIVE');

function sessionView(s) {
  const c = carts[s.cart_id];
  return {
    ...s, items: s.items.map((i) => ({ ...i, line_total: i.quantity * i.unit_price })),
    item_count: s.items.reduce((a, i) => a + i.quantity, 0),
    total_amount: s.status === 'ACTIVE' ? total(s.id) : s.total_amount,
    expected_weight: expected(s.id), actual_weight: c.current_weight, cart_status: c.cart_status,
    connection_status: c.connection_status, battery_percent: c.battery_percent,
    active_alerts: activeAlertTypes(s.cart_id),
  };
}
const activeAlertTypes = (cid) => alerts.filter((a) => a.cart_id === cid && a.status === 'ACTIVE').map((a) => a.alert_type);

function cartView(id) {
  const c = carts[id]; const s = activeSession(id);
  return {
    ...c, active_alerts: activeAlertTypes(id),
    session: s ? { id: s.id, started_at: s.started_at, item_count: sessionView(s).item_count, total_amount: total(s.id), expected_weight: expected(s.id) } : null,
  };
}

function raise(cid, type, detail) {
  if (alerts.some((a) => a.cart_id === cid && a.alert_type === type && a.status === 'ACTIVE')) return;
  const a = { id: seq.alert++, cart_id: cid, alert_type: type, status: 'ACTIVE', detail, created_at: now(), resolved_at: null };
  alerts.unshift(a);
  emit('ALERT_TRIGGERED', { cart_id: cid, alert: a });
}
function resolve(cid, type) {
  alerts.filter((a) => a.cart_id === cid && a.alert_type === type && a.status === 'ACTIVE').forEach((a) => {
    a.status = 'RESOLVED'; a.resolved_at = now();
    emit('ALERT_RESOLVED', { cart_id: cid, alert: a });
  });
}
function evaluate(cid) {
  const c = carts[cid]; const s = activeSession(cid);
  if (c.battery_percent < BATTERY_LOW) raise(cid, 'LOW_BATTERY', `Pin còn ${c.battery_percent.toFixed(0)}% (< ${BATTERY_LOW}%)`);
  else resolve(cid, 'LOW_BATTERY');
  if (c.cart_status === 'IN_USE' && s) {
    const diff = Math.abs(c.current_weight - expected(s.id));
    if (diff > TOLERANCE_G) raise(cid, 'WEIGHT_MISMATCH', `Cân thực tế ${c.current_weight.toFixed(0)} g, dự kiến ${expected(s.id).toFixed(0)} g (lệch ${diff.toFixed(0)} g > ${TOLERANCE_G} g)`);
    else resolve(cid, 'WEIGHT_MISMATCH');
  } else resolve(cid, 'WEIGHT_MISMATCH');
}
const push = (cid) => emit('CART_UPDATED', { cart_id: cid, cart: cartView(cid) });

function addToSession(s, p, qty = 1) {
  const ex = s.items.find((i) => i.product_id === p.id);
  if (ex) ex.quantity += qty;
  else s.items.push({ id: seq.item++, product_id: p.id, barcode: p.barcode, name: p.name, image: p.image, quantity: qty, unit_price: p.price, unit_weight: p.unit_weight });
}

// --- khởi tạo dữ liệu mẫu ---
mkCart('CART_001', 1);
mkCart('CART_002', 2, { cart_status: 'IN_USE', battery_percent: 64 });
mkCart('CART_003', 3, { battery_percent: 17 });
sessions[seq.session] = { id: seq.session, cart_id: 'CART_002', status: 'ACTIVE', started_at: now(), ended_at: null, total_amount: 0, note: '', items: [] };
addToSession(sessions[1], products[0], 2);
addToSession(sessions[1], products[2], 1);
carts.CART_002.current_weight = expected(1);
seq.session++;
evaluate('CART_003');

// mô phỏng telemetry định kỳ (pin tụt chậm, cân dao động nhẹ)
setInterval(() => {
  for (const id of Object.keys(carts)) {
    const c = carts[id];
    if (c.connection_status !== 'ONLINE') continue;
    c.last_seen = now();
    c.battery_percent = Math.max(0, +(c.battery_percent - 0.05).toFixed(2));
    const s = activeSession(id);
    const base = s ? expected(s.id) + (c._offset || 0) : 0;
    c.current_weight = Math.max(0, +(base + (Math.random() - 0.5) * 6).toFixed(1));
    telemetry[id].push({ id: Date.now() + Math.random(), cart_id: id, battery_percent: c.battery_percent, actual_weight: c.current_weight, cart_status: c.cart_status, timestamp: now() });
    telemetry[id] = telemetry[id].slice(-120);
    evaluate(id);
    push(id);
  }
}, 3000);
// khởi tạo vài điểm telemetry để biểu đồ không trống
for (const id of Object.keys(carts)) {
  for (let i = 12; i > 0; i--) {
    const c = carts[id];
    telemetry[id].push({ id: -i, cart_id: id, battery_percent: +(c.battery_percent + i * 0.05).toFixed(2), actual_weight: c.current_weight, cart_status: c.cart_status, timestamp: new Date(Date.now() - i * 10000).toISOString() });
  }
}

const must = (cond, status, code, msg) => { if (!cond) throw new ApiError(status, code, msg); };
const cartOr404 = (id) => { must(carts[id], 404, 'NOT_FOUND', `Không tìm thấy xe: ${id}`); return carts[id]; };
const sessOr404 = (id) => { must(sessions[id], 404, 'NOT_FOUND', `Không tìm thấy phiên mua hàng: ${id}`); return sessions[id]; };

export const mockApi = {
  async authConfig() { return { auth_required: false }; },
  async logout() { /* mock: không có đăng nhập */ },
  async health() { await delay(); return { status: 'ok', mqtt: 'mock', database: 'mock', websocket_clients: listeners.size, time: now() }; },
  async getProducts(q = '') { await delay(); const t = q.toLowerCase(); return products.filter((p) => p.active !== false && (!t || p.name.toLowerCase().includes(t) || p.barcode.includes(t))); },
  async getProductsAdmin(q = '') { await delay(); const t = q.toLowerCase(); return products.filter((p) => !t || p.name.toLowerCase().includes(t) || p.barcode.includes(t)); },
  async createProduct(p) {
    await delay();
    must(/^[0-9A-Za-z-]{4,64}$/.test(p.barcode || ''), 422, 'VALIDATION_ERROR', 'barcode: 4–64 ký tự [0-9A-Za-z-]');
    must((p.name || '').trim(), 422, 'VALIDATION_ERROR', 'name: không được để trống');
    must(p.price >= 0 && p.unit_weight > 0, 422, 'VALIDATION_ERROR', 'price ≥ 0 và unit_weight > 0');
    must(!products.some((x) => x.barcode === p.barcode), 409, 'BARCODE_EXISTS', `Mã vạch ${p.barcode} đã có`);
    const n = { id: Math.max(0, ...products.map((x) => x.id)) + 1, image: '', active: true, ...p, name: p.name.trim() };
    products.push(n); return { ...n };
  },
  async updateProduct(id, patch) {
    await delay(); const p = products.find((x) => x.id === id);
    must(p, 404, 'NOT_FOUND', `Không tìm thấy sản phẩm: ${id}`);
    if (patch.barcode !== undefined) must(!products.some((x) => x.barcode === patch.barcode && x.id !== id), 409, 'BARCODE_EXISTS', `Mã vạch ${patch.barcode} đã có`);
    Object.assign(p, patch); return { ...p };
  },
  async createCart(cart_id, name) {
    await delay();
    must(/^[A-Za-z0-9_-]{1,32}$/.test(cart_id || ''), 422, 'VALIDATION_ERROR', 'cart_id: chỉ gồm [A-Za-z0-9_-], tối đa 32 ký tự');
    must(!carts[cart_id], 409, 'CART_EXISTS', `Xe ${cart_id} đã tồn tại`);
    mkCart(cart_id, cart_id, { name: name || cart_id, connection_status: 'OFFLINE', battery_percent: null });
    push(cart_id); return cartView(cart_id);
  },
  async getCarts() { await delay(); return Object.keys(carts).map(cartView); },
  async getCart(id) { await delay(); cartOr404(id); return cartView(id); },
  async getTelemetry(id) { await delay(); cartOr404(id); return telemetry[id].slice(-60); },
  async getCartSession(id) { await delay(); cartOr404(id); const s = activeSession(id); must(s, 404, 'NOT_FOUND', `Không tìm thấy phiên ACTIVE của xe: ${id}`); return sessionView(s); },
  async lockCart(id) {
    await delay(400); const c = cartOr404(id);
    must(c.connection_status === 'ONLINE', 409, 'CART_OFFLINE', `Xe ${id} đang OFFLINE, không thể gửi lệnh`);
    must(c.cart_status !== 'LOCKED', 409, 'ALREADY_LOCKED', `Xe ${id} đã bị khoá`);
    c.cart_status = 'LOCKED'; push(id);
    const command = { command_id: crypto.randomUUID(), cart_id: id, command_type: 'LOCK_CART', parameters: {}, status: 'OK', message: 'Đã khoá xe' };
    emit('COMMAND_ACK', { cart_id: id, command }); return command;
  },
  async unlockCart(id) {
    await delay(400); const c = cartOr404(id);
    must(c.connection_status === 'ONLINE', 409, 'CART_OFFLINE', `Xe ${id} đang OFFLINE, không thể gửi lệnh`);
    must(c.cart_status === 'LOCKED', 409, 'NOT_LOCKED', `Xe ${id} không ở trạng thái LOCKED`);
    c.cart_status = activeSession(id) ? 'IN_USE' : 'AVAILABLE'; push(id);
    const command = { command_id: crypto.randomUUID(), cart_id: id, command_type: 'UNLOCK_CART', parameters: {}, status: 'OK', message: 'Đã mở khoá' };
    emit('COMMAND_ACK', { cart_id: id, command }); return command;
  },
  async createSession(cart_id) {
    await delay(); const c = cartOr404(cart_id);
    must(c.connection_status === 'ONLINE', 409, 'CART_OFFLINE', `Xe ${cart_id} đang OFFLINE, không thể bắt đầu phiên`);
    must(c.cart_status === 'AVAILABLE', 409, 'CART_NOT_AVAILABLE', `Xe ${cart_id} đang ${c.cart_status}, chỉ xe AVAILABLE mới bắt đầu được phiên`);
    const s = { id: seq.session++, cart_id, status: 'ACTIVE', started_at: now(), ended_at: null, total_amount: 0, note: '', items: [] };
    sessions[s.id] = s; c.cart_status = 'IN_USE'; c._offset = 0; push(cart_id); return sessionView(s);
  },
  async getSession(sid) { await delay(60); return sessionView(sessOr404(sid)); },
  async addItem(sid, { product_id, barcode, quantity = 1 }) {
    await delay(); const s = sessOr404(sid);
    must(s.status === 'ACTIVE', 409, 'SESSION_NOT_ACTIVE', `Phiên ${sid} đã kết thúc`);
    const p = products.find((x) => (product_id != null ? x.id === product_id : x.barcode === barcode));
    must(p, 404, 'NOT_FOUND', `Không tìm thấy sản phẩm: ${product_id ?? barcode}`);
    addToSession(s, p, quantity);
    carts[s.cart_id].current_weight = expected(sid) + (carts[s.cart_id]._offset || 0); // mock: cân cập nhật theo
    evaluate(s.cart_id); push(s.cart_id); return sessionView(s);
  },
  async removeItem(sid, itemId) {
    await delay(); const s = sessOr404(sid);
    must(s.status === 'ACTIVE', 409, 'SESSION_NOT_ACTIVE', `Phiên ${sid} đã kết thúc`);
    must(s.items.some((i) => i.id === itemId), 404, 'NOT_FOUND', `Không tìm thấy dòng hàng: ${itemId}`);
    s.items = s.items.filter((i) => i.id !== itemId);
    carts[s.cart_id].current_weight = expected(sid) + (carts[s.cart_id]._offset || 0);
    evaluate(s.cart_id); push(s.cart_id); return sessionView(s);
  },
  async checkout(sid) {
    await delay(300); const s = sessOr404(sid);
    must(s.status === 'ACTIVE', 409, 'SESSION_NOT_ACTIVE', `Phiên ${sid} đã kết thúc`);
    must(carts[s.cart_id].cart_status !== 'LOCKED', 409, 'CART_LOCKED', `Xe ${s.cart_id} đang bị khoá, không thể thanh toán`);
    must(s.items.length > 0, 409, 'EMPTY_SESSION', 'Giỏ hàng trống, không thể thanh toán');
    const un = activeAlertTypes(s.cart_id);
    s.total_amount = total(sid); s.status = 'COMPLETED'; s.ended_at = now();
    s.note = un.length ? `Cảnh báo chưa xử lý khi thanh toán: ${un.join(', ')}` : '';
    carts[s.cart_id].cart_status = 'AVAILABLE'; carts[s.cart_id].current_weight = 0;
    resolve(s.cart_id, 'WEIGHT_MISMATCH'); push(s.cart_id); return sessionView(s);
  },
  async cancelSession(sid) {
    await delay(); const s = sessOr404(sid);
    must(s.status === 'ACTIVE', 409, 'SESSION_NOT_ACTIVE', `Phiên ${sid} đã kết thúc`);
    s.items = []; s.status = 'COMPLETED'; s.ended_at = now(); s.total_amount = 0; s.note = 'Phiên bị huỷ';
    if (carts[s.cart_id].cart_status !== 'LOCKED') carts[s.cart_id].cart_status = 'AVAILABLE';
    resolve(s.cart_id, 'WEIGHT_MISMATCH'); push(s.cart_id); return sessionView(s);
  },
  async getAlerts(status) { await delay(); return alerts.filter((a) => !status || a.status === status); },
  async getCommands() { await delay(); return []; },
};

export function connectMockSocket(onEvent, onStatus) {
  listeners.add(onEvent);
  setTimeout(() => onStatus('open'), 50);
  return () => listeners.delete(onEvent);
}

// Cho phép chỉnh tay khi demo/E2E:  window.__mock.offline('CART_001') ...
if (typeof window !== 'undefined') {
  window.__mock = {
    offline(id) { carts[id].connection_status = 'OFFLINE'; raise(id, 'OFFLINE', 'Mất kết nối: không nhận heartbeat quá 15s'); push(id); },
    online(id) { carts[id].connection_status = 'ONLINE'; resolve(id, 'OFFLINE'); push(id); },
    battery(id, v) { carts[id].battery_percent = v; evaluate(id); push(id); },
    weightOffset(id, g) { carts[id]._offset = g; const s = activeSession(id); carts[id].current_weight = (s ? expected(s.id) : 0) + g; evaluate(id); push(id); },
  };
}
