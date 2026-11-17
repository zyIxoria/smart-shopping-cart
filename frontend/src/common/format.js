export const vnd = (n) => `${Math.round(n ?? 0).toLocaleString('vi-VN')} ₫`;

// Nội bộ lưu gram; hiển thị kg khi >= 1000 g.
export function weight(g) {
  if (g == null || Number.isNaN(g)) return '—';
  if (Math.abs(g) >= 1000) return `${(g / 1000).toLocaleString('vi-VN', { maximumFractionDigits: 2 })} kg`;
  return `${Math.round(g).toLocaleString('vi-VN')} g`;
}

export const CART_STATUS = {
  AVAILABLE: { label: 'Sẵn sàng', tone: 'ok' },
  IN_USE: { label: 'Đang sử dụng', tone: 'info' },
  LOCKED: { label: 'Đã khoá', tone: 'danger' },
};
export const CONN = {
  ONLINE: { label: 'Online', tone: 'ok' },
  OFFLINE: { label: 'Offline', tone: 'muted' },
};
export const ALERT_TYPE = {
  LOW_BATTERY: { label: 'Pin yếu', tone: 'warn', icon: '🔋' },
  WEIGHT_MISMATCH: { label: 'Lệch cân', tone: 'danger', icon: '⚖️' },
  OFFLINE: { label: 'Mất kết nối', tone: 'muted', icon: '📡' },
};
export const ALERT_STATUS = {
  ACTIVE: { label: 'Đang xảy ra', tone: 'danger' },
  RESOLVED: { label: 'Đã xử lý', tone: 'ok' },
};

export function parseTime(s) { return s ? new Date(s).getTime() : null; }

export function ago(s, nowMs = Date.now()) {
  const t = parseTime(s);
  if (t == null) return 'chưa có';
  const d = Math.max(0, Math.round((nowMs - t) / 1000));
  if (d < 5) return 'vừa xong';
  if (d < 60) return `${d} giây trước`;
  if (d < 3600) return `${Math.floor(d / 60)} phút trước`;
  if (d < 86400) return `${Math.floor(d / 3600)} giờ trước`;
  return `${Math.floor(d / 86400)} ngày trước`;
}

export const dateTime = (s) => (s ? new Date(s).toLocaleString('vi-VN', { hour12: false }) : '—');
export const timeOnly = (s) => (s ? new Date(s).toLocaleTimeString('vi-VN', { hour12: false }) : '—');
