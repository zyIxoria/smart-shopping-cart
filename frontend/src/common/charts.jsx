import { timeOnly } from './format.js';

// Biểu đồ đường SVG tối giản (không phụ thuộc thư viện).
export function LineChart({ title, points, unit, min, max, minSpan = 10, color = 'var(--primary)', format = (v) => v.toFixed(0), testid }) {
  const W = 560; const H = 160; const P = { l: 44, r: 10, t: 12, b: 24 };
  if (!points || points.length < 2) {
    return <div className="chart chart-empty" data-testid={testid}><b>{title}</b><p>Chưa đủ dữ liệu</p></div>;
  }
  const ys = points.map((p) => p.y);
  const lo = min ?? Math.min(...ys);
  const top = Math.max(max ?? Math.max(...ys), lo + minSpan);
  const x = (i) => P.l + (i / (points.length - 1)) * (W - P.l - P.r);
  const y = (v) => P.t + (1 - (v - lo) / (top - lo)) * (H - P.t - P.b);
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.y).toFixed(1)}`).join(' ');
  const last = points[points.length - 1];
  const ticks = [lo, (lo + top) / 2, top];
  return (
    <figure className="chart" data-testid={testid}>
      <figcaption><b>{title}</b><span>{format(last.y)} {unit}</span></figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}: hiện tại ${format(last.y)} ${unit}`}>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} className="grid" />
            <text x={P.l - 6} y={y(t) + 4} textAnchor="end" className="axis">{format(t)}</text>
          </g>
        ))}
        <path d={`${d} L${x(points.length - 1)},${H - P.b} L${x(0)},${H - P.b} Z`} fill={color} opacity="0.08" />
        <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
        <circle cx={x(points.length - 1)} cy={y(last.y)} r="3.5" fill={color} />
        <text x={P.l} y={H - 6} className="axis">{timeOnly(points[0].t)}</text>
        <text x={W - P.r} y={H - 6} textAnchor="end" className="axis">{timeOnly(last.t)}</text>
      </svg>
    </figure>
  );
}
