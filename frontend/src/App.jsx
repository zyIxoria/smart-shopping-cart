import { Link, matchPath, usePath } from './router.jsx';
import { StoreProvider } from './state/store.jsx';
import CartSelect from './customer/CartSelect.jsx';
import ShoppingPage from './customer/ShoppingPage.jsx';
import Dashboard from './admin/Dashboard.jsx';
import CartDetail from './admin/CartDetail.jsx';
import AlertsPage from './admin/AlertsPage.jsx';
import ProductsPage from './admin/ProductsPage.jsx';
import SimulatorPage from './simulator/SimulatorPage.jsx';
import SimulationPage from './simulation/SimulationPage.jsx';
import RequireStaff from './admin/RequireStaff.jsx';

const ROUTES = [
  ['/customer', CartSelect],
  ['/customer/cart/:sid', ShoppingPage],
  ['/admin', Dashboard],
  ['/admin/carts/:id', CartDetail],
  ['/admin/alerts', AlertsPage],
  ['/admin/products', ProductsPage],
  ['/simulation', SimulationPage],
  ['/simulator', SimulatorPage],
];

function Landing() {
  return (
    <div className="landing">
      <h1><span className="logo">🛒</span> Smart Shopping Cart</h1>
      <p>Hệ thống giỏ hàng thông minh IoT — chọn giao diện bạn muốn mở.</p>
      <div className="landing-cards">
        <Link to="/customer" className="card link-card" data-testid="go-customer"><h2>Khách hàng</h2><p>Chọn xe, quét sản phẩm, thanh toán.</p></Link>
        <Link to="/admin" className="card link-card" data-testid="go-admin"><h2>Quản trị</h2><p>Giám sát xe, cảnh báo, khoá/mở khoá.</p></Link>
        <Link to="/simulation" className="card link-card" data-testid="go-simulation"><h2>Mô phỏng 2D</h2><p>Bản đồ siêu thị Digital Twin trực quan & kịch bản IoT.</p></Link>
        <Link to="/simulator" className="card link-card" data-testid="go-simulator"><h2>Simulator phần cứng</h2><p>Giả lập xe IoT: quét hàng, pin, cân, mất mạng.</p></Link>
      </div>
    </div>
  );
}

function NotFound() {
  return <div className="landing"><h1>Không tìm thấy trang</h1><p><Link to="/" className="btn btn-primary">Về trang chủ</Link></p></div>;
}

export default function App() {
  const path = usePath();
  let page = null;
  if (path === '/') page = <Landing />;
  else {
    for (const [pattern, Comp] of ROUTES) {
      const params = matchPath(pattern, path);
      if (params) {
        const el = <Comp params={params} />;
        page = pattern.startsWith('/admin') || pattern === '/simulator' || pattern === '/simulation' ? <RequireStaff>{el}</RequireStaff> : el;
        break;
      }
    }
  }
  return <StoreProvider>{page || <NotFound />}</StoreProvider>;
}
