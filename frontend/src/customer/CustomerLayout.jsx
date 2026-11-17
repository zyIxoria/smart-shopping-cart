import { Link } from '../router.jsx';
import { ErrorBanner, Toasts, WsIndicator } from '../common/ui.jsx';
import { useStore } from '../state/store.jsx';

export default function CustomerLayout({ children, back, cartId }) {
  const { state, refresh } = useStore();
  return (
    <div className="shell customer">
      <header className="topbar">
        <Link to="/customer" className="brand"><span className="logo">🛒</span> Smart Cart</Link>
        <div className="topbar-right">
          {back}
          <WsIndicator />
          <Link to="/simulator" className="link-muted">Simulator →</Link>
          <Link to="/admin" className="link-muted">Quản trị →</Link>
        </div>
      </header>
      <main className="container">
        <ErrorBanner error={state.error} onRetry={refresh} />
        {children}
      </main>
      <Toasts scope="customer" cartId={cartId} />
    </div>
  );
}
