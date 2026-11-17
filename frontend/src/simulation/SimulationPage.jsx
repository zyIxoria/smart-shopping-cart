import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/index.js';
import { canWrite, useAuth } from '../api/auth.js';
import { simApi } from '../api/sim.js';
import { ago, ALERT_TYPE, timeOnly, vnd, weight } from '../common/format.js';
import { Battery, ConnBadge, ErrorBanner, StatusBadge, Toasts, WsIndicator } from '../common/ui.jsx';
import { Link } from '../router.jsx';
import { useStore } from '../state/store.jsx';
import {
  ZONES,
  WAYPOINTS,
  findPathWaypoints,
  initialSlotForIndex,
  nearestWaypoint,
  zoneById,
} from './floorPlan.js';
import SupermarketMap, { cartVisualState } from './SupermarketMap.jsx';

const POLL_SIM_MS = 1000;
const MOVE_SPEED_PX_PER_SEC = 210;

// Gợi ý khu vực kệ hàng tương ứng với tên/danh mục sản phẩm khi mô phỏng quét hàng
function inferZoneForProduct(prod) {
  const txt = `${prod?.category || ''} ${prod?.name || ''}`.toLowerCase();
  if (/(nước|sữa|trà|cà phê|bia|ngọt|coca|cola|pepsi|sprite|fanta|drink|beverage|milk|tea|water|juice)/.test(txt)) return 'beverage';
  if (/(nước giặt|rửa|tẩy|giấy|gia dụng|household|clean|detergent)/.test(txt)) return 'household';
  if (/(dầu gội|sữa tắm|kem đánh răng|cá nhân|personal|shampoo|soap)/.test(txt)) return 'personal_care';
  return 'grocery';
}

export default function SimulationPage() {
  const { state, refresh, toast } = useStore();
  const auth = useAuth();
  const writable = canWrite(auth);

  // Trạng thái Simulator (:8090) & dữ liệu phiên chi tiết
  const [simCarts, setSimCarts] = useState({});
  const [catalog, setCatalog] = useState([]);
  const [simError, setSimError] = useState(null);
  const [sessionDetail, setSessionDetail] = useState(null);
  const [busyAction, setBusyAction] = useState(null);

  // Trạng thái điều khiển 2D Digital Twin
  const [selectedId, setSelectedId] = useState('CART_001');
  const [targetZone, setTargetZone] = useState('beverage');
  const [selectedBarcode, setSelectedBarcode] = useState('');
  const [batteryInput, setBatteryInput] = useState(100);
  const [paused, setPaused] = useState(false);
  const [checkoutFlags, setCheckoutFlags] = useState({});

  // Toạ độ và tuyến đường waypoint 2D của từng xe
  const [positions, setPositions] = useState({});
  const [routes, setRoutes] = useState({});
  const positionsRef = useRef({});
  const routesRef = useRef({});
  const pausedRef = useRef(false);
  pausedRef.current = paused;

  // Hợp nhất danh sách xe từ Backend + Simulator (luôn giữ thứ tự ổn định)
  const mergedCarts = useMemo(() => {
    const ids = Array.from(new Set([...Object.keys(state.carts), ...Object.keys(simCarts)])).sort();
    return ids.map((id) => ({
      cart_id: id,
      backend: state.carts[id] || null,
      sim: simCarts[id] || null,
    }));
  }, [state.carts, simCarts]);

  // Đảm bảo luôn chọn một xe hợp lệ khi danh sách thay đổi
  useEffect(() => {
    if (mergedCarts.length > 0 && !mergedCarts.some((c) => c.cart_id === selectedId)) {
      setSelectedId(mergedCarts[0].cart_id);
    }
  }, [mergedCarts, selectedId]);

  // Khởi tạo vị trí ban đầu cho xe mới xuất hiện (tại khu vực Lối vào)
  useEffect(() => {
    let changed = false;
    const nextPos = { ...positionsRef.current };
    mergedCarts.forEach((c, idx) => {
      if (!nextPos[c.cart_id]) {
        nextPos[c.cart_id] = initialSlotForIndex(idx);
        changed = true;
      }
    });
    if (changed) {
      positionsRef.current = nextPos;
      setPositions(nextPos);
    }
  }, [mergedCarts]);

  // Poll trạng thái Simulator (:8090) định kỳ
  const loadSim = useCallback(async () => {
    try {
      const list = await simApi.carts();
      const map = {};
      list.forEach((c) => { map[c.cart_id] = c; });
      setSimCarts(map);
      setSimError(null);
    } catch (e) {
      setSimError(e.message || 'Không kết nối được Simulator (:8090)');
    }
  }, []);

  useEffect(() => {
    loadSim();
    simApi.catalog()
      .then((cats) => {
        setCatalog(cats);
        if (cats.length && !selectedBarcode) setSelectedBarcode(cats[0].barcode);
      })
      .catch(() => {
        // Fallback danh mục sản phẩm từ Backend nếu Simulator chưa bật
        api.getProducts().then((prods) => {
          setCatalog(prods);
          if (prods.length && !selectedBarcode) setSelectedBarcode(prods[0].barcode);
        }).catch(() => {});
      });
    const timer = setInterval(loadSim, POLL_SIM_MS);
    return () => clearInterval(timer);
  }, [loadSim]);

  // Theo dõi thay đổi xe đang chọn để đồng bộ thanh trượt pin và chi tiết phiên mua sắm
  const currentEntry = mergedCarts.find((c) => c.cart_id === selectedId) || null;
  const currentBackend = currentEntry?.backend || null;
  const currentSim = currentEntry?.sim || null;
  const activeSessionId = currentBackend?.session?.id || currentSim?.session_id || null;

  useEffect(() => {
    const bat = currentBackend?.battery_percent ?? currentSim?.battery_percent;
    if (bat != null) setBatteryInput(Math.round(bat));
  }, [selectedId, currentBackend?.battery_percent, currentSim?.battery_percent]);

  useEffect(() => {
    if (!activeSessionId) {
      setSessionDetail(null);
      return;
    }
    let cancelled = false;
    api.getSession(activeSessionId)
      .then((s) => { if (!cancelled) setSessionDetail(s); })
      .catch(() => { if (!cancelled) setSessionDetail(null); });
    return () => { cancelled = true; };
  }, [activeSessionId, currentBackend?.session?.item_count, currentBackend?.session?.total_amount]);

  // Vòng lặp requestAnimationFrame di chuyển xe mượt mà theo chuỗi waypoint hành lang
  useEffect(() => {
    let rafId = 0;
    let lastTs = performance.now();

    const tick = (now) => {
      const dt = Math.min(0.1, (now - lastTs) / 1000);
      lastTs = now;

      if (!pausedRef.current) {
        const curRoutes = routesRef.current;
        const activeIds = Object.keys(curRoutes).filter((id) => curRoutes[id]?.length > 0);
        if (activeIds.length > 0) {
          const nextPos = { ...positionsRef.current };
          const nextRoutes = { ...curRoutes };
          let posChanged = false;
          let routeChanged = false;

          for (const cid of activeIds) {
            const route = [...nextRoutes[cid]];
            const targetWp = route[0];
            const targetPt = WAYPOINTS[targetWp];
            const cur = nextPos[cid];
            if (!targetPt || !cur) {
              nextRoutes[cid] = [];
              routeChanged = true;
              continue;
            }
            const dx = targetPt.x - cur.x;
            const dy = targetPt.y - cur.y;
            const dist = Math.hypot(dx, dy);
            const step = MOVE_SPEED_PX_PER_SEC * dt;

            if (dist <= step || dist < 1.5) {
              nextPos[cid] = { x: targetPt.x, y: targetPt.y, wp: targetWp, zone: targetPt.zone };
              route.shift();
              nextRoutes[cid] = route;
              posChanged = true;
              routeChanged = true;
            } else {
              nextPos[cid] = {
                ...cur,
                x: cur.x + (dx / dist) * step,
                y: cur.y + (dy / dist) * step,
              };
              posChanged = true;
            }
          }

          if (posChanged) {
            positionsRef.current = nextPos;
            setPositions(nextPos);
          }
          if (routeChanged) {
            routesRef.current = nextRoutes;
            setRoutes(nextRoutes);
          }
        }
      }

      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, []);

  // Điều hướng xe dọc theo hành lang đến khu vực đích (không đi xuyên kệ hàng)
  const moveCartToZone = useCallback((cartId, zoneId) => {
    const zone = zoneById(zoneId);
    if (!zone) return;
    const cur = positionsRef.current[cartId] || initialSlotForIndex(0);
    const startWp = cur.wp || nearestWaypoint(cur.x, cur.y);
    const path = findPathWaypoints(startWp, zone.stop);
    const nextRoutes = { ...routesRef.current, [cartId]: path };
    routesRef.current = nextRoutes;
    setRoutes(nextRoutes);
    if (zoneId === 'entrance') {
      setCheckoutFlags((prev) => ({ ...prev, [cartId]: false }));
    }
  }, []);

  // Helper chạy action bất đồng bộ có khóa nút & thông báo lỗi rõ ràng
  const runAction = async (label, fn) => {
    setBusyAction(label);
    try {
      await fn();
      await Promise.allSettled([refresh(), loadSim()]);
    } catch (e) {
      toast('error', e.message || `Thao tác ${label} thất bại`);
    } finally {
      setBusyAction(null);
    }
  };

  // Đợi Simulator nhận lệnh START_SESSION qua MQTT (tối đa ~2s)
  const ensureSessionReady = async (cartId) => {
    const existingSid = state.carts[cartId]?.session?.id || simCarts[cartId]?.session_id;
    if (existingSid) return existingSid;

    const sess = await api.createSession(cartId);
    setCheckoutFlags((prev) => ({ ...prev, [cartId]: false }));
    const deadline = Date.now() + 2500;
    while (Date.now() < deadline) {
      const list = await simApi.carts().catch(() => []);
      const found = list.find((c) => c.cart_id === cartId);
      if (found?.session_id === sess.id) break;
      await new Promise((r) => setTimeout(r, 150));
    }
    return sess.id;
  };

  // Các handler điều khiển Simulation & nghiệp vụ IoT
  const handleStartSession = () => runAction('start-session', async () => {
    if (!writable) throw new Error('Tài khoản chỉ xem không có quyền bắt đầu phiên');
    const sess = await api.createSession(selectedId);
    setCheckoutFlags((prev) => ({ ...prev, [selectedId]: false }));
    const curZone = positionsRef.current[selectedId]?.zone;
    if (!curZone || curZone === 'entrance' || curZone === 'exit' || curZone === 'checkout') {
      moveCartToZone(selectedId, 'grocery');
    }
    toast('ok', `Đã bắt đầu phiên #${sess.id} cho ${selectedId}`);
  });

  const handleScanAdd = () => runAction('scan-add', async () => {
    if (!selectedBarcode) throw new Error('Chưa có sản phẩm nào trong danh mục');
    const prod = catalog.find((p) => p.barcode === selectedBarcode);
    await ensureSessionReady(selectedId);
    if (prod) {
      moveCartToZone(selectedId, inferZoneForProduct(prod));
    }
    const res = await simApi.scan(selectedId, selectedBarcode, 'ADD');
    if (res.offline_queued) {
      toast('warn', `${selectedId} đang offline — đã xếp hàng đợi ${res.offline_queue_len} sự kiện`);
    } else {
      toast('ok', `${selectedId} đã quét thêm ${prod?.name || selectedBarcode}`);
    }
  });

  const handleScanRemove = () => runAction('scan-remove', async () => {
    const targetBarcode = sessionDetail?.items?.[0]?.barcode || selectedBarcode;
    if (!targetBarcode) throw new Error('Không có sản phẩm để bỏ bớt');
    const res = await simApi.scan(selectedId, targetBarcode, 'REMOVE');
    toast('ok', `${selectedId} đã bỏ bớt ${res.barcode}`);
  });

  const handleScanUnknown = () => runAction('scan-unknown', async () => {
    await ensureSessionReady(selectedId);
    await simApi.scan(selectedId, 'UNKNOWN_999999', 'ADD');
    toast('warn', `${selectedId} đã gửi mã vạch không hợp lệ (UNKNOWN_999999)`);
  });

  const handleCheckout = () => runAction('checkout', async () => {
    if (!writable) throw new Error('Tài khoản chỉ xem không có quyền checkout');
    if (!activeSessionId) throw new Error(`${selectedId} chưa có phiên mua hàng đang hoạt động`);
    const result = await api.checkout(activeSessionId);
    setCheckoutFlags((prev) => ({ ...prev, [selectedId]: true }));
    moveCartToZone(selectedId, 'checkout');
    toast('ok', `Checkout thành công phiên #${activeSessionId} · ${vnd(result.total_amount)}`);
  });

  const handleSetBattery = (pct) => runAction('battery', async () => {
    const val = Math.max(0, Math.min(100, Number(pct)));
    await simApi.battery(selectedId, val);
    setBatteryInput(val);
    toast(val < 20 ? 'warn' : 'ok', `${selectedId} pin → ${val}%`);
  });

  const handleWeightOffset = (grams) => runAction('weight', async () => {
    await simApi.weightOffset(selectedId, Number(grams));
    toast(grams === 0 ? 'ok' : 'warn', grams === 0 ? `${selectedId} đã cân lại chuẩn (0g)` : `${selectedId} lệch cân ${grams > 0 ? '+' : ''}${grams}g`);
  });

  const handleConnection = (online) => runAction('connection', async () => {
    await simApi.connection(selectedId, online);
    toast(online ? 'ok' : 'warn', `${selectedId} → ${online ? 'ONLINE (kết nối lại)' : 'OFFLINE (ngắt mạng)'}`);
  });

  const handleResetSimulation = () => runAction('reset-sim', async () => {
    setPaused(false);
    setCheckoutFlags({});
    const resetPos = {};
    mergedCarts.forEach((c, idx) => {
      resetPos[c.cart_id] = initialSlotForIndex(idx);
    });
    positionsRef.current = resetPos;
    routesRef.current = {};
    setPositions(resetPos);
    setRoutes({});

    // Khôi phục phần cứng mô phỏng trên Simulator (nếu đang chạy) và đóng phiên còn mở
    await Promise.allSettled(
      mergedCarts.map(async (c) => {
        if (writable && c.backend?.session?.id) {
          await api.cancelSession(c.backend.session.id).catch(() => {});
        }
        await simApi.connection(c.cart_id, true).catch(() => {});
        await simApi.weightOffset(c.cart_id, 0).catch(() => {});
        await simApi.battery(c.cart_id, 100).catch(() => {});
        if (writable && c.backend?.cart_status === 'LOCKED') {
          await api.unlockCart(c.cart_id).catch(() => {});
        }
      }),
    );
    toast('ok', 'Đã đặt lại trạng thái mô phỏng 2D và toàn bộ xe về Lối vào');
  });

  // Thống kê nhanh đội xe trên thanh điều khiển
  const stats = useMemo(() => {
    const total = mergedCarts.length;
    const online = mergedCarts.filter((c) => (c.backend?.connection_status || (c.sim?.connected ? 'ONLINE' : 'OFFLINE')) === 'ONLINE').length;
    const activeSessions = mergedCarts.filter((c) => Boolean(c.backend?.session?.id || c.sim?.session_id)).length;
    const alertsCount = state.alerts.filter((a) => a.status === 'ACTIVE').length;
    return { total, online, activeSessions, alertsCount };
  }, [mergedCarts, state.alerts]);

  const visualSelected = cartVisualState(currentBackend, currentSim, checkoutFlags[selectedId]);
  const selConn = currentBackend?.connection_status || (currentSim?.connected ? 'ONLINE' : 'OFFLINE');
  const selStatus = currentBackend?.cart_status || currentSim?.cart_status || 'AVAILABLE';
  const selBattery = currentBackend?.battery_percent ?? currentSim?.battery_percent;
  const selWeight = currentBackend?.current_weight ?? currentSim?.true_weight ?? 0;
  const selExpected = sessionDetail?.expected_weight ?? currentSim?.expected_weight ?? 0;
  const selAlerts = currentBackend?.active_alerts || [];
  const selZone = zoneById(positions[selectedId]?.zone || 'entrance');
  const itemsToRender = sessionDetail?.items || currentSim?.basket || [];

  return (
    <div className="shell sim2d-shell">
      {/* Header điều hướng đồng nhất với hệ thống Admin */}
      <header className="topbar">
        <div className="topbar-left">
          <Link to="/admin" className="brand">Smart Cart <span className="pill">Digital Twin 2D</span></Link>
          <nav className="nav">
            <Link to="/admin" className="nav-link">Tổng quan</Link>
            <Link to="/admin/alerts" className="nav-link">Cảnh báo</Link>
            <Link to="/admin/products" className="nav-link">Sản phẩm</Link>
            <Link to="/simulation" className="nav-link active" data-testid="nav-simulation">Mô phỏng 2D</Link>
            <Link to="/simulator" className="nav-link">Simulator</Link>
          </nav>
        </div>
        <div className="topbar-right">
          <WsIndicator />
          {auth.staff && (
            <span className="user-chip" data-testid="user-chip">
              {auth.staff.username} · {auth.staff.role === 'admin' ? 'Quản trị' : 'Chỉ xem'}
              <button className="btn btn-link btn-small" onClick={() => api.logout()} data-testid="logout">Đăng xuất</button>
            </span>
          )}
          <Link to="/customer" className="link-muted">Màn hình khách →</Link>
        </div>
      </header>

      {/* Thanh điều khiển tổng quan Simulation */}
      <section className="sim2d-toolbar card">
        <div className="sim2d-toolbar-left">
          <div>
            <h1 style={{ fontSize: '1.15rem', margin: 0 }}>Mô phỏng Siêu thị 2D (Supermarket Digital Twin)</h1>
            <div className="muted small">Đồng bộ realtime qua MQTT · Backend FastAPI · WebSocket · Simulator ({simApi.base})</div>
          </div>
          <span
            className={`badge ${paused ? 'badge-warn' : 'badge-ok'}`}
            data-testid="sim-run-state"
          >
            {paused ? 'PAUSED · Tạm dừng di chuyển' : 'RUNNING · Đang hoạt động'}
          </span>
        </div>

        <div className="sim2d-kpis">
          <span className="sim2d-kpi">Xe online: <b>{stats.online}/{stats.total}</b></span>
          <span className="sim2d-kpi">Phiên mở: <b>{stats.activeSessions}</b></span>
          <span className="sim2d-kpi">Cảnh báo: <b className={stats.alertsCount > 0 ? 'text-danger' : ''}>{stats.alertsCount}</b></span>
          <span className="sim2d-kpi">Simulator: <b className={simError ? 'text-danger' : 'text-ok'}>{simError ? 'Ngắt kết nối' : 'Sẵn sàng'}</b></span>
        </div>

        <div className="sim2d-global-btns">
          <button
            type="button"
            className="btn btn-primary btn-small"
            onClick={() => { setPaused(false); toast('ok', 'Đã tiếp tục mô phỏng 2D'); }}
            disabled={!paused}
            data-testid="btn-sim-start"
          >
            Start Simulation
          </button>
          <button
            type="button"
            className="btn btn-small"
            onClick={() => { setPaused(true); toast('warn', 'Đã tạm dừng chuyển động 2D (WebSocket vẫn nhận sự kiện)'); }}
            disabled={paused}
            data-testid="btn-sim-pause"
          >
            Pause Simulation
          </button>
          <button
            type="button"
            className="btn btn-small"
            onClick={handleResetSimulation}
            disabled={busyAction === 'reset-sim'}
            data-testid="btn-sim-reset"
          >
            Reset Simulation
          </button>
        </div>
      </section>

      <div className="sim2d-alerts-wrap">
        <ErrorBanner error={state.error} onRetry={refresh} />
        {simError && (
          <div className="banner banner-warn" data-testid="sim-error-banner">
            <span><strong>Simulator chưa sẵn sàng:</strong> {simError}. Các lệnh giả lập phần cứng (quét, pin, cân, mất mạng) tạm không khả dụng, bản đồ vẫn hiển thị trạng thái thực từ Backend.</span>
            <button type="button" className="btn btn-small" onClick={loadSim}>Thử lại</button>
          </div>
        )}
      </div>

      {/* Bố cục 3 cột Cockpit */}
      <main className="sim2d-cockpit">
        {/* Cột trái: Danh sách đội xe */}
        <aside className="card sim2d-fleet" data-testid="fleet-panel">
          <div className="sim2d-card-head">
            <h2>Đội xe ({mergedCarts.length})</h2>
            <span className="muted small">Chọn xe</span>
          </div>
          <div className="sim2d-fleet-list">
            {mergedCarts.map(({ cart_id, backend, sim }) => {
              const vis = cartVisualState(backend, sim, checkoutFlags[cart_id]);
              const bat = backend?.battery_percent ?? sim?.battery_percent;
              const w = backend?.current_weight ?? sim?.true_weight ?? 0;
              const items = backend?.session?.item_count ?? (sim?.basket?.reduce((s, i) => s + i.quantity, 0) || 0);
              const alertsN = backend?.active_alerts?.length || 0;
              const zLabel = zoneById(positions[cart_id]?.zone || 'entrance')?.label || 'Lối vào';
              const isSel = cart_id === selectedId;
              return (
                <button
                  type="button"
                  key={cart_id}
                  onClick={() => setSelectedId(cart_id)}
                  className={`sim2d-fleet-item ${isSel ? 'selected' : ''}`}
                  data-testid={`fleet-item-${cart_id}`}
                >
                  <div className="sim2d-fleet-top">
                    <span className="mono" style={{ fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <i className="leg-dot" style={{ background: vis.color }} />
                      {cart_id}
                    </span>
                    <span className="sim2d-pill" style={{ color: vis.color, background: vis.bg }}>{vis.label}</span>
                  </div>
                  <div className="sim2d-fleet-meta muted small">
                    <span>{zLabel}</span>
                    <span>{bat != null ? `${Math.round(bat)}%` : '—'} · {weight(w)} · {items} món</span>
                  </div>
                  {alertsN > 0 && (
                    <div className="sim2d-fleet-alert">{alertsN} cảnh báo đang mở</div>
                  )}
                </button>
              );
            })}
            {mergedCarts.length === 0 && (
              <div className="muted small" style={{ padding: '12px 0' }}>Chưa có xe đẩy nào được đăng ký.</div>
            )}
          </div>
        </aside>

        {/* Cột giữa: Bản đồ siêu thị 2D tương tác */}
        <section className="card sim2d-map-card">
          <SupermarketMap
            cartsList={mergedCarts}
            positions={positions}
            routes={routes}
            selectedId={selectedId}
            onSelectCart={setSelectedId}
            onSelectZone={(zId) => {
              setTargetZone(zId);
              moveCartToZone(selectedId, zId);
            }}
            checkoutFlags={checkoutFlags}
          />
        </section>

        {/* Cột phải: Chi tiết xe + Bảng điều khiển tương tác */}
        <aside className="sim2d-right">
          {/* Thông tin chi tiết xe */}
          <section className="card sim2d-inspector" data-testid="inspector-panel">
            <div className="sim2d-card-head">
              <div>
                <h2 className="mono" style={{ margin: 0, fontSize: '1.1rem' }} data-testid="inspector-cart-id">{selectedId}</h2>
                <div className="muted small">Khu vực 2D: <strong>{selZone?.label || 'Lối vào'}</strong></div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                <ConnBadge status={selConn} />
                <StatusBadge status={selStatus} />
              </div>
            </div>

            <div className="sim2d-kv-grid">
              <div className="sim2d-kv">
                <span className="muted small">Pin</span>
                <div><Battery value={selBattery} /></div>
              </div>
              <div className="sim2d-kv">
                <span className="muted small">Trạng thái bản đồ</span>
                <div><span className="sim2d-pill" style={{ color: visualSelected.color, background: visualSelected.bg }}>{visualSelected.label}</span></div>
              </div>
              <div className="sim2d-kv">
                <span className="muted small">Trọng lượng thực / Dự kiến</span>
                <strong data-testid="inspector-weight">{weight(selWeight)} / {weight(selExpected)}</strong>
              </div>
              <div className="sim2d-kv">
                <span className="muted small">Phiên & Số món</span>
                <strong data-testid="inspector-session">
                  {activeSessionId ? `#${activeSessionId} · ${currentBackend?.session?.item_count ?? itemsToRender.length} món` : 'Chưa mở phiên'}
                </strong>
              </div>
              <div className="sim2d-kv">
                <span className="muted small">Tổng tiền</span>
                <strong data-testid="inspector-total">{vnd(currentBackend?.session?.total_amount ?? 0)}</strong>
              </div>
              <div className="sim2d-kv">
                <span className="muted small">Cập nhật cuối</span>
                <span>{ago(currentBackend?.last_seen)}</span>
              </div>
            </div>

            {/* Cảnh báo đang mở của xe */}
            {selAlerts.length > 0 && (
              <div className="sim2d-subblock" data-testid="inspector-alerts">
                <div className="muted small" style={{ marginBottom: 4 }}>Cảnh báo đang mở ({selAlerts.length})</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {selAlerts.map((alertType) => (
                    <span key={alertType} className="badge badge-danger" data-testid={`alert-badge-${alertType}`}>
                      {ALERT_TYPE[alertType]?.label || alertType}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Sản phẩm trong giỏ hiện tại */}
            <div className="sim2d-subblock">
              <div className="muted small" style={{ marginBottom: 4 }}>Sản phẩm trong giỏ ({itemsToRender.length})</div>
              {itemsToRender.length === 0 ? (
                <div className="muted small">Giỏ hàng đang trống.</div>
              ) : (
                <ul className="sim2d-items-list" data-testid="inspector-items">
                  {itemsToRender.map((it) => (
                    <li key={it.barcode}>
                      <span>{it.name || it.barcode} × {it.quantity}</span>
                      <span className="mono">{it.subtotal != null ? vnd(it.subtotal) : weight((it.unit_weight || 0) * it.quantity)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          {/* Bảng điều khiển Simulation Controls */}
          <section className="card sim2d-controls" data-testid="sim-controls">
            <div className="sim2d-card-head">
              <h2>Điều khiển kịch bản IoT</h2>
              {busyAction && <span className="muted small">Đang xử lý...</span>}
            </div>

            {/* 1. Di chuyển xe 2D */}
            <div className="sim2d-ctrl-group">
              <label className="small muted">Di chuyển xe (Digital Twin)</label>
              <div className="sim2d-ctrl-row">
                <select
                  value={targetZone}
                  onChange={(e) => setTargetZone(e.target.value)}
                  data-testid="select-target-zone"
                >
                  {ZONES.map((z) => (
                    <option key={z.id} value={z.id}>{z.label} ({z.en})</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={() => moveCartToZone(selectedId, targetZone)}
                  data-testid="btn-move-cart"
                >
                  Di chuyển xe
                </button>
              </div>
            </div>

            {/* 2. Nghiệp vụ phiên mua sắm */}
            <div className="sim2d-ctrl-group">
              <label className="small muted">Nghiệp vụ mua sắm (Backend + MQTT)</label>
              <div className="sim2d-btn-grid">
                <button
                  type="button"
                  className="btn btn-primary btn-small"
                  onClick={handleStartSession}
                  disabled={!writable || Boolean(activeSessionId) || Boolean(busyAction)}
                  data-testid="btn-start-session"
                >
                  Bắt đầu phiên
                </button>
                <button
                  type="button"
                  className="btn btn-ok btn-small"
                  onClick={handleCheckout}
                  disabled={!writable || !activeSessionId || Boolean(busyAction)}
                  data-testid="btn-checkout"
                >
                  Checkout
                </button>
              </div>
              <div className="sim2d-ctrl-row" style={{ marginTop: 6 }}>
                <select
                  value={selectedBarcode}
                  onChange={(e) => setSelectedBarcode(e.target.value)}
                  data-testid="select-product"
                >
                  {catalog.map((p) => (
                    <option key={p.barcode} value={p.barcode}>
                      {p.name} ({vnd(p.price)} · {p.unit_weight ?? p.weight ?? 0}g)
                    </option>
                  ))}
                </select>
              </div>
              <div className="sim2d-btn-grid" style={{ marginTop: 6 }}>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={handleScanAdd}
                  disabled={Boolean(simError) || Boolean(busyAction)}
                  data-testid="btn-scan-add"
                >
                  Quét & Thêm
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={handleScanRemove}
                  disabled={Boolean(simError) || Boolean(busyAction)}
                  data-testid="btn-scan-remove"
                >
                  Bỏ 1 món
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={handleScanUnknown}
                  disabled={Boolean(simError) || Boolean(busyAction)}
                  data-testid="btn-scan-unknown"
                >
                  Quét mã lạ
                </button>
              </div>
            </div>

            {/* 3. Sự cố phần cứng & cảm biến mô phỏng */}
            <div className="sim2d-ctrl-group">
              <label className="small muted">Pin, Cảm biến cân & Kết nối mạng</label>
              <div className="sim2d-ctrl-row">
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={batteryInput}
                  onChange={(e) => setBatteryInput(Number(e.target.value))}
                  onMouseUp={(e) => handleSetBattery(e.currentTarget.value)}
                  onTouchEnd={(e) => handleSetBattery(e.currentTarget.value)}
                  disabled={Boolean(simError)}
                  aria-label="Mức pin mô phỏng"
                  style={{ flex: 1 }}
                />
                <span className="mono small" style={{ minWidth: 38, textAlign: 'right' }}>{batteryInput}%</span>
              </div>
              <div className="sim2d-btn-grid" style={{ marginTop: 6 }}>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={() => handleSetBattery(15)}
                  disabled={Boolean(simError) || Boolean(busyAction)}
                  data-testid="btn-low-battery"
                >
                  Pin 15%
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={() => handleSetBattery(100)}
                  disabled={Boolean(simError) || Boolean(busyAction)}
                  data-testid="btn-full-battery"
                >
                  Sạc 100%
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={() => handleWeightOffset(250)}
                  disabled={Boolean(simError) || Boolean(busyAction)}
                  data-testid="btn-weight-mismatch"
                >
                  Lệch cân +250g
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={() => handleWeightOffset(0)}
                  disabled={Boolean(simError) || Boolean(busyAction)}
                  data-testid="btn-weight-reset"
                >
                  Cân chuẩn 0g
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={() => handleConnection(false)}
                  disabled={Boolean(simError) || Boolean(busyAction)}
                  data-testid="btn-trigger-offline"
                >
                  Ngắt mạng
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={() => handleConnection(true)}
                  disabled={Boolean(simError) || Boolean(busyAction)}
                  data-testid="btn-trigger-reconnect"
                >
                  Kết nối lại
                </button>
              </div>
            </div>
          </section>
        </aside>
      </main>

      {/* Live Event Log từ WebSocket */}
      <section className="card sim2d-eventlog" data-testid="live-event-log">
        <div className="sim2d-card-head">
          <h2>Live Event Log (WebSocket Realtime)</h2>
          <span className="muted small">Hiển thị {state.eventLog.length} sự kiện gần nhất</span>
        </div>
        {state.eventLog.length === 0 ? (
          <div className="muted small" style={{ padding: '8px 0' }}>Đang chờ sự kiện realtime từ WebSocket...</div>
        ) : (
          <div className="sim2d-log-scroll">
            <table className="table sim2d-log-table">
              <thead>
                <tr>
                  <th style={{ width: 90 }}>Thời gian</th>
                  <th style={{ width: 150 }}>Sự kiện</th>
                  <th style={{ width: 100 }}>Xe</th>
                  <th>Chi tiết</th>
                </tr>
              </thead>
              <tbody>
                {state.eventLog.map((ev) => (
                  <tr key={ev.id}>
                    <td className="mono small">{timeOnly(ev.timestamp)}</td>
                    <td><span className="badge badge-info">{ev.type}</span></td>
                    <td className="mono">{ev.cart_id}</td>
                    <td>{ev.summary}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <Toasts scope="admin" />
    </div>
  );
}
