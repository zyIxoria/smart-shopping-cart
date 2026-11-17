import { useState } from 'react';
import { api } from '../api/index.js';
import { Link } from '../router.jsx';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(username.trim(), password);   // thành công: token vào authStore, RequireStaff tự hiển thị trang quản trị
      setPassword('');
    } catch (err) {
      setError(err.status === 429 ? `${err.message}` : err.status === 401 ? 'Sai tên đăng nhập hoặc mật khẩu' : err.message);
    } finally { setBusy(false); }
  }

  return (
    <div className="landing login-page">
      <h1><span className="logo">🔐</span> Đăng nhập quản trị</h1>
      <p>Khu vực dành cho nhân viên. Khách hàng không cần đăng nhập.</p>
      <form className="card login-card" onSubmit={submit} data-testid="login-form">
        <label>Tên đăng nhập
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required maxLength={64} data-testid="login-username" />
        </label>
        <label>Mật khẩu
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required maxLength={256} data-testid="login-password" />
        </label>
        {error && <p className="hint-warn" role="alert" data-testid="login-error">{error}</p>}
        <button className="btn btn-primary btn-block" disabled={busy || !username || !password} data-testid="login-submit">{busy ? 'Đang đăng nhập…' : 'Đăng nhập'}</button>
        <p className="muted small"><Link to="/">← Về trang chủ</Link></p>
      </form>
    </div>
  );
}
