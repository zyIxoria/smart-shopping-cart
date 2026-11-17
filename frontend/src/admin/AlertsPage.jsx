import { useState } from 'react';
import { AlertChip, Badge, Empty, Loading } from '../common/ui.jsx';
import { ALERT_STATUS, ALERT_TYPE, dateTime } from '../common/format.js';
import { Link } from '../router.jsx';
import { useStore } from '../state/store.jsx';
import AdminLayout from './AdminLayout.jsx';

export default function AlertsPage() {
  const { state } = useStore();
  const [status, setStatus] = useState('ACTIVE');
  const [type, setType] = useState('ALL');
  const [cart, setCart] = useState('ALL');
  const carts = Object.keys(state.carts).sort();
  const rows = state.alerts.filter((a) => (status === 'ALL' || a.status === status) && (type === 'ALL' || a.alert_type === type) && (cart === 'ALL' || a.cart_id === cart));

  return (
    <AdminLayout>
      <h1 className="page-title">Cảnh báo</h1>
      <div className="toolbar">
        <label>Trạng thái
          <select value={status} onChange={(e) => setStatus(e.target.value)} data-testid="filter-status">
            <option value="ACTIVE">Đang xảy ra</option><option value="RESOLVED">Đã xử lý</option><option value="ALL">Tất cả</option>
          </select>
        </label>
        <label>Loại
          <select value={type} onChange={(e) => setType(e.target.value)} data-testid="filter-type">
            <option value="ALL">Tất cả</option>
            {Object.entries(ALERT_TYPE).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </label>
        <label>Xe
          <select value={cart} onChange={(e) => setCart(e.target.value)} data-testid="filter-cart">
            <option value="ALL">Tất cả</option>
            {carts.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <span className="muted" data-testid="alert-total">{rows.length} cảnh báo</span>
      </div>
      {!state.loaded ? <Loading /> : rows.length === 0 ? (
        <Empty icon="✅" title="Không có cảnh báo phù hợp" hint="Cảnh báo sẽ xuất hiện khi pin dưới 20%, lệch cân quá 100 g hoặc xe mất kết nối." />
      ) : (
        <div className="card table-wrap">
          <table className="table" data-testid="alerts-table">
            <thead><tr><th>Thời gian</th><th>Xe</th><th>Loại</th><th>Chi tiết</th><th>Trạng thái</th><th>Xử lý lúc</th></tr></thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id} data-testid="alert-row">
                  <td>{dateTime(a.created_at)}</td>
                  <td><Link to={`/admin/carts/${a.cart_id}`}>{a.cart_id}</Link></td>
                  <td><AlertChip type={a.alert_type} /></td>
                  <td>{a.detail}</td>
                  <td><Badge tone={ALERT_STATUS[a.status].tone}>{ALERT_STATUS[a.status].label}</Badge></td>
                  <td className="muted">{dateTime(a.resolved_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AdminLayout>
  );
}
