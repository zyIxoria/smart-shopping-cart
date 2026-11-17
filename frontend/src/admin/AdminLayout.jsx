import { Link, usePath } from '../router.jsx';
import { api } from '../api/index.js';
import { useAuth } from '../api/auth.js';
import { ErrorBanner, Toasts, WsIndicator } from '../common/ui.jsx';
import { useStore } from '../state/store.jsx';

export default function AdminLayout({ children }) {
  const { state, refresh } = useStore();
  const path = usePath();
  const auth = useAuth();
  const active = state.alerts.filter((a) => a.status === 'ACTIVE').length;
  const nav = [
    { to: '/admin', label: 'Tổng quan', on: path === '/admin' || path.startsWith('/admin/carts') },
    { to: '/simulation', label: 'Mô phỏng Siêu thị 3D', on: path === '/simulation' },
    { to: '/admin/alerts', label: 'Cảnh báo', on: path.startsWith('/admin/alerts'), count: active },
    { to: '/admin/products', label: 'Sản phẩm', on: path.startsWith('/admin/products') },
  ];
  return (
    <div className="shell admin">
      <header className="topbar">
        <Link to="/admin" className="brand"><span className="logo">🛒</span> Smart Cart <span className="tag">Quản trị</span></Link>
        <nav className="nav" aria-label="Điều hướng quản trị">
          {nav.map((n) => (
            <Link key={n.to} to={n.to} className={`nav-link ${n.on ? 'on' : ''}`} data-testid={`nav-${n.to.split('/').pop()}`}>
              {n.label}{n.count > 0 && <span className="count" data-testid="nav-alert-count">{n.count}</span>}
            </Link>
          ))}
        </nav>
        <div className="topbar-right"><WsIndicator />
          {auth.staff && (
            <span className="user-chip" data-testid="user-chip">
              {auth.staff.username} · {auth.staff.role === 'admin' ? 'Quản trị' : 'Chỉ xem'}
              <button className="btn btn-link btn-small" onClick={() => api.logout()} data-testid="logout">Đăng xuất</button>
            </span>
          )}<Link to="/simulator" className="link-muted" data-testid="nav-simulator">Simulator →</Link><Link to="/customer" className="link-muted">Màn hình khách →</Link></div>
      </header>
      <main className="container wide">
        <ErrorBanner error={state.error} onRetry={refresh} />
        {children}
      </main>
      <Toasts scope="admin" />
    </div>
  );
}
