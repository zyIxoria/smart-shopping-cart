import { useAuth } from '../api/auth.js';
import { Loading } from '../common/ui.jsx';
import LoginPage from './LoginPage.jsx';

// Chặn các trang quản trị khi máy chủ yêu cầu đăng nhập (AUTH_ENABLED=1). Quyền thật vẫn do Backend kiểm tra.
export default function RequireStaff({ children }) {
  const auth = useAuth();
  if (auth.required === null) return <Loading text="Đang kiểm tra phiên đăng nhập…" />;
  if (auth.required && !auth.staff) return <LoginPage />;
  return children;
}
