// Trạng thái đăng nhập phía trình duyệt.
//  - staff  : token quản trị (admin/viewer) lưu trong sessionStorage (đóng tab là mất)
//  - khách  : token theo phiên mua hàng, lưu localStorage để tải lại trang vẫn tiếp tục được phiên của mình
// Token KHÔNG bao giờ nằm trong URL.
import { useSyncExternalStore } from 'react';

const K_STAFF = 'smartcart.staff';
const K_CUST = 'smartcart.customer';

const safe = {
  get(store, k) { try { return JSON.parse(window[store].getItem(k) || 'null'); } catch { return null; } },
  set(store, k, v) { try { window[store].setItem(k, JSON.stringify(v)); } catch { /* chế độ riêng tư: giữ trong bộ nhớ */ } },
  del(store, k) { try { window[store].removeItem(k); } catch { /* noop */ } },
};

let snap = {
  required: null,                         // null = chưa biết, true/false sau khi gọi /api/auth/config
  staff: safe.get('sessionStorage', K_STAFF),   // {token, role, username, exp}
  customers: safe.get('localStorage', K_CUST) || {},   // { [sid]: {token, cart_id, exp} }
};
const subs = new Set();
function commit(patch) {
  snap = { ...snap, ...patch };
  subs.forEach((f) => f());
}

const expired = (x) => !x || (x.exp && x.exp * 1000 < Date.now());
if (expired(snap.staff)) snap = { ...snap, staff: null };
snap = { ...snap, customers: Object.fromEntries(Object.entries(snap.customers).filter(([, v]) => !expired(v))) };

export const authStore = {
  get: () => snap,
  subscribe: (f) => { subs.add(f); return () => subs.delete(f); },
  setRequired: (required) => commit({ required }),
  setStaff(r) {
    const staff = r ? { token: r.token, role: r.role, username: r.username, exp: Math.floor(Date.now() / 1000) + (r.expires_in || 3600) } : null;
    if (staff) safe.set('sessionStorage', K_STAFF, staff); else safe.del('sessionStorage', K_STAFF);
    commit({ staff });
  },
  addCustomer(sess) {
    if (!sess?.token) return;
    const customers = { ...snap.customers, [sess.id]: { token: sess.token, cart_id: sess.cart_id, exp: Math.floor(Date.now() / 1000) + (sess.token_expires_in || 3600) } };
    safe.set('localStorage', K_CUST, customers);
    commit({ customers });
  },
  dropCustomer(sid) {
    const { [sid]: _gone, ...customers } = snap.customers;
    safe.set('localStorage', K_CUST, customers);
    commit({ customers });
  },
};

export const useAuth = () => useSyncExternalStore(authStore.subscribe, authStore.get);

export const isStaff = (a) => Boolean(a.staff);
export const canWrite = (a) => !a.required || a.staff?.role === 'admin';
export const hasSessionAccess = (a, sid) => Boolean(a.staff) || Boolean(a.customers[sid]);

// token cần gửi cho một đường dẫn REST (ưu tiên staff; không thì token của đúng phiên/xe)
export function tokenFor(path) {
  if (snap.staff) return snap.staff.token;
  let m = path.match(/^\/sessions\/(\d+)/);
  if (m) return snap.customers[m[1]]?.token || null;
  m = path.match(/^\/carts\/([^/?]+)\/session/);
  if (m) return Object.values(snap.customers).find((c) => c.cart_id === m[1])?.token || null;
  return null;
}

// token cho WebSocket: staff, hoặc token phiên khách đang xem (/customer/cart/:sid)
export function wsToken() {
  if (snap.staff) return snap.staff.token;
  const m = location.pathname.match(/^\/customer\/cart\/(\d+)/);
  return (m && snap.customers[m[1]]?.token) || null;
}
