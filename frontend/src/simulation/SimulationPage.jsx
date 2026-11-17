import AdminLayout from '../admin/AdminLayout.jsx';
import SupermarketSimulation from './SupermarketSimulation.jsx';

export default function SimulationPage() {
  return (
    <AdminLayout>
      <div className="page-head" style={{ marginBottom: 12 }}>
        <div>
          <h1 className="page-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>🛒</span> Mô hình Siêu thị 3D Interactive Digital Twin
          </h1>
          <p className="muted lead" style={{ marginTop: 4, marginBottom: 0 }}>
            Mô hình siêu thị 3D tương tác nhìn từ góc isometric: các dãy kệ hàng phân loại, sản phẩm low-poly sắc màu, quầy thu ngân và xe đẩy di chuyển realtime theo kịch bản IoT.
          </p>
        </div>
      </div>
      <SupermarketSimulation />
    </AdminLayout>
  );
}
