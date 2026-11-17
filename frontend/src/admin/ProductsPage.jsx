import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/index.js';
import { canWrite, useAuth } from '../api/auth.js';
import { Badge, Empty, Loading, Modal } from '../common/ui.jsx';
import { vnd, weight } from '../common/format.js';
import { useStore } from '../state/store.jsx';
import AdminLayout from './AdminLayout.jsx';

const BLANK = { barcode: '', name: '', price: '', unit_weight: '', image: '' };

function ProductForm({ product, onClose, onSaved }) {
  const editing = Boolean(product?.id);
  const [f, setF] = useState(editing ? { barcode: product.barcode, name: product.name, price: String(product.price), unit_weight: String(product.unit_weight), image: product.image || '' } : BLANK);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const price = Number(f.price);
  const w = Number(f.unit_weight);
  const valid = /^[0-9A-Za-z-]{4,64}$/.test(f.barcode) && f.name.trim() && f.price !== '' && Number.isInteger(price) && price >= 0 && f.unit_weight !== '' && w > 0;

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErr('');
    const body = { barcode: f.barcode.trim(), name: f.name.trim(), price, unit_weight: w, image: f.image.trim() };
    try { onSaved(editing ? await api.updateProduct(product.id, body) : await api.createProduct(body), editing); } catch (x) { setErr(x.message); } finally { setBusy(false); }
  }

  return (
    <Modal title={editing ? `Sửa sản phẩm` : 'Thêm sản phẩm'} onClose={() => !busy && onClose()}>
      <form onSubmit={submit} className="form-grid" data-testid="product-form">
        <label>Mã vạch
          <input value={f.barcode} onChange={set('barcode')} placeholder="vd. 8934588099999" maxLength={64} autoFocus data-testid="pf-barcode" />
          <span className="muted small">4–64 ký tự: chữ, số, dấu “-” (máy quét của xe chỉ chấp nhận các ký tự này)</span>
        </label>
        <label>Tên sản phẩm
          <input value={f.name} onChange={set('name')} maxLength={120} data-testid="pf-name" />
        </label>
        <div className="form-row">
          <label>Giá (₫)
            <input type="number" inputMode="numeric" min="0" step="1" value={f.price} onChange={set('price')} data-testid="pf-price" />
          </label>
          <label>Khối lượng 1 đơn vị (gram)
            <input type="number" inputMode="decimal" min="0.1" step="any" value={f.unit_weight} onChange={set('unit_weight')} data-testid="pf-weight" />
          </label>
        </div>
        <label>Ảnh (URL, tuỳ chọn)
          <input value={f.image} onChange={set('image')} maxLength={500} data-testid="pf-image" />
        </label>
        <p className="muted small">Khối lượng dùng để tính <b>cân dự kiến</b> của giỏ: sai số quá 100 g sẽ sinh cảnh báo lệch cân.</p>
        {err && <p className="form-error" role="alert" data-testid="pf-error">⚠️ {err}</p>}
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose} disabled={busy}>Huỷ</button>
          <button type="submit" className="btn btn-primary" disabled={busy || !valid} data-testid="pf-save">{busy ? 'Đang lưu…' : editing ? 'Lưu thay đổi' : 'Thêm'}</button>
        </div>
      </form>
    </Modal>
  );
}

export default function ProductsPage() {
  const { toast } = useStore();
  const auth = useAuth();
  const writable = canWrite(auth);
  const [list, setList] = useState(null);
  const [error, setError] = useState('');
  const [q, setQ] = useState('');
  const [hidden, setHidden] = useState(false);
  const [form, setForm] = useState(null);       // null | {} (thêm) | product (sửa)

  const load = useCallback(() => api.getProductsAdmin().then((r) => { setList(r); setError(''); }).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const t = q.trim().toLowerCase();
  const shown = (list || []).filter((p) => (hidden || p.active) && (!t || p.name.toLowerCase().includes(t) || p.barcode.toLowerCase().includes(t)));

  async function toggle(p) {
    try {
      const u = await api.updateProduct(p.id, { active: !p.active });
      toast('ok', `${u.active ? 'Đã hiện lại' : 'Đã ẩn'}: ${u.name}`, { scope: 'admin' });
      load();
    } catch (e) { toast('error', e.message, { scope: 'admin' }); }
  }

  return (
    <AdminLayout>
      <div className="page-head">
        <h1 className="page-title">Sản phẩm</h1>
        {writable && <button className="btn btn-primary" onClick={() => setForm({})} data-testid="add-product">＋ Thêm sản phẩm</button>}
      </div>
      {!writable && <p className="muted small">Tài khoản chỉ xem: không sửa được danh mục sản phẩm.</p>}
      <div className="toolbar">
        <label>Tìm theo tên / mã vạch
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm…" data-testid="product-search" />
        </label>
        <label className="check"><input type="checkbox" checked={hidden} onChange={(e) => setHidden(e.target.checked)} data-testid="show-hidden" /> Hiện cả sản phẩm đã ẩn</label>
      </div>
      {error && <div className="banner banner-danger" role="alert"><span>⚠️ {error}</span><button className="btn btn-small" onClick={load}>Thử lại</button></div>}
      {!list && !error ? <Loading /> : shown.length === 0 ? <Empty icon="📦" title="Không có sản phẩm phù hợp" /> : (
        <div className="card table-wrap">
          <table className="table" data-testid="products-table">
            <thead><tr><th>Mã vạch</th><th>Tên</th><th className="num">Giá</th><th className="num">Khối lượng</th><th>Trạng thái</th>{writable && <th />}</tr></thead>
            <tbody>
              {shown.map((p) => (
                <tr key={p.id} className={p.active ? '' : 'row-off'} data-testid={`product-row-${p.barcode}`}>
                  <td className="mono">{p.barcode}</td>
                  <td>{p.name}</td>
                  <td className="num">{vnd(p.price)}</td>
                  <td className="num">{weight(p.unit_weight)}</td>
                  <td><Badge tone={p.active ? 'ok' : 'muted'}>{p.active ? 'Đang bán' : 'Đã ẩn'}</Badge></td>
                  {writable && (
                    <td className="row-actions">
                      <button className="btn btn-small" onClick={() => setForm(p)} data-testid={`edit-${p.barcode}`}>Sửa</button>{' '}
                      <button className="btn btn-small" onClick={() => toggle(p)} data-testid={`toggle-${p.barcode}`}>{p.active ? 'Ẩn' : 'Hiện'}</button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted small">Sản phẩm không bị xoá hẳn để giữ lịch sử giỏ hàng; “Ẩn” khiến khách không quét/chọn được nữa.</p>
      {form && (
        <ProductForm product={form} onClose={() => setForm(null)}
          onSaved={(p, editing) => { setForm(null); toast('ok', `${editing ? 'Đã lưu' : 'Đã thêm'}: ${p.name}`, { scope: 'admin' }); load(); }} />
      )}
    </AdminLayout>
  );
}
