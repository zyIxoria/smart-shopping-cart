import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import {
  COUNTERS,
  MAP_H,
  MAP_W,
  SHELVES,
  WAYPOINTS,
  ZONES,
  zoneById,
} from './floorPlan.js';
import { cartVisualState } from './SupermarketMap.jsx';

// Hệ số chuyển đổi toạ độ 2D (1000x620) sang không gian 3D
// Gốc toạ độ (0, 0, 0) ở giữa sàn siêu thị
const SCALE = 0.1;
const to3Dx = (x) => (x - MAP_W / 2) * SCALE;
const to3Dz = (y) => (y - MAP_H / 2) * SCALE;

// Vẽ texture nhãn chữ sắc nét bằng HTML5 Canvas cho biển khu vực và nhãn xe
function createTextBadgeTexture(title, subtitle, bgColor = '#1e293b', fgColor = '#f8fafc', borderColor = '#38bdf8') {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 160;
  const ctx = canvas.getContext('2d');

  // Nền bo góc
  ctx.fillStyle = bgColor;
  ctx.strokeStyle = borderColor;
  ctx.lineWidth = 6;
  ctx.beginPath();
  ctx.roundRect(10, 10, 492, 140, 24);
  ctx.fill();
  ctx.stroke();

  // Tiêu đề
  ctx.fillStyle = fgColor;
  ctx.font = 'bold 44px Inter, system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(title, 256, subtitle ? 60 : 80);

  // Phụ đề (nếu có)
  if (subtitle) {
    ctx.fillStyle = borderColor;
    ctx.font = '600 28px Inter, system-ui, sans-serif';
    ctx.fillText(subtitle, 256, 112);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

// Tạo texture nhãn xe nổi trên đầu xe đẩy
function createCartBadgeTexture(cartId, battery, visual) {
  const canvas = document.createElement('canvas');
  canvas.width = 384;
  canvas.height = 144;
  const ctx = canvas.getContext('2d');

  // Nền card
  ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
  ctx.strokeStyle = visual.color || '#10b981';
  ctx.lineWidth = 5;
  ctx.beginPath();
  ctx.roundRect(8, 8, 368, 128, 20);
  ctx.fill();
  ctx.stroke();

  // Chấm tròn trạng thái
  ctx.fillStyle = visual.color || '#10b981';
  ctx.beginPath();
  ctx.arc(44, 46, 14, 0, Math.PI * 2);
  ctx.fill();

  // Cart ID
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 36px monospace, sans-serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText(cartId, 72, 46);

  // Pin & Trạng thái
  const batPct = Math.round(battery ?? 100);
  const batColor = batPct < 20 ? '#ef4444' : batPct < 50 ? '#f59e0b' : '#10b981';
  ctx.fillStyle = batColor;
  ctx.font = '600 24px monospace, sans-serif';
  ctx.fillText(`🔋 ${batPct}%`, 28, 102);

  ctx.fillStyle = visual.color || '#94a3b8';
  ctx.font = 'bold 22px system-ui, sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText(visual.label || 'Sẵn sàng', 356, 102);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export default function Supermarket3D({
  carts = [],
  selectedId = 'CART_001',
  onSelectCart,
  onTargetZoneSelect,
  positions = {},
  checkoutFlags = {},
}) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);
  const cartMeshesRef = useRef({});
  const raycasterRef = useRef(new THREE.Raycaster());
  const mouseRef = useRef(new THREE.Vector2());

  const [followCart, setFollowCart] = useState(false);
  const [cameraMode, setCameraMode] = useState('isometric'); // 'isometric' | 'topdown' | 'follow'
  const [dragMode, setDragMode] = useState('pan'); // 'pan' (mặc định cho phép kéo di chuyển bằng chuột trái) | 'rotate'
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Khởi tạo Three.js Scene, Camera, Renderer, Lighting và OrbitControls
  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || 900;
    const height = container.clientHeight || 700;

    // 1. Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#0b1120');
    scene.fog = new THREE.FogExp2('#0b1120', 0.005);
    sceneRef.current = scene;

    // 2. Camera Isometric (gần hơn để mô hình to và rõ nét)
    const aspect = width / height;
    const camera = new THREE.PerspectiveCamera(38, aspect, 0.5, 300);
    camera.position.set(0, 42, 46);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    // 3. Renderer với khử răng cưa
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    rendererRef.current = renderer;
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // 4. OrbitControls hỗ trợ Pan di chuyển mượt mà
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.maxPolarAngle = Math.PI / 2 - 0.06; // Không cho camera chìm xuống sàn
    controls.minDistance = 10;
    controls.maxDistance = 140;
    controls.enablePan = true;
    controls.screenSpacePanning = true; // Di chuyển theo mặt phẳng màn hình cực kỳ tự nhiên
    controls.panSpeed = 1.25;
    controls.rotateSpeed = 0.9;
    controls.target.set(0, 0, 0);

    // Cấu hình chuột: dragMode 'pan' cho phép kéo chuột trái để di chuyển mô hình
    controls.mouseButtons = {
      LEFT: THREE.MOUSE.PAN,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.ROTATE,
    };
    controlsRef.current = controls;

    // 5. Hệ thống ánh sáng siêu thị
    const ambientLight = new THREE.AmbientLight('#ffffff', 0.9);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight('#fffaf0', 1.4);
    dirLight.position.set(30, 50, 40);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
    dirLight.shadow.camera.near = 10;
    dirLight.shadow.camera.far = 140;
    dirLight.shadow.camera.left = -60;
    dirLight.shadow.camera.right = 60;
    dirLight.shadow.camera.top = 45;
    dirLight.shadow.camera.bottom = -45;
    dirLight.shadow.bias = -0.0005;
    scene.add(dirLight);

    const fillLight = new THREE.DirectionalLight('#93c5fd', 0.55);
    fillLight.position.set(-35, 30, -30);
    scene.add(fillLight);

    // 6. Xây dựng không gian siêu thị 3D
    buildSupermarketEnvironment(scene);

    // 7. Raycasting tương tác click chuột
    let dragDistance = 0;
    let downPos = { x: 0, y: 0 };

    const handlePointerDown = (e) => {
      downPos = { x: e.clientX, y: e.clientY };
      dragDistance = 0;
    };

    const handlePointerMove = (e) => {
      dragDistance += Math.hypot(e.clientX - downPos.x, e.clientY - downPos.y);
      downPos = { x: e.clientX, y: e.clientY };
    };

    const handlePointerUp = (e) => {
      // Chỉ kích hoạt chọn xe/khu vực nếu người dùng click nhẹ, không kích hoạt khi đang kéo di chuyển (drag)
      if (dragDistance > 6) return;

      const rect = renderer.domElement.getBoundingClientRect();
      mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouseRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      raycasterRef.current.setFromCamera(mouseRef.current, camera);
      const intersects = raycasterRef.current.intersectObjects(scene.children, true);

      for (const hit of intersects) {
        let curr = hit.object;
        while (curr && curr !== scene) {
          if (curr.userData?.cartId) {
            onSelectCart?.(curr.userData.cartId);
            return;
          }
          if (curr.userData?.zoneId) {
            onTargetZoneSelect?.(curr.userData.zoneId);
            return;
          }
          curr = curr.parent;
        }
      }
    };

    renderer.domElement.addEventListener('pointerdown', handlePointerDown);
    renderer.domElement.addEventListener('pointermove', handlePointerMove);
    renderer.domElement.addEventListener('pointerup', handlePointerUp);

    // 8. Hỗ trợ phím mũi tên di chuyển không gian 3D
    const handleKeyDown = (e) => {
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'KeyW', 'KeyS', 'KeyA', 'KeyD'].includes(e.code)) {
        e.preventDefault();
        const step = 4;
        if (e.code === 'ArrowUp' || e.code === 'KeyW') moveModel(0, -step);
        if (e.code === 'ArrowDown' || e.code === 'KeyS') moveModel(0, step);
        if (e.code === 'ArrowLeft' || e.code === 'KeyA') moveModel(-step, 0);
        if (e.code === 'ArrowRight' || e.code === 'KeyD') moveModel(step, 0);
      }
      if (e.code === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    // 9. Vòng lặp Render (Animation Frame)
    let animId = 0;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // 10. Resize Handler
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('keydown', handleKeyDown);
      renderer.domElement.removeEventListener('pointerdown', handlePointerDown);
      renderer.domElement.removeEventListener('pointermove', handlePointerMove);
      renderer.domElement.removeEventListener('pointerup', handlePointerUp);
      renderer.dispose();
      controls.dispose();
    };
  }, []);

  // Cập nhật chế độ kéo chuột (Left Mouse Drag: Pan hoặc Rotate)
  useEffect(() => {
    if (!controlsRef.current) return;
    if (dragMode === 'pan') {
      controlsRef.current.mouseButtons = {
        LEFT: THREE.MOUSE.PAN,
        MIDDLE: THREE.MOUSE.DOLLY,
        RIGHT: THREE.MOUSE.ROTATE,
      };
    } else {
      controlsRef.current.mouseButtons = {
        LEFT: THREE.MOUSE.ROTATE,
        MIDDLE: THREE.MOUSE.DOLLY,
        RIGHT: THREE.MOUSE.PAN,
      };
    }
  }, [dragMode]);

  // Cập nhật kích thước khi bật/tắt toàn màn hình
  useEffect(() => {
    const timer = setTimeout(() => {
      if (mountRef.current && rendererRef.current && cameraRef.current) {
        const w = mountRef.current.clientWidth;
        const h = mountRef.current.clientHeight;
        cameraRef.current.aspect = w / h;
        cameraRef.current.updateProjectionMatrix();
        rendererRef.current.setSize(w, h);
      }
    }, 60);
    return () => clearTimeout(timer);
  }, [isFullscreen]);

  // Cập nhật vị trí, trạng thái và hiệu ứng của các xe đẩy 3D trong Scene
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;

    const existingMeshIds = new Set(Object.keys(cartMeshesRef.current));
    const currentCarts = carts.map((c) => c.cart_id);

    // Xoá xe không còn tồn tại
    existingMeshIds.forEach((id) => {
      if (!currentCarts.includes(id)) {
        scene.remove(cartMeshesRef.current[id]);
        delete cartMeshesRef.current[id];
      }
    });

    // Cập nhật hoặc tạo mới xe 3D
    carts.forEach((c) => {
      const cid = c.cart_id;
      const pos2D = positions[cid] || { x: 100, y: 500 };
      const targetX = to3Dx(pos2D.x);
      const targetZ = to3Dz(pos2D.y);
      const visual = cartVisualState(c.backend, c.sim, checkoutFlags[cid]);
      const battery = c.backend?.battery_percent ?? c.sim?.battery_percent ?? 100;
      const isSelected = cid === selectedId;

      let cartGroup = cartMeshesRef.current[cid];

      if (!cartGroup) {
        cartGroup = createCart3DModel(cid);
        scene.add(cartGroup);
        cartMeshesRef.current[cid] = cartGroup;
        cartGroup.position.set(targetX, 0, targetZ);
      }

      // Xoay đầu xe theo hướng di chuyển mượt mà
      const dx = targetX - cartGroup.position.x;
      const dz = targetZ - cartGroup.position.z;
      const dist = Math.hypot(dx, dz);
      if (dist > 0.05) {
        const targetRotY = Math.atan2(dx, dz);
        cartGroup.rotation.y = THREE.MathUtils.lerp(cartGroup.rotation.y, targetRotY, 0.25);
      }

      // Cập nhật vị trí mượt
      cartGroup.position.x = THREE.MathUtils.lerp(cartGroup.position.x, targetX, 0.35);
      cartGroup.position.z = THREE.MathUtils.lerp(cartGroup.position.z, targetZ, 0.35);

      // Cập nhật nhãn nổi phía trên đầu xe
      if (cartGroup.userData?.badgeSprite) {
        const badgeTex = createCartBadgeTexture(cid, battery, visual);
        cartGroup.userData.badgeSprite.material.map?.dispose();
        cartGroup.userData.badgeSprite.material.map = badgeTex;
        cartGroup.userData.badgeSprite.material.needsUpdate = true;
      }

      // Cập nhật vòng sáng hào quang bên dưới gầm xe
      if (cartGroup.userData?.auraRing) {
        cartGroup.userData.auraRing.material.color.set(visual.color || '#10b981');
      }

      // Hiệu ứng Highlight khi xe được chọn
      if (cartGroup.userData?.selectionBeam) {
        cartGroup.userData.selectionBeam.visible = isSelected;
      }
    });

    // Nếu đang bật chế độ bám theo xe đang chọn (Follow Cart)
    if (followCart && selectedId && cartMeshesRef.current[selectedId] && controlsRef.current) {
      const selCart = cartMeshesRef.current[selectedId];
      controlsRef.current.target.lerp(new THREE.Vector3(selCart.position.x, 1, selCart.position.z), 0.1);
    }
  }, [carts, positions, selectedId, checkoutFlags, followCart]);

  // Điều khiển Camera theo các góc nhìn Preset
  const setCameraPreset = (mode) => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;

    setCameraMode(mode);

    if (mode === 'isometric') {
      setFollowCart(false);
      controls.target.set(0, 0, 0);
      camera.position.set(0, 42, 46);
    } else if (mode === 'topdown') {
      setFollowCart(false);
      controls.target.set(0, 0, 0);
      camera.position.set(0, 68, 0.1);
    } else if (mode === 'follow') {
      setFollowCart(true);
      if (selectedId && cartMeshesRef.current[selectedId]) {
        const p = cartMeshesRef.current[selectedId].position;
        controls.target.set(p.x, 1, p.z);
        camera.position.set(p.x, 18, p.z + 20);
      }
    }
    controls.update();
  };

  // Di chuyển mô hình siêu thị 3D theo các hướng (Pan Offset)
  const moveModel = (dx, dz) => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;

    controls.target.x += dx;
    controls.target.z += dz;
    camera.position.x += dx;
    camera.position.z += dz;
    controls.update();
  };

  // Phóng to / thu nhỏ mô hình (Zoom in/out)
  const zoomModel = (factor) => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;

    const dir = new THREE.Vector3().subVectors(camera.position, controls.target);
    const newDist = Math.max(12, Math.min(130, dir.length() * factor));
    dir.setLength(newDist);
    camera.position.copy(controls.target).add(dir);
    controls.update();
  };

  return (
    <div
      className="sim3d-viewport"
      style={{
        position: isFullscreen ? 'fixed' : 'relative',
        inset: isFullscreen ? 0 : undefined,
        zIndex: isFullscreen ? 99999 : 1,
        width: isFullscreen ? '100vw' : '100%',
        height: isFullscreen ? '100vh' : '700px',
        borderRadius: isFullscreen ? 0 : '12px',
        overflow: 'hidden',
        border: isFullscreen ? 'none' : '1px solid #1e293b',
        boxShadow: isFullscreen ? 'none' : '0 10px 30px rgba(0, 0, 0, 0.45)',
        background: '#0b1120',
      }}
    >
      {/* Khung Canvas 3D */}
      <div ref={mountRef} style={{ width: '100%', height: '100%' }} data-testid="sim-3d-canvas" />

      {/* Top HUD Overlay: Camera Presets, Drag Mode, Fullscreen, Fleet Selector */}
      <div
        className="sim3d-toolbar-overlay"
        style={{
          position: 'absolute',
          top: 14,
          left: 14,
          right: 14,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 10,
          pointerEvents: 'none',
        }}
      >
        <div style={{ pointerEvents: 'auto', display: 'flex', gap: 6, flexWrap: 'wrap', background: 'rgba(15, 23, 42, 0.88)', backdropFilter: 'blur(10px)', padding: '6px 12px', borderRadius: '10px', border: '1px solid #334155' }}>
          <span style={{ color: '#94a3b8', fontSize: '0.85rem', display: 'inline-flex', alignItems: 'center', marginRight: 4, fontWeight: 600 }}>
            🎥 Góc nhìn:
          </span>
          <button
            type="button"
            className={`btn btn-small ${cameraMode === 'isometric' ? 'btn-primary' : ''}`}
            onClick={() => setCameraPreset('isometric')}
            data-testid="btn-camera-isometric"
          >
            Isometric
          </button>
          <button
            type="button"
            className={`btn btn-small ${cameraMode === 'topdown' ? 'btn-primary' : ''}`}
            onClick={() => setCameraPreset('topdown')}
            data-testid="btn-camera-topdown"
          >
            Nhìn từ trên
          </button>
          <button
            type="button"
            className={`btn btn-small ${cameraMode === 'follow' ? 'btn-primary' : ''}`}
            onClick={() => setCameraPreset('follow')}
            data-testid="btn-camera-follow"
          >
            Bám theo xe {selectedId}
          </button>
          <button
            type="button"
            className="btn btn-small"
            onClick={() => setCameraPreset('isometric')}
            data-testid="btn-camera-reset"
            title="Đưa camera về góc nhìn toàn cảnh ban đầu"
          >
            ↺ Đặt lại
          </button>

          <span style={{ borderLeft: '1px solid #475569', margin: '0 4px' }} />

          {/* Toggle Chế độ kéo chuột trái: Di chuyển mô hình (Pan) hoặc Xoay (Rotate) */}
          <span style={{ color: '#94a3b8', fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center' }}>Chuột trái:</span>
          <button
            type="button"
            className={`btn btn-small ${dragMode === 'pan' ? 'btn-primary' : ''}`}
            onClick={() => setDragMode('pan')}
            data-testid="btn-drag-pan"
            title="Kéo chuột trái để di chuyển mô hình tự do"
            style={{ fontWeight: 600 }}
          >
            ✋ Di chuyển (Pan)
          </button>
          <button
            type="button"
            className={`btn btn-small ${dragMode === 'rotate' ? 'btn-primary' : ''}`}
            onClick={() => setDragMode('rotate')}
            data-testid="btn-drag-rotate"
            title="Kéo chuột trái để xoay 360 độ quanh tâm"
            style={{ fontWeight: 600 }}
          >
            🔄 Xoay góc
          </button>
        </div>

        {/* Nút Phóng to Toàn màn hình & Bộ nút Di chuyển Pan / Zoom */}
        <div style={{ pointerEvents: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
          {/* Bộ nút Pan & Zoom nhanh */}
          <div style={{ display: 'flex', gap: 3, background: 'rgba(15, 23, 42, 0.88)', backdropFilter: 'blur(10px)', padding: '5px 8px', borderRadius: '10px', border: '1px solid #334155' }}>
            <button type="button" className="btn btn-small" onClick={() => moveModel(-6, 0)} title="Di chuyển sang trái" style={{ padding: '2px 7px' }}>◄</button>
            <button type="button" className="btn btn-small" onClick={() => moveModel(0, -6)} title="Di chuyển lên trên" style={{ padding: '2px 7px' }}>▲</button>
            <button type="button" className="btn btn-small" onClick={() => moveModel(0, 6)} title="Di chuyển xuống dưới" style={{ padding: '2px 7px' }}>▼</button>
            <button type="button" className="btn btn-small" onClick={() => moveModel(6, 0)} title="Di chuyển sang phải" style={{ padding: '2px 7px' }}>►</button>
            <span style={{ borderLeft: '1px solid #475569', margin: '0 3px' }} />
            <button type="button" className="btn btn-small" onClick={() => zoomModel(0.85)} title="Phóng to gần hơn" style={{ padding: '2px 7px', fontWeight: 'bold' }}>＋</button>
            <button type="button" className="btn btn-small" onClick={() => zoomModel(1.18)} title="Thu nhỏ xa hơn" style={{ padding: '2px 7px', fontWeight: 'bold' }}>－</button>
          </div>

          {/* Nút Toàn màn hình */}
          <button
            type="button"
            className={`btn ${isFullscreen ? 'btn-primary' : ''}`}
            onClick={() => setIsFullscreen(!isFullscreen)}
            data-testid="btn-fullscreen-toggle"
            style={{
              background: isFullscreen ? '#0284c7' : 'rgba(15, 23, 42, 0.92)',
              border: '1px solid #38bdf8',
              color: '#ffffff',
              padding: '6px 14px',
              fontSize: '0.88rem',
              fontWeight: 700,
              boxShadow: '0 4px 12px rgba(2, 132, 199, 0.35)',
            }}
            title={isFullscreen ? 'Thu nhỏ cửa sổ (Esc)' : 'Mở rộng mô hình 3D toàn màn hình'}
          >
            {isFullscreen ? '✕ Thu nhỏ (Esc)' : '⛶ Phóng to toàn màn hình'}
          </button>
        </div>
      </div>

      {/* Bottom Overlay: Điều hướng nhanh các khu vực siêu thị 3D & Đội xe */}
      <div
        style={{
          position: 'absolute',
          bottom: 14,
          left: 14,
          right: 14,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 10,
          pointerEvents: 'none',
        }}
      >
        {/* Nút chọn điểm đến 3D */}
        <div style={{ pointerEvents: 'auto', display: 'flex', gap: 6, flexWrap: 'wrap', background: 'rgba(15, 23, 42, 0.92)', backdropFilter: 'blur(10px)', padding: '7px 12px', borderRadius: '10px', border: '1px solid #334155' }}>
          <span style={{ color: '#38bdf8', fontSize: '0.84rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', marginRight: 4 }}>
            📍 Điểm đến 3D:
          </span>
          {ZONES.map((z) => (
            <button
              key={z.id}
              type="button"
              className="chip-btn"
              onClick={() => onTargetZoneSelect?.(z.id)}
              data-testid={`map-zone-${z.id}`}
              style={{ padding: '3px 9px', fontSize: '0.8rem', background: '#1e293b', border: '1px solid #334155', color: '#f8fafc' }}
              title={`Điều hướng xe ${selectedId} tới ${z.label}`}
            >
              {z.label}
            </button>
          ))}
        </div>

        {/* Quick Cart HUD Selector */}
        <div style={{ pointerEvents: 'auto', display: 'flex', gap: 6, flexWrap: 'wrap', background: 'rgba(15, 23, 42, 0.92)', backdropFilter: 'blur(10px)', padding: '7px 12px', borderRadius: '10px', border: '1px solid #334155' }}>
          <span style={{ color: '#94a3b8', fontSize: '0.84rem', display: 'inline-flex', alignItems: 'center', fontWeight: 600 }}>
            🛒 Đội xe 3D:
          </span>
          {carts.map((c) => {
            const cid = c.cart_id;
            const isSel = cid === selectedId;
            const vis = cartVisualState(c.backend, c.sim, checkoutFlags[cid]);
            const itemCount = c.backend?.session?.item_count ?? (c.sim?.basket?.reduce((s, i) => s + i.quantity, 0) || 0);
            return (
              <button
                key={cid}
                type="button"
                className={`btn btn-small ${isSel ? 'btn-primary' : ''}`}
                onClick={() => onSelectCart?.(cid)}
                data-testid={`map-cart-${cid}`}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px', fontSize: '0.8rem' }}
                title={`Chọn xe ${cid} trên không gian 3D`}
              >
                <i className="leg-dot" style={{ background: vis.color, width: 8, height: 8 }} />
                <span>{cid}</span>
                {itemCount > 0 && <span style={{ opacity: 0.85 }}>({itemCount} món)</span>}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// XÂY DỰNG KHÔNG GIAN SIÊU THỊ 3D (Floor, Wall, Zones, Shelves, Counters, Signs)
// -----------------------------------------------------------------------------
function buildSupermarketEnvironment(scene) {
  // 1. Sàn chính siêu thị (Gạch lát bóng hiện đại)
  const floorW = MAP_W * SCALE;
  const floorH = MAP_H * SCALE;
  const floorGeo = new THREE.PlaneGeometry(floorW, floorH);
  const floorMat = new THREE.MeshStandardMaterial({
    color: '#0f172a',
    roughness: 0.65,
    metalness: 0.15,
  });
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  // Lưới gạch lát sàn siêu thị (Grid lines)
  const grid = new THREE.GridHelper(Math.max(floorW, floorH), 40, '#334155', '#1e293b');
  grid.position.y = 0.01;
  scene.add(grid);

  // 2. Viền tường bảo vệ siêu thị (Kính mica trong suốt hiện đại)
  const wallH = 1.8;
  const wallMat = new THREE.MeshStandardMaterial({
    color: '#38bdf8',
    transparent: true,
    opacity: 0.22,
    roughness: 0.1,
    metalness: 0.5,
  });

  // Tường Bắc/Nam
  const wallHGeo = new THREE.BoxGeometry(floorW + 0.4, wallH, 0.3);
  const wallN = new THREE.Mesh(wallHGeo, wallMat);
  wallN.position.set(0, wallH / 2, -floorH / 2);
  scene.add(wallN);

  const wallS = new THREE.Mesh(wallHGeo, wallMat);
  wallS.position.set(0, wallH / 2, floorH / 2);
  scene.add(wallS);

  // Tường Tây/Đông
  const wallVGeo = new THREE.BoxGeometry(0.3, wallH, floorH);
  const wallW = new THREE.Mesh(wallVGeo, wallMat);
  wallW.position.set(-floorW / 2, wallH / 2, 0);
  scene.add(wallW);

  const wallE = new THREE.Mesh(wallVGeo, wallMat);
  wallE.position.set(floorW / 2, wallH / 2, 0);
  scene.add(wallE);

  // 3. Các phân vùng mặt sàn (Zones plates & viền màu)
  const zoneColors = {
    grocery: '#10b981',
    beverage: '#3b82f6',
    household: '#f59e0b',
    personal_care: '#8b5cf6',
    checkout: '#06b6d4',
    entrance: '#059669',
    exit: '#64748b',
  };

  ZONES.forEach((z) => {
    const zw = z.w * SCALE;
    const zh = z.h * SCALE;
    const zx = to3Dx(z.x + z.w / 2);
    const zz = to3Dz(z.y + z.h / 2);
    const col = zoneColors[z.id] || '#64748b';

    // Mặt đệm sàn khu vực
    const plateGeo = new THREE.PlaneGeometry(zw - 0.2, zh - 0.2);
    const plateMat = new THREE.MeshStandardMaterial({
      color: col,
      transparent: true,
      opacity: 0.12,
      roughness: 0.7,
    });
    const plate = new THREE.Mesh(plateGeo, plateMat);
    plate.rotation.x = -Math.PI / 2;
    plate.position.set(zx, 0.02, zz);
    plate.userData = { zoneId: z.id, zoneLabel: z.label };
    scene.add(plate);

    // Đường viền vi tính khu vực
    const edgesGeo = new THREE.EdgesGeometry(new THREE.BoxGeometry(zw, 0.06, zh));
    const edgesMat = new THREE.LineBasicMaterial({ color: col, linewidth: 2 });
    const edges = new THREE.LineSegments(edgesGeo, edgesMat);
    edges.position.set(zx, 0.03, zz);
    scene.add(edges);

    // Biển tên phân vùng treo lơ lửng 3D
    const badgeTex = createTextBadgeTexture(z.label, z.en, '#0f172a', '#ffffff', col);
    const spriteMat = new THREE.SpriteMaterial({ map: badgeTex, transparent: true });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(10, 3.2, 1);
    sprite.position.set(zx, 7.8, zz);
    sprite.userData = { zoneId: z.id };
    scene.add(sprite);

    // Trụ treo biển từ trần xuống
    const postGeo = new THREE.CylinderGeometry(0.04, 0.04, 3.5, 8);
    const postMat = new THREE.MeshStandardMaterial({ color: '#475569', metalness: 0.8 });
    const post = new THREE.Mesh(postGeo, postMat);
    post.position.set(zx, 9.5, zz);
    scene.add(post);
  });

  // 4. Các dãy kệ hàng (Shelves & Sản phẩm nhiều màu sắc)
  SHELVES.forEach((s) => {
    const sw = s.w * SCALE;
    const sh = s.h * SCALE;
    const sx = to3Dx(s.x + s.w / 2);
    const sz = to3Dz(s.y + s.h / 2);

    const shelfGroup = createGondolaShelf(sw, sh, s.zone);
    shelfGroup.position.set(sx, 0, sz);
    scene.add(shelfGroup);
  });

  // 5. Quầy thanh toán (Checkout Counters)
  COUNTERS.forEach((q, idx) => {
    const qw = q.w * SCALE;
    const qh = q.h * SCALE;
    const qx = to3Dx(q.x + q.w / 2);
    const qz = to3Dz(q.y + q.h / 2);

    const counterMesh = createCheckoutCounter(qw, qh, idx + 1);
    counterMesh.position.set(qx, 0, qz);
    scene.add(counterMesh);
  });
}

// -----------------------------------------------------------------------------
// TẠO MÔ HÌNH DÃY KỆ HÀNG GONDOLA VỚI 3 TẦNG SẢN PHẨM SẮC MÀU
// -----------------------------------------------------------------------------
function createGondolaShelf(width, depth, zone) {
  const group = new THREE.Group();
  const shelfHeight = 4.2;

  // 1. Khung kệ kim loại chính
  const metalMat = new THREE.MeshStandardMaterial({ color: '#334155', metalness: 0.6, roughness: 0.4 });
  const shelfMat = new THREE.MeshStandardMaterial({ color: '#e2e8f0', metalness: 0.2, roughness: 0.6 });

  // Vách ngăn trung tâm
  const backGeo = new THREE.BoxGeometry(width, shelfHeight, 0.2);
  const back = new THREE.Mesh(backGeo, metalMat);
  back.position.y = shelfHeight / 2;
  back.castShadow = true;
  group.add(back);

  // 2 trụ hồi 2 đầu
  const postGeo = new THREE.BoxGeometry(0.35, shelfHeight, depth);
  const post1 = new THREE.Mesh(postGeo, metalMat);
  post1.position.set(-width / 2, shelfHeight / 2, 0);
  post1.castShadow = true;
  group.add(post1);

  const post2 = new THREE.Mesh(postGeo, metalMat);
  post2.position.set(width / 2, shelfHeight / 2, 0);
  post2.castShadow = true;
  group.add(post2);

  // 3 tầng đợt kệ (Đáy, Giữa, Đỉnh)
  const levels = [0.4, 1.8, 3.2];
  levels.forEach((lvlY) => {
    const tierGeo = new THREE.BoxGeometry(width - 0.4, 0.15, depth - 0.2);
    const tier = new THREE.Mesh(tierGeo, shelfMat);
    tier.position.y = lvlY;
    tier.receiveShadow = true;
    group.add(tier);

    // Đặt các hộp/chai sản phẩm nhiều màu sắc lên từng tầng
    addProductsOnTier(group, width - 0.8, depth - 0.4, lvlY + 0.15, zone);
  });

  return group;
}

// Thêm các hộp/chai sản phẩm low-poly lên tầng kệ
function addProductsOnTier(group, spanW, spanD, baseY, zone) {
  const palette = {
    grocery: ['#ef4444', '#f59e0b', '#eab308', '#10b981'],
    beverage: ['#3b82f6', '#06b6d4', '#0284c7', '#22c55e'],
    household: ['#14b8a6', '#f97316', '#6366f1', '#ec4899'],
    personal_care: ['#8b5cf6', '#a855f7', '#d946ef', '#f43f5e'],
  }[zone] || ['#3b82f6', '#ef4444', '#f59e0b'];

  const rows = [-spanD / 4, spanD / 4];
  const itemsPerRow = Math.floor(spanW / 0.9);

  rows.forEach((zOffset) => {
    for (let i = 0; i < itemsPerRow; i++) {
      const col = palette[(i + Math.floor(Math.abs(zOffset * 10))) % palette.length];
      const isBottle = zone === 'beverage' || zone === 'personal_care';
      const itemH = 0.6 + (i % 3) * 0.15;

      let geo;
      if (isBottle) {
        geo = new THREE.CylinderGeometry(0.18, 0.2, itemH, 6);
      } else {
        geo = new THREE.BoxGeometry(0.38, itemH, 0.38);
      }
      const mat = new THREE.MeshStandardMaterial({ color: col, roughness: 0.5 });
      const mesh = new THREE.Mesh(geo, mat);
      const x = -spanW / 2 + (i + 0.5) * (spanW / itemsPerRow);
      mesh.position.set(x, baseY + itemH / 2, zOffset);
      mesh.castShadow = true;
      group.add(mesh);
    }
  });
}

// -----------------------------------------------------------------------------
// TẠO QUẦY THU NGÂN (Checkout Counter)
// -----------------------------------------------------------------------------
function createCheckoutCounter(width, depth, num) {
  const group = new THREE.Group();

  // Bàn thu ngân chính
  const deskGeo = new THREE.BoxGeometry(width, 1.4, depth);
  const deskMat = new THREE.MeshStandardMaterial({ color: '#1e293b', roughness: 0.4 });
  const desk = new THREE.Mesh(deskGeo, deskMat);
  desk.position.y = 0.7;
  desk.castShadow = true;
  desk.receiveShadow = true;
  group.add(desk);

  // Băng chuyền cao su màu đen
  const beltGeo = new THREE.BoxGeometry(width - 0.4, 0.08, depth - 0.6);
  const beltMat = new THREE.MeshStandardMaterial({ color: '#090d16', roughness: 0.9 });
  const belt = new THREE.Mesh(beltGeo, beltMat);
  belt.position.y = 1.44;
  group.add(belt);

  // Màn hình POS thu ngân
  const posGeo = new THREE.BoxGeometry(0.7, 0.5, 0.1);
  const posMat = new THREE.MeshStandardMaterial({ color: '#38bdf8', emissive: '#0284c7', emissiveIntensity: 0.4 });
  const pos = new THREE.Mesh(posGeo, posMat);
  pos.position.set(width / 4, 1.85, 0);
  pos.rotation.y = -Math.PI / 6;
  group.add(pos);

  // Chân đế màn hình
  const standGeo = new THREE.CylinderGeometry(0.06, 0.06, 0.45, 8);
  const standMat = new THREE.MeshStandardMaterial({ color: '#94a3b8' });
  const stand = new THREE.Mesh(standGeo, standMat);
  stand.position.set(width / 4, 1.55, 0);
  group.add(stand);

  return group;
}

// -----------------------------------------------------------------------------
// TẠO MÔ HÌNH XE ĐẨY THÔNG MINH 3D (Smart Shopping Cart 3D Model)
// -----------------------------------------------------------------------------
function createCart3DModel(cartId) {
  const group = new THREE.Group();
  group.userData = { cartId };

  const cartScale = 0.82;
  const chromeMat = new THREE.MeshStandardMaterial({ color: '#cbd5e1', metalness: 0.8, roughness: 0.2 });
  const wireMat = new THREE.MeshStandardMaterial({ color: '#94a3b8', metalness: 0.6, roughness: 0.3, wireframe: true });
  const blackMat = new THREE.MeshStandardMaterial({ color: '#0f172a', roughness: 0.8 });
  const screenMat = new THREE.MeshStandardMaterial({ color: '#22c55e', emissive: '#16a34a', emissiveIntensity: 0.6 });

  // 1. Khung gầm xe đẩy (Chassis)
  const baseGeo = new THREE.BoxGeometry(1.6 * cartScale, 0.12, 2.2 * cartScale);
  const baseMesh = new THREE.Mesh(baseGeo, chromeMat);
  baseMesh.position.y = 0.45;
  baseMesh.castShadow = true;
  group.add(baseMesh);

  // 4 Bánh xe (Casters)
  const wheelGeo = new THREE.CylinderGeometry(0.22 * cartScale, 0.22 * cartScale, 0.12 * cartScale, 12);
  wheelGeo.rotateZ(Math.PI / 2);
  const wheelOffsets = [
    [-0.7 * cartScale, -0.9 * cartScale],
    [0.7 * cartScale, -0.9 * cartScale],
    [-0.7 * cartScale, 0.9 * cartScale],
    [0.7 * cartScale, 0.9 * cartScale],
  ];
  wheelOffsets.forEach(([wx, wz]) => {
    const wheel = new THREE.Mesh(wheelGeo, blackMat);
    wheel.position.set(wx, 0.22 * cartScale, wz);
    wheel.castShadow = true;
    group.add(wheel);
  });

  // 2. Giỏ chứa hàng (Wire Basket)
  const basketGeo = new THREE.BoxGeometry(1.5 * cartScale, 1.2 * cartScale, 2.0 * cartScale);
  const basketMesh = new THREE.Mesh(basketGeo, wireMat);
  basketMesh.position.y = 1.35 * cartScale + 0.45;
  basketMesh.castShadow = true;
  group.add(basketMesh);

  // Đáy giỏ đặc
  const basketBottomGeo = new THREE.BoxGeometry(1.48 * cartScale, 0.05, 1.98 * cartScale);
  const basketBottom = new THREE.Mesh(basketBottomGeo, chromeMat);
  basketBottom.position.y = 0.75 * cartScale + 0.45;
  group.add(basketBottom);

  // 3. Tay cầm đẩy xe & Màn hình IoT thông minh
  const handleGeo = new THREE.CylinderGeometry(0.06 * cartScale, 0.06 * cartScale, 1.4 * cartScale, 8);
  handleGeo.rotateZ(Math.PI / 2);
  const handle = new THREE.Mesh(handleGeo, blackMat);
  handle.position.set(0, 1.95 * cartScale + 0.45, -1.05 * cartScale);
  group.add(handle);

  // Màn hình máy tính IoT trên tay cầm
  const screenGeo = new THREE.BoxGeometry(0.65 * cartScale, 0.45 * cartScale, 0.08 * cartScale);
  const screen = new THREE.Mesh(screenGeo, screenMat);
  screen.position.set(0, 2.15 * cartScale + 0.45, -0.98 * cartScale);
  screen.rotation.x = -Math.PI / 5;
  group.add(screen);

  // 4. Vòng tròn hào quang trạng thái dưới chân xe (Aura Ring)
  const auraGeo = new THREE.RingGeometry(1.2 * cartScale, 1.45 * cartScale, 24);
  auraGeo.rotateX(-Math.PI / 2);
  const auraMat = new THREE.MeshBasicMaterial({ color: '#10b981', side: THREE.DoubleSide });
  const auraRing = new THREE.Mesh(auraGeo, auraMat);
  auraRing.position.y = 0.04;
  group.add(auraRing);
  group.userData.auraRing = auraRing;

  // 5. Cột sáng Highlight khi được chọn
  const beamGeo = new THREE.CylinderGeometry(0.04, 0.8 * cartScale, 5, 16, 1, true);
  const beamMat = new THREE.MeshBasicMaterial({
    color: '#38bdf8',
    transparent: true,
    opacity: 0.35,
    side: THREE.DoubleSide,
  });
  const selectionBeam = new THREE.Mesh(beamGeo, beamMat);
  selectionBeam.position.y = 2.5;
  selectionBeam.visible = false;
  group.add(selectionBeam);
  group.userData.selectionBeam = selectionBeam;

  // 6. Nhãn nổi hiển thị Cart ID & Pin trên đầu xe (Sprite)
  const badgeTex = createCartBadgeTexture(cartId, 100, { color: '#10b981', label: 'Sẵn sàng' });
  const spriteMat = new THREE.SpriteMaterial({ map: badgeTex, transparent: true });
  const badgeSprite = new THREE.Sprite(spriteMat);
  badgeSprite.scale.set(3.8, 1.45, 1);
  badgeSprite.position.set(0, 3.4, 0);
  group.add(badgeSprite);
  group.userData.badgeSprite = badgeSprite;

  return group;
}
