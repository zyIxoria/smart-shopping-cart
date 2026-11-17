import { useRef, useState } from 'react';
import { COUNTERS, MAP_H, MAP_W, SHELVES, WAYPOINTS, ZONES } from './floorPlan.js';

const ZONE_STYLE = {
  grocery: { fill: '#f0fdf4', stroke: '#86efac', shelfFill: '#dcfce7', shelfStroke: '#22c55e', text: '#166534' },
  beverage: { fill: '#eff6ff', stroke: '#93c5fd', shelfFill: '#dbeafe', shelfStroke: '#3b82f6', text: '#1e40af' },
  household: { fill: '#fffbeb', stroke: '#fcd34d', shelfFill: '#fef3c7', shelfStroke: '#f59e0b', text: '#92400e' },
  personal: { fill: '#f5f3ff', stroke: '#c4b5fd', shelfFill: '#ede9fe', shelfStroke: '#8b5cf6', text: '#5b21b6' },
  checkout: { fill: '#f0f9ff', stroke: '#7dd3fc', shelfFill: '#e0f2fe', shelfStroke: '#0284c7', text: '#0369a1' },
  neutral: { fill: '#f8fafc', stroke: '#cbd5e1', shelfFill: '#e2e8f0', shelfStroke: '#94a3b8', text: '#334155' },
};

export function cartVisualState(cart, simCart, justCheckedOut) {
  const conn = cart?.connection_status || (simCart?.connected ? 'ONLINE' : 'OFFLINE');
  const status = cart?.cart_status || simCart?.cart_status || 'AVAILABLE';
  const alerts = cart?.active_alerts || [];
  const queueLen = simCart?.offline_queue_len || 0;

  if (conn !== 'ONLINE') return { key: 'offline', label: 'Offline', color: '#64748b', bg: '#f1f5f9', ring: '#94a3b8' };
  if (status === 'LOCKED') return { key: 'locked', label: 'Đã khoá', color: '#dc2626', bg: '#fef2f2', ring: '#ef4444' };
  if (justCheckedOut && status === 'AVAILABLE') return { key: 'checkout', label: 'Vừa Checkout', color: '#0284c7', bg: '#e0f2fe', ring: '#38bdf8' };
  if (alerts.length > 0 || queueLen > 0) return { key: 'warning', label: 'Cảnh báo', color: '#d97706', bg: '#fffbeb', ring: '#f59e0b' };
  return { key: 'online', label: status === 'IN_USE' ? 'Đang mua' : 'Sẵn sàng', color: '#059669', bg: '#ecfdf5', ring: '#10b981' };
}

function CartGlyph({ x, y, cartId, battery, weightG, itemsCount, visual, selected, onSelect }) {
  const wLabel = `${Math.round(weightG ?? 0)}g`;
  const bLabel = battery != null ? `${Math.round(battery)}%` : '—';
  return (
    <g
      transform={`translate(${x}, ${y})`}
      onClick={(e) => { e.stopPropagation(); onSelect(cartId); }}
      style={{ cursor: 'pointer' }}
      data-testid={`map-cart-${cartId}`}
      role="button"
      aria-label={`Chọn xe ${cartId}`}
    >
      {/* Vòng chọn / vòng trạng thái */}
      {selected && (
        <circle r="27" fill="none" stroke="#0ea5e9" strokeWidth="2.5" strokeDasharray="4 3" />
      )}
      {visual.key === 'warning' && (
        <circle r="23" fill="none" stroke={visual.ring} strokeWidth="2" opacity="0.7" />
      )}
      <circle r="19" fill={visual.bg} stroke={visual.color} strokeWidth={selected ? '3' : '2.2'} />

      {/* Biểu tượng xe đẩy SVG sắc nét */}
      <g transform="translate(-10, -9)" fill="none" stroke={visual.color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M1 1h3l2.2 9.5a1.5 1.5 0 0 0 1.5 1.2h8.5a1.5 1.5 0 0 0 1.4-1.1L19 4.5H5" />
        <circle cx="8" cy="15.5" r="1.4" fill={visual.color} />
        <circle cx="15.5" cy="15.5" r="1.4" fill={visual.color} />
      </g>

      {/* Nhãn thông số trực tiếp */}
      <g transform="translate(0, 24)" style={{ pointerEvents: 'none' }}>
        <rect x="-42" y="0" width="84" height="28" rx="5" fill="#0f172a" fillOpacity="0.90" stroke={selected ? '#38bdf8' : '#334155'} strokeWidth="1" />
        <text x="0" y="12" textAnchor="middle" fill="#ffffff" fontSize="9" fontWeight="700" fontFamily="ui-monospace, monospace">
          {cartId}
        </text>
        <text x="0" y="23" textAnchor="middle" fill="#cbd5e1" fontSize="7.8" fontFamily="system-ui, sans-serif">
          {`${bLabel} · ${wLabel} · ${itemsCount} món`}
        </text>
      </g>
    </g>
  );
}

export default function SupermarketMap({
  cartsList,
  positions,
  routes,
  selectedId,
  onSelectCart,
  onSelectZone,
  checkoutFlags,
}) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragRef = useRef(null);

  const handleWheel = (e) => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.12 : -0.12;
    setZoom((z) => Math.max(0.75, Math.min(2.0, Number((z + delta).toFixed(2)))));
  };

  const onMouseDown = (e) => {
    if (e.button !== 0) return;
    dragRef.current = { sx: e.clientX, sy: e.clientY, px: pan.x, py: pan.y };
  };
  const onMouseMove = (e) => {
    if (!dragRef.current) return;
    const dx = e.clientX - dragRef.current.sx;
    const dy = e.clientY - dragRef.current.sy;
    setPan({ x: dragRef.current.px + dx, y: dragRef.current.py + dy });
  };
  const onMouseUp = () => { dragRef.current = null; };

  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  return (
    <div className="sim2d-map-wrap">
      {/* Thanh công cụ bản đồ */}
      <div className="sim2d-map-toolbar">
        <div className="sim2d-legend">
          <span className="leg-item"><i className="leg-dot" style={{ background: '#059669' }} />Online</span>
          <span className="leg-item"><i className="leg-dot" style={{ background: '#d97706' }} />Cảnh báo</span>
          <span className="leg-item"><i className="leg-dot" style={{ background: '#dc2626' }} />Khoá</span>
          <span className="leg-item"><i className="leg-dot" style={{ background: '#64748b' }} />Offline</span>
          <span className="leg-item"><i className="leg-dot" style={{ background: '#0284c7' }} />Vừa Checkout</span>
        </div>
        <div className="sim2d-zoom-ctrls">
          <button type="button" className="btn btn-small" onClick={() => setZoom((z) => Math.max(0.75, Number((z - 0.15).toFixed(2))))} aria-label="Thu nhỏ">−</button>
          <span className="mono small" style={{ minWidth: '44px', textAlign: 'center' }}>{Math.round(zoom * 100)}%</span>
          <button type="button" className="btn btn-small" onClick={() => setZoom((z) => Math.min(2.0, Number((z + 0.15).toFixed(2))))} aria-label="Phóng to">+</button>
          <button type="button" className="btn btn-small" onClick={resetView}>Reset</button>
        </div>
      </div>

      {/* Khung SVG 2D Digital Twin */}
      <div
        className="sim2d-svg-viewport"
        onWheel={handleWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        data-testid="supermarket-2d-map"
      >
        <svg
          viewBox={`0 0 ${MAP_W} ${MAP_H}`}
          className="sim2d-svg"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
        >
          <defs>
            <pattern id="floorGrid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e2e8f0" strokeWidth="0.8" />
            </pattern>
          </defs>

          {/* Nền sàn siêu thị */}
          <rect x="0" y="0" width={MAP_W} height={MAP_H} fill="#f8fafc" />
          <rect x="20" y="20" width={MAP_W - 40} height={MAP_H - 40} rx="10" fill="url(#floorGrid)" stroke="#0f172a" strokeWidth="2.5" />

          {/* Nhãn các trục hành lang */}
          <text x="500" y="39" textAnchor="middle" fill="#64748b" fontSize="10" fontWeight="600" letterSpacing="1.2">
            HÀNH LANG PHÍA BẮC · LỐI ĐI CHÍNH
          </text>
          <text x="500" y="302" textAnchor="middle" fill="#64748b" fontSize="10" fontWeight="600" letterSpacing="1.2">
            HÀNH LANG TRUNG TÂM · ĐIỂM DỪNG KỆ HÀNG
          </text>

          {/* Các khu vực (Click vào khu vực để điều khiển xe đang chọn di chuyển tới) */}
          {ZONES.map((z) => {
            const st = ZONE_STYLE[z.tone] || ZONE_STYLE.neutral;
            return (
              <g
                key={z.id}
                onClick={() => onSelectZone(z.id)}
                style={{ cursor: 'pointer' }}
                data-testid={`map-zone-${z.id}`}
              >
                <rect x={z.x} y={z.y} width={z.w} height={z.h} rx="8" fill={st.fill} stroke={st.stroke} strokeWidth="1.5" strokeDasharray={z.id === 'entrance' || z.id === 'exit' ? '5 4' : 'none'} />
                <text x={z.x + z.w / 2} y={z.y + (z.id === 'entrance' || z.id === 'exit' ? 22 : 16)} textAnchor="middle" fill={st.text} fontSize="11" fontWeight="700">
                  {z.label}
                </text>
                <text x={z.x + z.w / 2} y={z.y + (z.id === 'entrance' || z.id === 'exit' ? 35 : z.h - 7)} textAnchor="middle" fill={st.text} fontSize="8.5" opacity="0.78">
                  {z.en}
                </text>
              </g>
            );
          })}

          {/* Kệ hàng chi tiết */}
          {SHELVES.map((sh) => {
            const z = ZONES.find((zn) => zn.id === sh.zone);
            const st = ZONE_STYLE[z?.tone || 'neutral'];
            return (
              <g key={sh.id} style={{ pointerEvents: 'none' }}>
                <rect x={sh.x} y={sh.y} width={sh.w} height={sh.h} rx="5" fill={st.shelfFill} stroke={st.shelfStroke} strokeWidth="1.4" />
                <text x={sh.x + sh.w / 2} y={sh.y + sh.h / 2 + 4} textAnchor="middle" fill={st.text} fontSize="10" fontWeight="600">
                  {sh.label}
                </text>
              </g>
            );
          })}

          {/* Quầy thanh toán */}
          {COUNTERS.map((ct) => (
            <g key={ct.id} onClick={() => onSelectZone('checkout')} style={{ cursor: 'pointer' }}>
              <rect x={ct.x} y={ct.y} width={ct.w} height={ct.h} rx="6" fill="#e0f2fe" stroke="#0284c7" strokeWidth="1.6" />
              <rect x={ct.x + 8} y={ct.y + 12} width="16" height="30" rx="2" fill="#0369a1" opacity="0.8" />
              <text x={ct.x + 58} y={ct.y + 31} textAnchor="middle" fill="#0c4a6e" fontSize="10.5" fontWeight="700">
                {ct.label}
              </text>
            </g>
          ))}

          {/* Cửa ra vào */}
          <rect x="20" y="478" width="10" height="72" fill="#059669" />
          <text x="38" y="472" fill="#059669" fontSize="9" fontWeight="700">VÀO</text>
          <rect x="970" y="478" width="10" height="72" fill="#0284c7" />
          <text x="938" y="472" fill="#0284c7" fontSize="9" fontWeight="700">RA</text>

          {/* Tuyến đường đang di chuyển của từng xe */}
          {cartsList.map(({ cart_id }) => {
            const pos = positions[cart_id];
            const route = routes[cart_id];
            if (!pos || !route || route.length === 0) return null;
            const pts = [`${pos.x},${pos.y}`, ...route.map((wpId) => {
              const pt = WAYPOINTS[wpId];
              return pt ? `${pt.x},${pt.y}` : '';
            })].filter(Boolean).join(' ');
            const isSel = cart_id === selectedId;
            return (
              <polyline
                key={`route-${cart_id}`}
                points={pts}
                fill="none"
                stroke={isSel ? '#0ea5e9' : '#94a3b8'}
                strokeWidth={isSel ? '2.5' : '1.6'}
                strokeDasharray="6 4"
                opacity={isSel ? 0.95 : 0.6}
              />
            );
          })}

          {/* Điểm nút waypoint hành lang (hiển thị mờ để minh hoạ đồ thị định tuyến) */}
          {Object.entries(WAYPOINTS).map(([id, pt]) => (
            <circle key={id} cx={pt.x} cy={pt.y} r="2.2" fill="#94a3b8" opacity="0.45" style={{ pointerEvents: 'none' }} />
          ))}

          {/* Các xe đẩy trên bản đồ */}
          {cartsList.map(({ cart_id, backend, sim }) => {
            const pos = positions[cart_id] || { x: 100, y: 500 };
            const visual = cartVisualState(backend, sim, checkoutFlags[cart_id]);
            const battery = backend?.battery_percent ?? sim?.battery_percent;
            const weightG = backend?.current_weight ?? sim?.true_weight ?? 0;
            const itemsCount = backend?.session?.item_count ?? (sim?.basket?.reduce((s, i) => s + i.quantity, 0) || 0);
            return (
              <CartGlyph
                key={cart_id}
                x={pos.x}
                y={pos.y}
                cartId={cart_id}
                battery={battery}
                weightG={weightG}
                itemsCount={itemsCount}
                visual={visual}
                selected={cart_id === selectedId}
                onSelect={onSelectCart}
              />
            );
          })}
        </svg>
      </div>
      <div className="sim2d-map-hint muted small">
        Click vào từng khu vực trên bản đồ để điều hướng xe đang chọn di chuyển theo hành lang · Cuộn chuột để thu phóng · Kéo chuột để di chuyển góc nhìn. <em>(Toạ độ 2D là vị trí mô phỏng Digital Twin, không phải dữ liệu cảm biến thực tế.)</em>
      </div>
    </div>
  );
}
