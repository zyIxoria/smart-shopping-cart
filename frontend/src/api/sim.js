// Client của API điều khiển Simulator (python -m simulator.main, mặc định cổng 8090).
// Địa chỉ: ?sim=http://host:port  >  VITE_SIM_URL  >  proxy cùng origin (/api/sim/...) khi nhúng trong /admin,
// hoặc http://<host>:8090 cho trang /simulator độc lập.
import { tokenFor } from './auth.js';

const qs = new URLSearchParams(location.search);
const EXPLICIT = (qs.get('sim') || import.meta.env.VITE_SIM_URL || '').replace(/\/$/, '');
const BASE = EXPLICIT || `http://${location.hostname}:8090`;
const SIM_TOKEN = qs.get('sim_token') || (typeof localStorage !== 'undefined' && localStorage.getItem('sim_token')) || '';

async function reqDirect(method, path, body) {
  let res;
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (SIM_TOKEN) headers.Authorization = `Bearer ${SIM_TOKEN}`;
  try {
    res = await fetch(`${BASE}/sim${path}`, {
      method,
      headers: Object.keys(headers).length ? headers : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error('Không kết nối được tới Simulator');
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.error || `Lỗi ${res.status}`);
  return data;
}

async function reqProxy(method, path, body) {
  let res;
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const token = tokenFor('/carts');
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    res = await fetch(`/api/sim${path}`, {
      method,
      headers: Object.keys(headers).length ? headers : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error('Không kết nối được tới Backend Simulator Proxy');
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.error?.message || data?.error || `Lỗi ${res.status}`);
  return data;
}

const act = (method, path, body) => (EXPLICIT ? reqDirect(method, path, body) : reqProxy(method, path, body));

export const simApi = {
  base: EXPLICIT || '/api/sim (Simulator :8090)',
  hasExplicitUrl: Boolean(EXPLICIT),
  carts: () => reqDirect('GET', '/carts'),
  catalog: () => reqDirect('GET', '/catalog'),
  embeddedState: async () => {
    if (EXPLICIT) {
      const [carts, catalog] = await Promise.all([reqDirect('GET', '/carts'), reqDirect('GET', '/catalog')]);
      return { available: true, carts, catalog };
    }
    return reqProxy('GET', '/status');
  },
  scan: (id, barcode, action = 'ADD') => act('POST', `/carts/${id}/scan`, { barcode, action }),
  battery: (id, percent) => act('POST', `/carts/${id}/battery`, { percent }),
  weightOffset: (id, grams) => act('POST', `/carts/${id}/weight_offset`, { grams }),
  connection: (id, online) => act('POST', `/carts/${id}/connection`, { online }),
};
