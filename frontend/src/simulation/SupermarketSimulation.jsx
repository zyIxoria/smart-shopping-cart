import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, USE_MOCK } from '../api/index.js';
import { canWrite, useAuth } from '../api/auth.js';
import { simApi } from '../api/sim.js';
import { ago, ALERT_TYPE, CART_STATUS, timeOnly, vnd, weight } from '../common/format.js';
import { Badge, Battery, ConnBadge } from '../common/ui.jsx';
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
import Supermarket3D from './Supermarket3D.jsx';

const POLL_SIM_MS = 1200;
const MOVE_SPEED_PX_PER_SEC = 210;

// Gợi ý khu vực kệ hàng tương ứng với tên/danh mục sản phẩm khi mô phỏng quét hàng
export function inferZoneForProduct(prod) {
  const txt = `${prod?.category || ''} ${prod?.name || ''}`.toLowerCase();
  if (/(bột giặt|nước giặt|omo|ariel|comfort|downy|rửa chén|sunlight|khăn giấy|giấy|pulppy|tẩy|gia dụng|household|clean|detergent|tissue)/.test(txt)) return 'household';
  if (/(dầu gội|sữa tắm|kem đánh răng|p\/s|colgate|closeup|cá nhân|personal|shampoo|soap|shower)/.test(txt)) return 'personal_care';
  if (/(coca|cola|pepsi|sprite|fanta|7up|sting|redbull|bò húc|0 độ|trà|sữa tươi|vinamilk|th true milk|milo|aquafina|lavie|nước suối|nước ngọt|nước khoáng|cà phê|bia|drink|beverage|milk|tea|water|juice)/.test(txt)) return 'beverage';
  return 'grocery';
}

export default function SupermarketSimulation() {
  const { state, refresh, toast } = useStore();
  const auth = useAuth();
  const writable = canWrite(auth);

  // Trạng thái Simulator & dữ liệu phiên chi tiết
  const [simCarts, setSimCarts] = useState({});
  const [catalog, setCatalog] = useState([]);
  const [simError, setSimError] = useState(null);
  const [sessionDetail, setSessionDetail] = useState(null);
  const [busyAction, setBusyAction] = useState(null);

  // Chế độ hiển thị không gian mô phỏng: 3D Digital Twin (mặc định) hoặc 2D Mặt bằng
  const [viewDimension, setViewDimension] = useState('3d');

  // Trạng thái điều khiển Digital Twin
  const [selectedId, setSelectedId] = useState('CART_001');
  const [targetZone, setTargetZone] = useState('beverage');
  const [selectedBarcode, setSelectedBarcode] = useState('');
  const [filterByZone, setFilterByZone] = useState(true);
  const [batteryInput, setBatteryInput] = useState(100);
  const [paused, setPaused] = useState(false);
  const [checkoutFlags, setCheckoutFlags] = useState({});

  // Trạng thái online mô phỏng: { [cart_id]: boolean } (ban đầu tất cả xe chưa mở phiên đều OFFLINE)
  const [onlineCarts, setOnlineCarts] = useState({});

  // Tiến trình tự động checkout: 'to_checkout' -> 'to_exit' -> 'to_bay'
  const checkoutStageRef = useRef({});

  // Toạ độ và tuyến đường waypoint 2D của từng xe
  const [positions, setPositions] = useState({});
  const [routes, setRoutes] = useState({});
  const positionsRef = useRef({});
  const routesRef = useRef({});
  const pausedRef = useRef(false);
  pausedRef.current = paused;

  // Hợp nhất danh sách xe từ Backend + Simulator (giữ thứ tự ổn định)
  const mergedCarts = useMemo(() => {
    const ids = Array.from(new Set([...Object.keys(state.carts), ...Object.keys(simCarts)])).sort();
    return ids.map((id) => ({
      cart_id: id,
      backend: state.carts[id] || null,
      sim: simCarts[id] || null,
    }));
  }, [state.carts, simCarts]);

  // Kiểm tra trạng thái Online của xe: Mặc định khi khởi động mọi xe chưa mở phiên đều OFFLINE
  const isCartOnline = useCallback((cid) => {
    if (onlineCarts[cid] !== undefined) return onlineCarts[cid];
    const b = state.carts[cid];
    const s = simCarts[cid];
    if (b?.session?.id || s?.session_id) return true;
    return false;
  }, [onlineCarts, state.carts, simCarts]);

  // Danh sách xe với connection_status phản ánh đúng logic khởi động offline / phiên online
  const effectiveCarts = useMemo(() => {
    return mergedCarts.map((c) => {
      const isOnline = isCartOnline(c.cart_id);
      const connStatus = isOnline ? 'ONLINE' : 'OFFLINE';
      return {
        ...c,
        backend: c.backend ? { ...c.backend, connection_status: connStatus } : null,
        sim: c.sim ? { ...c.sim, connected: isOnline } : null,
      };
    });
  }, [mergedCarts, isCartOnline]);

  useEffect(() => {
    if (effectiveCarts.length > 0 && !effectiveCarts.some((c) => c.cart_id === selectedId)) {
      setSelectedId(effectiveCarts[0].cart_id);
    }
  }, [effectiveCarts, selectedId]);

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

  // Đồng bộ trạng thái Simulator qua proxy Backend (hoặc ?sim= trực tiếp), không phát lỗi mạng khi mock=1
  const loadSim = useCallback(async () => {
    if (USE_MOCK) {
      setSimError('Đang ở chế độ dữ liệu giả (mock)');
      return;
    }
    try {
      const res = await simApi.embeddedState();
      if (!res?.available) {
        setSimCarts({});
        setSimError(res?.error || 'Simulator chưa chạy (:8090)');
        return;
      }
      const map = {};
      (res.carts || []).forEach((c) => { map[c.cart_id] = c; });
      setSimCarts(map);
      if (Array.isArray(res.catalog) && res.catalog.length > 0) {
        setCatalog(res.catalog);
        setSelectedBarcode((prev) => prev || res.catalog[0].barcode);
      }
      setSimError(null);
    } catch (e) {
      setSimError(e.message || 'Không kết nối được Simulator');
    }
  }, []);

  useEffect(() => {
    loadSim();
    api.getProducts()
      .then((prods) => {
        setCatalog((prev) => (prev.length ? prev : prods));
        if (prods.length) setSelectedBarcode((prev) => prev || prods[0].barcode);
      })
      .catch(() => {});
    if (USE_MOCK) return undefined;
    const timer = setInterval(loadSim, POLL_SIM_MS);
    return () => clearInterval(timer);
  }, [loadSim]);

  const currentEntry = effectiveCarts.find((c) => c.cart_id === selectedId) || null;
  const currentBackend = currentEntry?.backend || null;
  const currentSim = currentEntry?.sim || null;
  const activeSessionId = currentBackend?.session?.id || null;

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

  const moveCartToZone = useCallback((cartId, zoneId, bypassOfflineCheck = false) => {
    if (!bypassOfflineCheck && !isCartOnline(cartId)) {
      toast('warn', `Xe ${cartId} đang OFFLINE tại bãi giữ xe. Hãy bấm "Bắt đầu phiên" để kích hoạt xe trước khi di chuyển!`, { scope: 'admin' });
      return;
    }
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
  }, [isCartOnline, toast]);

  const moveCartToZoneRef = useRef(moveCartToZone);
  moveCartToZoneRef.current = moveCartToZone;

  // Xử lý chuỗi sự kiện khi xe đến điểm đích của chặng (quầy thanh toán -> lối ra -> quay về bãi xe sẵn sàng đón khách mới)
  const handleDestinationReached = useCallback((cid, arrivedZone) => {
    const stage = checkoutStageRef.current[cid];
    if (!stage) return;

    if (stage === 'to_checkout') {
      // 1. Đã tới Quầy thanh toán -> dừng 1.2s rồi tự động di chuyển ra Lối ra
      checkoutStageRef.current[cid] = 'waiting_at_checkout';
      setTimeout(() => {
        checkoutStageRef.current[cid] = 'to_exit';
        moveCartToZoneRef.current(cid, 'exit', true);
        toast('ok', `Xe ${cid} thanh toán xong, đang di chuyển ra Lối ra...`, { scope: 'admin' });
      }, 1200);
    } else if (stage === 'to_exit') {
      // 2. Đã tới Lối ra -> bàn giao hoàn tất, dừng 1.2s rồi tự động trở về Bãi giữ xe
      checkoutStageRef.current[cid] = 'waiting_at_exit';
      toast('info', `Xe ${cid} đã qua Lối ra · Tự động trở về bãi giữ xe đón khách mới...`, { scope: 'admin' });
      setTimeout(() => {
        checkoutStageRef.current[cid] = 'to_bay';
        moveCartToZoneRef.current(cid, 'entrance', true);
      }, 1200);
    } else if (stage === 'to_bay') {
      // 3. Đã về tới Bãi giữ xe -> đỗ vào slot ban đầu, xe ở trạng thái Sẵn sàng (ONLINE, giỏ trống đón khách mới)
      delete checkoutStageRef.current[cid];
      setCheckoutFlags((prev) => ({ ...prev, [cid]: false }));
      setOnlineCarts((prev) => ({ ...prev, [cid]: true }));
      const cIdx = mergedCarts.findIndex((c) => c.cart_id === cid);
      const parkSlot = initialSlotForIndex(cIdx >= 0 ? cIdx : 0);
      positionsRef.current = {
        ...positionsRef.current,
        [cid]: parkSlot,
      };
      setPositions({ ...positionsRef.current });
      toast('ok', `Xe ${cid} đã về bãi đỗ (Giỏ trống · Sẵn sàng đón khách mới)`, { scope: 'admin' });
    }
  }, [mergedCarts, toast]);

  const handleDestinationReachedRef = useRef(handleDestinationReached);
  handleDestinationReachedRef.current = handleDestinationReached;

  // Vòng lặp requestAnimationFrame di chuyển xe mượt mà theo hành lang
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
              if (route.length === 0) {
                setTimeout(() => handleDestinationReachedRef.current(cid, targetPt.zone), 0);
              }
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

  const runAction = async (label, fn) => {
    setBusyAction(label);
    try {
      await fn();
      await Promise.allSettled([refresh(), loadSim()]);
    } catch (e) {
      toast('error', e.message || `Thao tác ${label} thất bại`, { scope: 'admin' });
    } finally {
      setBusyAction(null);
    }
  };

  const ensureSessionReady = async (cartId) => {
    const existingSid = state.carts[cartId]?.session?.id || simCarts[cartId]?.session_id;
    if (existingSid) return existingSid;

    setOnlineCarts((prev) => ({ ...prev, [cartId]: true }));
    await simApi.connection(cartId, true).catch(() => {});

    let sess = null;
    let lastErr = null;
    for (let i = 0; i < 5; i++) {
      try {
        sess = await api.createSession(cartId);
        break;
      } catch (err) {
        lastErr = err;
        if (err.message?.includes('OFFLINE') || err.message?.includes('CART_OFFLINE')) {
          await new Promise((r) => setTimeout(r, 200));
          continue;
        }
        throw err;
      }
    }
    if (!sess) throw lastErr;
    setCheckoutFlags((prev) => ({ ...prev, [cartId]: false }));
    const deadline = Date.now() + 2500;
    while (Date.now() < deadline) {
      const res = await simApi.embeddedState().catch(() => null);
      const found = (res?.carts || []).find((c) => c.cart_id === cartId);
      if (found?.session_id === sess.id) break;
      await new Promise((r) => setTimeout(r, 150));
    }
    return sess.id;
  };

  const handleStartSession = () => runAction('start-session', async () => {
    if (!writable) throw new Error('Tài khoản chỉ xem không có quyền bắt đầu phiên');
    setOnlineCarts((prev) => ({ ...prev, [selectedId]: true }));
    await simApi.connection(selectedId, true).catch(() => {});

    let sess = null;
    let lastErr = null;
    for (let i = 0; i < 5; i++) {
      try {
        sess = await api.createSession(selectedId);
        break;
      } catch (err) {
        lastErr = err;
        if (err.message?.includes('OFFLINE') || err.message?.includes('CART_OFFLINE')) {
          await new Promise((r) => setTimeout(r, 200));
          continue;
        }
        throw err;
      }
    }
    if (!sess) throw lastErr;

    setCheckoutFlags((prev) => ({ ...prev, [selectedId]: false }));
    const curZone = positionsRef.current[selectedId]?.zone;
    if (!curZone || curZone === 'entrance' || curZone === 'exit' || curZone === 'checkout') {
      moveCartToZone(selectedId, 'beverage', true);
    }
    toast('ok', `Đã kích hoạt ONLINE và bắt đầu phiên #${sess.id} cho ${selectedId}`, { scope: 'admin' });
  });

  const handleScanAdd = () => runAction('scan-add', async () => {
    if (!selectedBarcode) throw new Error('Chưa có sản phẩm nào trong danh mục');
    const prod = catalog.find((p) => p.barcode === selectedBarcode);
    await ensureSessionReady(selectedId);
    if (prod) {
      moveCartToZone(selectedId, inferZoneForProduct(prod), true);
    }
    const res = await simApi.scan(selectedId, selectedBarcode, 'ADD');
    if (res.offline_queued) {
      toast('warn', `${selectedId} đang offline — đã xếp hàng đợi ${res.offline_queue_len} sự kiện`, { scope: 'admin' });
    } else {
      toast('ok', `${selectedId} đã quét thêm ${prod?.name || selectedBarcode}`, { scope: 'admin' });
    }
  });

  const handleScanRemove = () => runAction('scan-remove', async () => {
    const targetBarcode = sessionDetail?.items?.[0]?.barcode || selectedBarcode;
    if (!targetBarcode) throw new Error('Không có sản phẩm để bỏ bớt');
    const res = await simApi.scan(selectedId, targetBarcode, 'REMOVE');
    toast('ok', `${selectedId} đã bỏ bớt ${res.barcode}`, { scope: 'admin' });
  });

  const handleScanUnknown = () => runAction('scan-unknown', async () => {
    await ensureSessionReady(selectedId);
    await simApi.scan(selectedId, 'UNKNOWN_999999', 'ADD');
    toast('warn', `${selectedId} đã gửi mã vạch không hợp lệ (UNKNOWN_999999)`, { scope: 'admin' });
  });

  const handleCheckout = () => runAction('checkout', async () => {
    if (!writable) throw new Error('Tài khoản chỉ xem không có quyền checkout');
    if (!activeSessionId) throw new Error(`${selectedId} chưa có phiên mua hàng đang hoạt động`);
    const result = await api.checkout(activeSessionId);
    setCheckoutFlags((prev) => ({ ...prev, [selectedId]: true }));
    checkoutStageRef.current[selectedId] = 'to_checkout';
    moveCartToZone(selectedId, 'checkout', true);
    toast('ok', `Checkout thành công phiên #${activeSessionId} · ${vnd(result.total_amount)}`, { scope: 'admin' });
  });

  const handleSetBattery = (pct) => runAction('battery', async () => {
    const val = Math.max(0, Math.min(100, Number(pct)));
    await simApi.battery(selectedId, val);
    setBatteryInput(val);
    toast(val < 20 ? 'warn' : 'ok', `${selectedId} pin → ${val}%`, { scope: 'admin' });
  });

  const handleWeightOffset = (grams) => runAction('weight', async () => {
    await simApi.weightOffset(selectedId, Number(grams));
    toast(grams === 0 ? 'ok' : 'warn', grams === 0 ? `${selectedId} đã cân lại chuẩn (0g)` : `${selectedId} lệch cân ${grams > 0 ? '+' : ''}${grams}g`, { scope: 'admin' });
  });

  const handleConnection = (online) => runAction('connection', async () => {
    setOnlineCarts((prev) => ({ ...prev, [selectedId]: online }));
    await simApi.connection(selectedId, online);
    toast(online ? 'ok' : 'warn', `${selectedId} → ${online ? 'ONLINE (kết nối lại)' : 'OFFLINE (ngắt mạng)'}`, { scope: 'admin' });
  });

  const handleResetSimulation = () => runAction('reset-sim', async () => {
    setPaused(false);
    setCheckoutFlags({});
    setOnlineCarts({});
    checkoutStageRef.current = {};
    const resetPos = {};
    mergedCarts.forEach((c, idx) => {
      resetPos[c.cart_id] = initialSlotForIndex(idx);
    });
    positionsRef.current = resetPos;
    routesRef.current = {};
    setPositions(resetPos);
    setRoutes({});

    if (!simError && writable) {
      await Promise.allSettled(
        mergedCarts.map(async (c) => {
          if (c.backend?.session?.id) {
            await api.cancelSession(c.backend.session.id).catch(() => {});
          }
          await simApi.connection(c.cart_id, false).catch(() => {});
          await simApi.weightOffset(c.cart_id, 0).catch(() => {});
          await simApi.battery(c.cart_id, 100).catch(() => {});
          if (c.backend?.cart_status === 'LOCKED') {
            await api.unlockCart(c.cart_id).catch(() => {});
          }
        }),
      );
    }
    toast('ok', 'Đã đặt lại mô phỏng: toàn bộ xe về Bãi xe và ở trạng thái OFFLINE', { scope: 'admin' });
  });

  const visualSelected = cartVisualState(currentBackend, currentSim, checkoutFlags[selectedId]);
  const selConn = currentBackend?.connection_status || (currentSim?.connected ? 'ONLINE' : 'OFFLINE');
  const selStatus = currentBackend?.cart_status || currentSim?.cart_status || 'AVAILABLE';
  const selBattery = currentBackend?.battery_percent ?? currentSim?.battery_percent;
  const selWeight = currentBackend?.current_weight ?? currentSim?.true_weight ?? 0;
  const selExpected = sessionDetail?.expected_weight ?? currentSim?.expected_weight ?? 0;
  const selAlerts = currentBackend?.active_alerts || [];
  const selZone = zoneById(positions[selectedId]?.zone || 'entrance');

  // Quầy hàng hiện tại (hoặc quầy đích đang di chuyển tới) của xe được chọn
  const activeZone = useMemo(() => {
    const curPos = positions[selectedId];
    const curRoute = routes[selectedId];
    if (curRoute && curRoute.length > 0) {
      const destWp = curRoute[curRoute.length - 1];
      if (WAYPOINTS[destWp]?.zone) return WAYPOINTS[destWp].zone;
    }
    return curPos?.zone || 'entrance';
  }, [positions, routes, selectedId]);

  const activeZoneObj = zoneById(activeZone) || selZone;
  const isRetailZone = ['grocery', 'beverage', 'household', 'personal_care'].includes(activeZone);

  // Danh sách sản phẩm hiển thị: nếu filterByZone và đang ở quầy bán lẻ -> chỉ hiện hàng tại quầy đó
  const displayedProducts = useMemo(() => {
    if (!catalog || catalog.length === 0) return [];
    if (filterByZone && isRetailZone) {
      const filtered = catalog.filter((p) => inferZoneForProduct(p) === activeZone);
      return filtered.length > 0 ? filtered : catalog;
    }
    return catalog;
  }, [catalog, filterByZone, isRetailZone, activeZone]);

  // Tự động giữ selectedBarcode hợp lệ khi danh sách sản phẩm thay đổi theo quầy
  useEffect(() => {
    if (displayedProducts.length === 0) return;
    const exists = displayedProducts.some((p) => p.barcode === selectedBarcode);
    if (!exists) {
      setSelectedBarcode(displayedProducts[0].barcode);
    }
  }, [displayedProducts, selectedBarcode]);

  const itemsToRender = sessionDetail?.items || currentSim?.basket || [];
  const hardwareDisabled = Boolean(simError) || Boolean(busyAction) || !writable;

  return (
    <section className="sim2d-embedded" data-testid="simulation-section">
      {/* Thanh điều khiển tổng quan Digital Twin */}
      <div className="sim2d-toolbar card">
        <div className="sim2d-toolbar-left">
          <div>
            <h2 style={{ fontSize: '1.08rem', margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>🛒</span> Siêu thị Interactive Digital Twin ({viewDimension === '3d' ? '3D' : '2D'})
            </h2>
            <div className="muted small">Giám sát không gian 3D/2D và điều khiển kịch bản IoT realtime qua MQTT · WebSocket</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              className={`badge ${paused ? 'badge-warn' : 'badge-ok'}`}
              data-testid="sim-run-state"
            >
              {paused ? 'PAUSED · Tạm dừng di chuyển' : 'RUNNING · Đang hoạt động'}
            </span>

            {/* Nút chuyển đổi chế độ xem 3D Digital Twin / 2D Mặt bằng */}
            <div className="sim-dimension-toggle" style={{ display: 'inline-flex', background: '#0f172a', padding: '2px', borderRadius: '6px', border: '1px solid #334155' }}>
              <button
                type="button"
                className={`btn btn-small ${viewDimension === '3d' ? 'btn-primary' : ''}`}
                onClick={() => setViewDimension('3d')}
                data-testid="toggle-view-3d"
                style={{ padding: '2px 8px', fontSize: '0.8rem' }}
              >
                🎮 3D Digital Twin
              </button>
              <button
                type="button"
                className={`btn btn-small ${viewDimension === '2d' ? 'btn-primary' : ''}`}
                onClick={() => setViewDimension('2d')}
                data-testid="toggle-view-2d"
                style={{ padding: '2px 8px', fontSize: '0.8rem' }}
              >
                🗺️ 2D Mặt bằng
              </button>
            </div>
          </div>
        </div>

        <div className="sim2d-global-btns">
          <span className="sim2d-kpi">Simulator: <b className={simError ? 'text-danger' : 'text-ok'}>{simError ? 'Chưa kết nối' : 'Sẵn sàng'}</b></span>
          <button
            type="button"
            className="btn btn-primary btn-small"
            onClick={() => { setPaused(false); toast('ok', 'Đã tiếp tục mô phỏng 2D', { scope: 'admin' }); }}
            disabled={!paused}
            data-testid="btn-sim-start"
          >
            Start Simulation
          </button>
          <button
            type="button"
            className="btn btn-small"
            onClick={() => { setPaused(true); toast('warn', 'Đã tạm dừng chuyển động 2D (WebSocket vẫn nhận sự kiện)', { scope: 'admin' }); }}
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
      </div>

      {simError && !USE_MOCK && (
        <div className="banner banner-warn" style={{ marginTop: 10 }} data-testid="sim-error-banner">
          <span><strong>Simulator chưa sẵn sàng:</strong> {simError}. Các nút giả lập phần cứng (quét, pin, cân, mất mạng) tạm vô hiệu, bản đồ vẫn hiển thị dữ liệu thực từ Backend.</span>
          <button type="button" className="btn btn-small" onClick={loadSim}>Thử lại</button>
        </div>
      )}

      {/* Bố cục Cockpit 3 cột */}
      <div className="sim2d-cockpit">
        {/* Cột trái: Danh sách đội xe */}
        <aside className="card sim2d-fleet" data-testid="fleet-panel">
          <div className="sim2d-card-head">
            <h3>Đội xe ({effectiveCarts.length})</h3>
            <span className="muted small">Chọn xe</span>
          </div>
          <div className="sim2d-fleet-list">
            {effectiveCarts.map(({ cart_id, backend, sim }) => {
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
            {effectiveCarts.length === 0 && (
              <div className="muted small" style={{ padding: '12px 0' }}>Chưa có xe đẩy nào được đăng ký.</div>
            )}
          </div>
        </aside>

        {/* Cột giữa: Không gian mô phỏng Siêu thị (3D Digital Twin hoặc 2D Mặt bằng) */}
        <div className="card sim2d-map-card" style={{ padding: viewDimension === '3d' ? 0 : undefined, overflow: 'hidden', background: '#0f172a' }}>
          {viewDimension === '3d' ? (
            <Supermarket3D
              carts={effectiveCarts}
              selectedId={selectedId}
              onSelectCart={setSelectedId}
              onTargetZoneSelect={(zId) => {
                setTargetZone(zId);
                moveCartToZone(selectedId, zId);
              }}
              positions={positions}
              checkoutFlags={checkoutFlags}
            />
          ) : (
            <SupermarketMap
              cartsList={effectiveCarts}
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
          )}
        </div>

        {/* Cột phải: Chi tiết xe + Kịch bản IoT */}
        <aside className="sim2d-right">
          <div className="card sim2d-inspector" data-testid="inspector-panel">
            <div className="sim2d-card-head">
              <div>
                <h3 className="mono" style={{ margin: 0, fontSize: '1.08rem' }} data-testid="inspector-cart-id">{selectedId}</h3>
                <div className="muted small">Khu vực 2D: <strong>{selZone?.label || 'Lối vào'}</strong></div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end', alignItems: 'center' }}>
                <ConnBadge status={selConn} />
                {!isCartOnline(selectedId) && writable && (
                  <button
                    type="button"
                    className="btn btn-small btn-ok"
                    style={{ fontSize: '0.74rem', padding: '2px 8px', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    onClick={() => handleConnection(true)}
                    disabled={Boolean(busyAction)}
                    data-testid="btn-quick-reconnect"
                    title="Kết nối lại xe với Server (MQTT + Backend)"
                  >
                    🔌 Kết nối lại
                  </button>
                )}
                <Badge tone={CART_STATUS[selStatus]?.tone}>{CART_STATUS[selStatus]?.label || selStatus}</Badge>
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
          </div>

          <div className="card sim2d-controls" data-testid="sim-controls">
            <div className="sim2d-card-head">
              <h3>Điều khiển kịch bản IoT</h3>
              {busyAction && <span className="muted small">Đang xử lý...</span>}
            </div>

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
                  disabled={!isCartOnline(selectedId) || Boolean(busyAction)}
                  title={isCartOnline(selectedId) ? 'Di chuyển xe' : 'Xe đang OFFLINE tại bãi xe. Hãy bấm "Bắt đầu phiên" để kích hoạt xe trước khi di chuyển!'}
                  data-testid="btn-move-cart"
                >
                  Di chuyển xe
                </button>
              </div>
              {!isCartOnline(selectedId) && (
                <div className="small" style={{ marginTop: 6, padding: '6px 10px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid #f59e0b', borderRadius: 6, color: '#f59e0b', fontSize: '0.78rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
                  <span>⚠️ Xe {selectedId} đang <b>OFFLINE</b> tại bãi xe. Bấm <b>Bắt đầu phiên</b> hoặc kết nối lại để sử dụng.</span>
                  {writable && (
                    <button
                      type="button"
                      className="btn btn-small btn-ok"
                      style={{ padding: '2px 8px', fontSize: '0.74rem' }}
                      onClick={() => handleConnection(true)}
                      disabled={Boolean(busyAction)}
                      data-testid="btn-banner-reconnect"
                      title="Kết nối lại xe ngay với Server"
                    >
                      🔌 Kết nối server ngay
                    </button>
                  )}
                </div>
              )}
            </div>

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
              {/* Khu vực nhận diện quầy hàng & Lọc vật phẩm */}
              <div style={{ marginTop: 8, padding: '8px 10px', background: 'var(--bg-subtle, #f8fafc)', borderRadius: 6, border: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--fg)' }}>
                    📍 Quầy: <span style={{ color: 'var(--primary, #059669)' }}>{activeZoneObj?.label || activeZone}</span>
                    {isRetailZone ? (
                      <span className="muted" style={{ fontWeight: 400 }}> ({displayedProducts.length} món)</span>
                    ) : (
                      <span className="muted" style={{ fontWeight: 400 }}> (Chưa vào quầy)</span>
                    )}
                  </span>
                  <label style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', userSelect: 'none', color: 'var(--muted)' }} title="Chỉ hiện sản phẩm tại quầy xe đang đỗ">
                    <input
                      type="checkbox"
                      checked={filterByZone}
                      onChange={(e) => setFilterByZone(e.target.checked)}
                      data-testid="toggle-filter-zone"
                    />
                    Lọc theo quầy
                  </label>
                </div>

                {/* Các nút chuyển nhanh quầy hàng */}
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
                  <button
                    type="button"
                    className={`btn btn-small ${activeZone === 'beverage' ? 'btn-primary' : ''}`}
                    style={{ fontSize: '0.75rem', padding: '2px 7px' }}
                    onClick={() => moveCartToZone(selectedId, 'beverage')}
                    disabled={!isCartOnline(selectedId)}
                    title={isCartOnline(selectedId) ? 'Đến quầy Đồ uống & Sữa' : 'Xe đang OFFLINE. Cần bắt đầu phiên trước!'}
                    data-testid="btn-goto-beverage"
                  >
                    🥤 Đồ uống
                  </button>
                  <button
                    type="button"
                    className={`btn btn-small ${activeZone === 'grocery' ? 'btn-primary' : ''}`}
                    style={{ fontSize: '0.75rem', padding: '2px 7px' }}
                    onClick={() => moveCartToZone(selectedId, 'grocery')}
                    disabled={!isCartOnline(selectedId)}
                    title={isCartOnline(selectedId) ? 'Đến quầy Thực phẩm khô' : 'Xe đang OFFLINE. Cần bắt đầu phiên trước!'}
                    data-testid="btn-goto-grocery"
                  >
                    🍜 Thực phẩm
                  </button>
                  <button
                    type="button"
                    className={`btn btn-small ${activeZone === 'household' ? 'btn-primary' : ''}`}
                    style={{ fontSize: '0.75rem', padding: '2px 7px' }}
                    onClick={() => moveCartToZone(selectedId, 'household')}
                    disabled={!isCartOnline(selectedId)}
                    title={isCartOnline(selectedId) ? 'Đến quầy Gia dụng' : 'Xe đang OFFLINE. Cần bắt đầu phiên trước!'}
                    data-testid="btn-goto-household"
                  >
                    🧼 Gia dụng
                  </button>
                  <button
                    type="button"
                    className={`btn btn-small ${activeZone === 'personal_care' ? 'btn-primary' : ''}`}
                    style={{ fontSize: '0.75rem', padding: '2px 7px' }}
                    onClick={() => moveCartToZone(selectedId, 'personal_care')}
                    disabled={!isCartOnline(selectedId)}
                    title={isCartOnline(selectedId) ? 'Đến quầy Chăm sóc cá nhân' : 'Xe đang OFFLINE. Cần bắt đầu phiên trước!'}
                    data-testid="btn-goto-personal"
                  >
                    🪥 Cá nhân
                  </button>
                </div>

                <div className="sim2d-ctrl-row">
                  <select
                    value={selectedBarcode}
                    onChange={(e) => {
                      setSelectedBarcode(e.target.value);
                      const prod = catalog.find((p) => p.barcode === e.target.value);
                      if (prod && !isRetailZone) {
                        moveCartToZone(selectedId, inferZoneForProduct(prod));
                      }
                    }}
                    data-testid="select-product"
                    style={{ width: '100%' }}
                  >
                    {displayedProducts.map((p) => (
                      <option key={p.barcode} value={p.barcode}>
                        {p.name} ({vnd(p.price)} · {p.unit_weight ?? p.weight ?? 0}g)
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="sim2d-btn-grid" style={{ marginTop: 6 }}>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={handleScanAdd}
                  disabled={hardwareDisabled}
                  data-testid="btn-scan-add"
                >
                  Quét & Thêm
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={handleScanRemove}
                  disabled={hardwareDisabled}
                  data-testid="btn-scan-remove"
                >
                  Bỏ 1 món
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  onClick={handleScanUnknown}
                  disabled={hardwareDisabled}
                  data-testid="btn-scan-unknown"
                >
                  Quét mã lạ
                </button>
              </div>
            </div>

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
                  disabled={Boolean(simError) || !writable}
                  aria-label="Mức pin mô phỏng"
                  style={{ flex: 1 }}
                />
                <span className="mono small" style={{ minWidth: 38, textAlign: 'right' }}>{batteryInput}%</span>
              </div>
              <div className="sim2d-btn-grid" style={{ marginTop: 6 }}>
                <button type="button" className="btn btn-small" onClick={() => handleSetBattery(15)} disabled={hardwareDisabled} data-testid="btn-low-battery">Pin 15%</button>
                <button type="button" className="btn btn-small" onClick={() => handleSetBattery(100)} disabled={hardwareDisabled} data-testid="btn-full-battery">Sạc 100%</button>
                <button type="button" className="btn btn-small" onClick={() => handleWeightOffset(250)} disabled={hardwareDisabled} data-testid="btn-weight-mismatch">Lệch cân +250g</button>
                <button type="button" className="btn btn-small" onClick={() => handleWeightOffset(0)} disabled={hardwareDisabled} data-testid="btn-weight-reset">Cân chuẩn 0g</button>
                <button type="button" className="btn btn-small" onClick={() => handleConnection(false)} disabled={hardwareDisabled} data-testid="btn-trigger-offline">Ngắt mạng</button>
                <button type="button" className="btn btn-small" onClick={() => handleConnection(true)} disabled={hardwareDisabled} data-testid="btn-trigger-reconnect">Kết nối lại</button>
              </div>
            </div>
          </div>
        </aside>
      </div>

      {/* Live Event Log từ WebSocket */}
      <div className="card sim2d-eventlog" data-testid="live-event-log">
        <div className="sim2d-card-head">
          <h3>Live Event Log (WebSocket Realtime)</h3>
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
      </div>
    </section>
  );
}
