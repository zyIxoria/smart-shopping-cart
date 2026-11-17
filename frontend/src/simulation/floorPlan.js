// Định nghĩa bản đồ siêu thị 2D (tọa độ SVG 1000x620), vùng kệ hàng, điểm nút hành lang
// và thuật toán tìm đường BFS tránh va chạm kệ hàng.
// Lưu ý: Đây là tọa độ mô phỏng không gian 2D trên Frontend (Digital Twin), không phải dữ liệu cảm biến vật lý.

export const MAP_W = 1000;
export const MAP_H = 620;

export const ZONES = [
  { id: 'entrance', label: 'Lối vào & Bãi xe', en: 'Entrance / Cart Bay', x: 26, y: 405, w: 178, h: 195, stop: 'wp_bay', tone: 'neutral' },
  { id: 'grocery', label: 'Thực phẩm khô', en: 'Grocery', x: 250, y: 78, w: 200, h: 185, stop: 'wp_grocery', tone: 'grocery' },
  { id: 'beverage', label: 'Đồ uống & Sữa', en: 'Beverage', x: 530, y: 78, w: 200, h: 185, stop: 'wp_beverage', tone: 'beverage' },
  { id: 'household', label: 'Gia dụng', en: 'Household', x: 250, y: 340, w: 200, h: 170, stop: 'wp_household', tone: 'household' },
  { id: 'personal_care', label: 'Chăm sóc cá nhân', en: 'Personal Care', x: 530, y: 340, w: 200, h: 170, stop: 'wp_personal', tone: 'personal' },
  { id: 'checkout', label: 'Quầy thanh toán', en: 'Checkout Counters', x: 825, y: 85, w: 135, h: 280, stop: 'wp_checkout', tone: 'checkout' },
  { id: 'exit', label: 'Lối ra', en: 'Exit Gate', x: 825, y: 445, w: 135, h: 140, stop: 'wp_exit', tone: 'neutral' },
];

// Các khối kệ vật lý hiển thị bên trong từng khu vực
export const SHELVES = [
  // Grocery (2 dãy kệ)
  { id: 'G1', zone: 'grocery', label: 'Kệ A1 · Mì & Bánh kẹo', x: 265, y: 95, w: 170, h: 66 },
  { id: 'G2', zone: 'grocery', label: 'Kệ A2 · Gia vị & Đồ khô', x: 265, y: 180, w: 170, h: 66 },
  // Beverage (2 dãy kệ)
  { id: 'B1', zone: 'beverage', label: 'Kệ B1 · Nước giải khát', x: 545, y: 95, w: 170, h: 66 },
  { id: 'B2', zone: 'beverage', label: 'Kệ B2 · Sữa & Trà đóng chai', x: 545, y: 180, w: 170, h: 66 },
  // Household (2 dãy kệ)
  { id: 'H1', zone: 'household', label: 'Kệ C1 · Giặt tẩy & Vệ sinh', x: 265, y: 356, w: 170, h: 62 },
  { id: 'H2', zone: 'household', label: 'Kệ C2 · Đồ dùng nhà bếp', x: 265, y: 434, w: 170, h: 62 },
  // Personal Care (2 dãy kệ)
  { id: 'P1', zone: 'personal_care', label: 'Kệ D1 · Dầu gội & Sữa tắm', x: 545, y: 356, w: 170, h: 62 },
  { id: 'P2', zone: 'personal_care', label: 'Kệ D2 · Chăm sóc răng miệng', x: 545, y: 434, w: 170, h: 62 },
];

export const COUNTERS = [
  { id: 'Q1', label: 'Quầy 1', x: 845, y: 105, w: 98, h: 54 },
  { id: 'Q2', label: 'Quầy 2', x: 845, y: 195, w: 98, h: 54 },
  { id: 'Q3', label: 'Quầy 3', x: 845, y: 285, w: 98, h: 54 },
];

// Đồ thị điểm nút hành lang (tuyệt đối không xuyên qua kệ hàng)
export const WAYPOINTS = {
  wp_bay:       { x: 112, y: 505, zone: 'entrance' },
  wp_sw:        { x: 215, y: 545, zone: 'entrance' },
  wp_nw:        { x: 215, y: 52,  zone: 'grocery' },
  wp_wm:        { x: 215, y: 298, zone: 'grocery' },
  wp_grocery_t: { x: 350, y: 52,  zone: 'grocery' },
  wp_grocery:   { x: 350, y: 298, zone: 'grocery' },
  wp_household: { x: 350, y: 545, zone: 'household' },
  wp_cm:        { x: 490, y: 298, zone: 'grocery' },
  wp_ct:        { x: 490, y: 52,  zone: 'beverage' },
  wp_cb:        { x: 490, y: 545, zone: 'household' },
  wp_bev_t:     { x: 630, y: 52,  zone: 'beverage' },
  wp_beverage:  { x: 630, y: 298, zone: 'beverage' },
  wp_personal:  { x: 630, y: 545, zone: 'personal_care' },
  wp_et:        { x: 780, y: 52,  zone: 'checkout' },
  wp_checkout:  { x: 780, y: 222, zone: 'checkout' },
  wp_em:        { x: 780, y: 298, zone: 'checkout' },
  wp_exit:      { x: 780, y: 510, zone: 'exit' },
  wp_se:        { x: 780, y: 545, zone: 'exit' },
};

const EDGES = [
  ['wp_bay', 'wp_sw'],
  ['wp_sw', 'wp_wm'],
  ['wp_wm', 'wp_nw'],
  ['wp_nw', 'wp_grocery_t'],
  ['wp_grocery_t', 'wp_ct'],
  ['wp_ct', 'wp_bev_t'],
  ['wp_bev_t', 'wp_et'],
  ['wp_wm', 'wp_grocery'],
  ['wp_grocery', 'wp_cm'],
  ['wp_cm', 'wp_beverage'],
  ['wp_beverage', 'wp_em'],
  ['wp_sw', 'wp_household'],
  ['wp_household', 'wp_cb'],
  ['wp_cb', 'wp_personal'],
  ['wp_personal', 'wp_se'],
  ['wp_ct', 'wp_cm'],
  ['wp_cm', 'wp_cb'],
  ['wp_et', 'wp_checkout'],
  ['wp_checkout', 'wp_em'],
  ['wp_em', 'wp_exit'],
  ['wp_exit', 'wp_se'],
];

const ADJ = {};
for (const k of Object.keys(WAYPOINTS)) ADJ[k] = [];
for (const [a, b] of EDGES) {
  ADJ[a].push(b);
  ADJ[b].push(a);
}

// Vị trí đỗ mặc định cho nhiều xe ở khu vực Lối vào (không chồng đè nhãn/nút bấm)
export function initialSlotForIndex(idx) {
  const slots = [
    { x: 74, y: 465, wp: 'wp_bay', zone: 'entrance' },
    { x: 162, y: 465, wp: 'wp_bay', zone: 'entrance' },
    { x: 118, y: 542, wp: 'wp_bay', zone: 'entrance' },
    { x: 162, y: 542, wp: 'wp_bay', zone: 'entrance' },
  ];
  return slots[idx % slots.length];
}

export function nearestWaypoint(x, y) {
  let best = 'wp_bay';
  let bestD = Infinity;
  for (const [id, pt] of Object.entries(WAYPOINTS)) {
    const d = (pt.x - x) ** 2 + (pt.y - y) ** 2;
    if (d < bestD) { bestD = d; best = id; }
  }
  return best;
}

export function findPathWaypoints(fromWp, toWp) {
  if (fromWp === toWp) return [toWp];
  const q = [[fromWp]];
  const seen = new Set([fromWp]);
  while (q.length > 0) {
    const path = q.shift();
    const cur = path[path.length - 1];
    for (const nxt of (ADJ[cur] || [])) {
      if (seen.has(nxt)) continue;
      const nextPath = [...path, nxt];
      if (nxt === toWp) return nextPath;
      seen.add(nxt);
      q.push(nextPath);
    }
  }
  return [toWp];
}

export function zoneById(zoneId) {
  return ZONES.find((z) => z.id === zoneId) || ZONES[0];
}
