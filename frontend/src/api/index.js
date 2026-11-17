import { realApi, connectSocket } from './client.js';
import { mockApi, connectMockSocket } from './mock.js';

const qs = new URLSearchParams(location.search);
export const USE_MOCK =
  import.meta.env.VITE_USE_MOCK === 'true' || qs.get('mock') === '1' || sessionStorageGet('smartcart.mock') === '1';

function sessionStorageGet(k) {
  try { return sessionStorage.getItem(k); } catch { return null; }
}
if (qs.get('mock') === '1') { try { sessionStorage.setItem('smartcart.mock', '1'); } catch { /* noop */ } }
if (qs.get('mock') === '0') { try { sessionStorage.removeItem('smartcart.mock'); } catch { /* noop */ } }

export const api = USE_MOCK ? mockApi : realApi;
export const connectEvents = USE_MOCK ? connectMockSocket : connectSocket;
export { ApiError } from './client.js';
