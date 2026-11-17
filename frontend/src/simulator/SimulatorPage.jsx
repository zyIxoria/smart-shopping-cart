import { useCallback, useEffect, useState } from 'react';
import { simApi } from '../api/sim.js';
import { ConnBadge, Empty, Loading, StatusBadge, Toasts, WsIndicator } from '../common/ui.jsx';
import { weight } from '../common/format.js';
import { Link } from '../router.jsx';
import { useStore } from '../state/store.jsx';
import SupermarketSimulation from '../simulation/SupermarketSimulation.jsx';

const RESULT = {
  sent: ['ok', 'Đã gửi lệnh quét lên hệ thống (MQTT)'],
  queued: ['warn', 'Xe mất mạng – đã lưu vào Offline Queue, sẽ tự gửi bù khi nối lại'],
  offline: ['warn', 'Xe đang mất mạng – gói tin quét bị mất (QoS 0)'],
  locked: ['warn', 'Xe đang bị khoá – máy quét bỏ qua'],
  no_session: ['warn', 'Xe chưa có phiên mua hàng – máy quét bỏ qua'],
  not_in_basket: ['warn', 'Món này không có trong giỏ vật lý'],
};

function Lcd({ c }) {
  const qLine = c.offline_queue_len > 0 ? `\nQUEUE      : ${c.offline_queue_len} cho gui` : '';
  return (
    <pre className="lcd" data-testid={`lcd-${c.cart_id}`} aria-label="Màn hình thiết bị">
      {`${c.cart_id}\nTRANG THAI : ${c.cart_status}\nCAN        : ${Math.round(c.true_weight)} g\nPIN        : ${Math.round(c.battery_percent)} %\nPHIEN      : ${c.session_id ?? '-'}\nMQTT       : ${c.connected ? 'CONNECTED' : 'OFFLINE'}${qLine}`}
    </pre>
  );
}

function Device({ c, catalog, backend, onAct }) {
  const [barcode, setBarcode] = useState('');
  const [pct, setPct] = useState(null);
  const [note, setNote] = useState(null);
  const bc = barcode || catalog[0]?.barcode || '';
  const id = c.cart_id;

  const run = async (fn, show) => {
    try {
      const r = await fn();
      if (show && r.result) setNote(RESULT[r.result] || ['warn', r.result]);
      onAct();
    } catch (e) { setNote(['error', e.message]); }
  };

  return (
    <article className={`card device ${c.connected ? '' : 'device-off'}`} data-testid={`device-${id}`}>
      <header className="device-head">
        <div>
          <h3>{id}</h3>
          <span className="led-row"><i className={`led ${c.connected ? 'led-on' : 'led-off'}`} data-testid={`led-${id}`} />{c.connected ? 'Đang kết nối MQTT' : 'Mất kết nối MQTT'}</span>
        </div>
        <div className="backend-view" title="Trạng thái Backend ghi nhận cho xe này" data-testid={`backend-view-${id}`}>
          <span className="muted small">Hệ thống thấy</span>
          {backend ? <><ConnBadge status={backend.connection_status} /><StatusBadge status={backend.cart_status} /></> : <span className="muted small">chưa có</span>}
        </div>
      </header>

      <Lcd c={c} />

      <section className="dev-section">
        <h4>Máy quét mã vạch</h4>
        <select value={bc} onChange={(e) => setBarcode(e.target.value)} aria-label={`Sản phẩm cho ${id}`} data-testid={`product-${id}`}>
          {catalog.map((p) => <option key={p.barcode} value={p.barcode}>{p.name} · {Math.round(p.unit_weight)} g</option>)}
        </select>
        <div className="btn-row">
          <button className="btn btn-primary" onClick={() => run(() => simApi.scan(id, bc, 'ADD'), true)} data-testid={`scan-add-${id}`}>Quét · bỏ vào giỏ</button>
          <button className="btn" onClick={() => run(() => simApi.scan(id, bc, 'REMOVE'), true)} data-testid={`scan-remove-${id}`}>Lấy ra</button>
          <button className="btn" onClick={() => run(() => simApi.scan(id, '0000000000000', 'ADD'), true)} data-testid={`scan-unknown-${id}`}>Quét mã lạ</button>
        </div>
        {note && <p className={`sim-note note-${note[0]}`} data-testid={`note-${id}`}>{note[1]}</p>}
      </section>

      <section className="dev-section">
        <h4>Cảm biến cân · {weight(c.true_weight)}</h4>
        <div className="btn-row">
          <button className="btn" onClick={() => run(() => simApi.weightOffset(id, c.weight_offset + 250))} data-testid={`weight-add-${id}`}>+250 g vật lạ</button>
          <button className="btn" disabled={!c.weight_offset} onClick={() => run(() => simApi.weightOffset(id, 0))} data-testid={`weight-fix-${id}`}>Bỏ vật lạ</button>
        </div>
        {c.weight_offset !== 0 && <p className="sim-note note-warn">Đang lệch {c.weight_offset > 0 ? '+' : ''}{c.weight_offset} g so với hàng đã quét</p>}
        <ul className="plain-list basket" data-testid={`basket-${id}`}>
          {c.basket.length === 0 ? <li className="muted small">Giỏ vật lý trống</li> : c.basket.map((b) => <li key={b.barcode}>{b.name} <span className="muted">× {b.quantity}</span></li>)}
        </ul>
      </section>

      <section className="dev-section">
        <h4>Pin · {Math.round(pct ?? c.battery_percent)}%</h4>
        <input type="range" min="0" max="100" value={pct ?? Math.round(c.battery_percent)} aria-label={`Pin ${id}`} data-testid={`battery-${id}`}
          onChange={(e) => setPct(Number(e.target.value))}
          onPointerUp={() => pct != null && run(() => simApi.battery(id, pct)).then(() => setPct(null))}
          onKeyUp={() => pct != null && run(() => simApi.battery(id, pct)).then(() => setPct(null))} />
        <div className="btn-row">
          <button className="btn" onClick={() => run(() => simApi.battery(id, 15))} data-testid={`battery-low-${id}`}>Pin yếu 15%</button>
          <button className="btn" onClick={() => run(() => simApi.battery(id, 100))} data-testid={`battery-full-${id}`}>Sạc đầy</button>
        </div>
      </section>

      <section className="dev-section">
        <h4>Mạng</h4>
        <button className={`btn btn-block ${c.connected ? 'btn-danger' : 'btn-primary'}`} onClick={() => run(() => simApi.connection(id, !c.connected))} data-testid={`conn-${id}`}>
          {c.connected ? '📡 Ngắt kết nối (mô phỏng mất mạng)' : '📡 Kết nối lại'}
        </button>
      </section>

      <footer className="dev-foot">
        <div className="counters" data-testid={`sent-${id}`}>
          <span>heartbeat <b>{c.sent.heartbeat}</b></span><span>telemetry <b>{c.sent.telemetry}</b></span>
          <span>scan <b>{c.sent.scan}</b></span><span>ack <b>{c.sent.ack}</b></span>
        </div>
        <pre className="devlog" data-testid={`log-${id}`}>{c.log.slice(-5).join('\n') || '(chưa có nhật ký)'}</pre>
      </footer>
    </article>
  );
}

export default function SimulatorPage() {
  const { state } = useStore();
  const [carts, setCarts] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [error, setError] = useState(null);

  const poll = useCallback(async () => {
    try { setCarts(await simApi.carts()); setError(null); } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => {
    simApi.catalog().then(setCatalog).catch(() => {});
    poll();
    const t = setInterval(poll, 800);
    return () => clearInterval(t);
  }, [poll]);

  useEffect(() => { if (error) simApi.catalog().then(setCatalog).catch(() => {}); }, [error]);

  return (
    <div className="shell simulator">
      <header className="topbar">
        <Link to="/" className="brand"><span className="logo">🛒</span> Smart Cart <span className="tag">Simulator & Digital Twin</span></Link>
        <nav className="nav" aria-label="Điều hướng mô phỏng">
          <Link to="/simulation" className="nav-link" data-testid="nav-to-simulation">🎮 Siêu thị 3D Digital Twin</Link>
          <a href="#sim2d-section" className="nav-link on">Không gian 3D</a>
          <a href="#hardware-section" className="nav-link">Thiết bị phần cứng</a>
        </nav>
        <div className="topbar-right">
          <WsIndicator />
          <Link to="/simulation" className="btn btn-primary btn-small" style={{ marginRight: 6 }}>🎮 Mở Siêu thị 3D</Link>
          <Link to="/admin" className="link-muted">Quản trị →</Link>
          <Link to="/customer" className="link-muted">Khách hàng →</Link>
        </div>
      </header>
      <main className="container wide">
        <div className="card" style={{ marginBottom: 20, background: 'linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 100%)', border: '1px solid #bbf7d0', padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h3 style={{ margin: 0, color: '#166534', fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>🛒</span> Mô hình Siêu thị 3D Interactive Digital Twin
            </h3>
            <p style={{ margin: '4px 0 0', color: '#15803d', fontSize: '0.92rem' }}>
              Mô hình siêu thị 3D isometric tương tác: 8 dãy kệ hàng, 7 khu vực (Thực phẩm, Đồ uống, Gia dụng, Chăm sóc cá nhân, Quầy thanh toán), xe di chuyển realtime và kịch bản IoT.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Link to="/simulation" className="btn btn-primary btn-small" data-testid="btn-open-simulation-page">Xem trang 3D toàn màn hình →</Link>
          </div>
        </div>

        <section id="sim2d-section" style={{ marginBottom: 32 }}>
          <SupermarketSimulation />
        </section>

        <section id="hardware-section" style={{ borderTop: '2px dashed var(--border)', paddingTop: 24, marginTop: 12 }}>
          <div className="page-head">
            <div>
              <h2 className="page-title" style={{ fontSize: '1.25rem', margin: 0 }}>Mô phỏng Thiết bị IoT trên xe đẩy (Màn hình LCD / Cân / Pin)</h2>
              <p className="muted lead" style={{ marginTop: 4, marginBottom: 16 }}>
                Mỗi thẻ là một xe giả lập (thay cho ESP32 + máy quét + cân + pin). Thao tác ở đây được gửi lên hệ thống qua MQTT giống phần cứng thật; mở <Link to="/customer">giao diện khách</Link> hoặc <Link to="/admin">quản trị</Link> ở tab khác để xem kết quả theo thời gian thực.
              </p>
            </div>
          </div>
          {error && (
            <div className="banner banner-danger" role="alert" data-testid="sim-error">
              <span>⚠️ {error} ({simApi.base}). Hãy chạy <code>python -m simulator.main</code> (hoặc <code>scripts/run_local.sh</code>).</span>
              <button className="btn btn-small" onClick={poll}>Thử lại</button>
            </div>
          )}
          {!carts ? (error ? <Empty icon="🔌" title="Chưa kết nối được Simulator" hint="Simulator chạy tách riêng với Backend." /> : <Loading text="Đang kết nối Simulator…" />) : (
            <div className="grid device-grid" data-testid="device-grid">
              {carts.map((c) => <Device key={c.cart_id} c={c} catalog={catalog} backend={state.carts[c.cart_id]} onAct={poll} />)}
            </div>
          )}
        </section>
      </main>
      <Toasts scope="admin" />
    </div>
  );
}
