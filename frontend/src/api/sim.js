// Client của API điều khiển Simulator (python -m simulator.main, mặc định cổng 8090).
// Địa chỉ: ?sim=http://host:port  >  VITE_SIM_URL  >  http://<host trang>:8090
const qs = new URLSearchParams(location.search);
const BASE = (qs.get('sim') || import.meta.env.VITE_SIM_URL || `http://${location.hostname}:8090`).replace(/\/$/, '');
const SIM_TOKEN = qs.get('sim_token') || (typeof localStorage !== 'undefined' && localStorage.getItem('sim_token')) || '';

async function req(method, path, body) {
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

export const simApi = {
  base: BASE,
  carts: () => req('GET', '/carts'),
  catalog: () => req('GET', '/catalog'),
  scan: (id, barcode, action = 'ADD') => req('POST', `/carts/${id}/scan`, { barcode, action }),
  battery: (id, percent) => req('POST', `/carts/${id}/battery`, { percent }),
  weightOffset: (id, grams) => req('POST', `/carts/${id}/weight_offset`, { grams }),
  connection: (id, online) => req('POST', `/carts/${id}/connection`, { online }),
};
