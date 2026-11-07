// Read-only fixtures for the UI preview. No backend, storage or broker connection.
type Row = Record<string, any>;
export type PreviewContext = { node: string; token?: string | null };
export const PREVIEW_PASSWORD = 'ToyChainDemo2026!';
export const PREVIEW_READ_ONLY = 'Bản xem thử chỉ dùng để xem giao diện. Thay đổi chưa được lưu; cần chạy hệ thống đầy đủ để thực hiện thao tác này.';
const branches: Record<string, string> = { DONG: 'Chi nhánh Đông', TAY: 'Chi nhánh Tây', NAM: 'Chi nhánh Nam', BAC: 'Chi nhánh Bắc' };
const codes = Object.keys(branches);
const snapshotTime = '2026-11-06T10:00:00Z';
const catalogue: [string, string, string, number][] = [
  ['LEGO-001', 'LEGO Classic · Hộp sáng tạo', 'Lắp ráp', 599000],
  ['LEGO-002', 'LEGO City · Xe cứu hỏa', 'Lắp ráp', 899000],
  ['WOOD-001', 'Bộ xếp hình gỗ cầu vồng', 'Giáo dục', 249000],
  ['STEM-001', 'Bộ thí nghiệm khoa học', 'Giáo dục', 459000],
  ['CAR-001', 'Xe mô hình thể thao 1:32', 'Mô hình', 189000],
  ['CAR-002', 'Xe điều khiển địa hình', 'Điều khiển', 749000],
  ['DOLL-001', 'Búp bê và tủ quần áo', 'Búp bê', 329000],
  ['DOLL-002', 'Ngôi nhà búp bê gỗ', 'Búp bê', 1250000],
  ['PLUSH-001', 'Gấu bông mây mềm 35cm', 'Thú bông', 219000],
  ['PLUSH-002', 'Thỏ bông tai dài', 'Thú bông', 179000],
  ['BOARD-001', 'Cờ tỷ phú gia đình', 'Board game', 289000],
  ['BOARD-002', 'Bộ cờ vua gỗ', 'Board game', 349000],
  ['ART-001', 'Hộp màu sáng tạo 48 màu', 'Mỹ thuật', 159000],
  ['ART-002', 'Đất nặn sắc màu 12 hộp', 'Mỹ thuật', 129000],
  ['OUT-001', 'Bóng rổ trẻ em', 'Vận động', 199000],
  ['OUT-002', 'Xe trượt scooter', 'Vận động', 890000],
];
const products: Row[] = catalogue.map(([sku, name, category, price], i) => ({ id: `preview-product-${i + 1}`, sku, name, category, price, active: true, version: 1 }));
const users: Row[] = [
  { id: 'preview-admin', username: 'admin', name: 'Quản trị ToyChain', role: 'admin', branch_id: null, active: true },
  ...codes.flatMap(branch_id => ['manager', 'cashier'].map(role => ({
    id: `preview-${role}-${branch_id}`, username: `${role === 'manager' ? 'ql' : 'nv'}.${branch_id.toLowerCase()}`,
    name: `${role === 'manager' ? 'Quản lý' : 'Thu ngân'} ${branches[branch_id].replace('Chi nhánh ', '')}`,
    role, branch_id, active: true,
  }))),
];
const partners: Row[] = codes.flatMap(branch_id => [
  { id: `preview-supplier-${branch_id}`, branch_id, kind: 'supplier', name: 'Nhà cung cấp Đồ chơi Tuổi Thơ (mẫu)', phone: '' },
  { id: `preview-customer-${branch_id}`, branch_id, kind: 'customer', name: `Khách hàng mẫu · ${branches[branch_id]}`, phone: '' },
]);
function line(index: number, quantity: number, purchase = false): Row {
  const p = products[index];
  return { product_id: p.id, sku: p.sku, name: p.name, quantity, unit_price: purchase ? Math.round(p.price * 0.6) : p.price };
}
const transactions: Row[] = [];
function transaction(branch_id: string, kind: string, lines: Row[], created_at: string, reference_id: string | null = null): Row {
  const row = {
    id: `DM${String(transactions.length + 1).padStart(6, '0')}-${branch_id}`, branch_id, kind, lines,
    total: lines.reduce((sum, l) => sum + l.quantity * l.unit_price, 0), reference_id,
    partner_id: `preview-${kind === 'purchase' ? 'supplier' : 'customer'}-${branch_id}`,
    note: 'Dữ liệu minh họa cho giao diện', actor: `ql.${branch_id.toLowerCase()}`, created_at,
  };
  transactions.push(row);
  return row;
}
codes.forEach((branch, b) => {
  transaction(branch, 'purchase', products.map((_, i) => line(i, 18 + (i * 7 + b * 11) % 30, true)), '2026-11-05T02:00:00Z');
  const sale = transaction(branch, 'sale', [line(0, 3 + b), line(8, 2)], '2026-11-06T02:15:00Z');
  transaction(branch, 'sale', [line(2 + b, 4), line(12, 2 + b)], '2026-11-06T04:30:00Z');
  transaction(branch, 'sale', [line(0, 7), line(10, 2)], '2026-11-06T07:20:00Z');
  if (b === 0) transaction(branch, 'refund', [line(0, 1)], '2026-11-06T08:00:00Z', sale.id);
});
const transfers: Row[] = [
  { id: 'DC000001-DONG-TAY', source: 'DONG', destination: 'TAY', lines: [line(0, 3), line(2, 2)], status: 'in_transit', actor: 'ql.dong', created_at: '2026-11-06T09:00:00Z', received_at: null, received_by: null },
  { id: 'DC000002-NAM-BAC', source: 'NAM', destination: 'BAC', lines: [line(8, 4)], status: 'received', actor: 'ql.nam', created_at: '2026-11-06T06:00:00Z', received_at: '2026-11-06T09:30:00Z', received_by: 'ql.bac' },
];
// Derive stock and dashboard from the same sample ledger to keep the screens consistent.
const stock: Row[] = codes.flatMap(branch_id => products.map(p => {
  let quantity = 0;
  for (const t of transactions.filter(t => t.branch_id === branch_id)) {
    for (const l of t.lines.filter((l: Row) => l.product_id === p.id)) quantity += l.quantity * (t.kind === 'sale' ? -1 : 1);
  }
  for (const t of transfers) for (const l of t.lines.filter((l: Row) => l.product_id === p.id)) {
    if (t.source === branch_id) quantity -= l.quantity;
    if (t.destination === branch_id && t.status === 'received') quantity += l.quantity;
  }
  return { branch_id, product_id: p.id, sku: p.sku, name: p.name, category: p.category, price: p.price, quantity };
}));
const documentTexts = [
  'Chứng nhận an toàn LEGO Classic – dữ liệu minh họa. Sản phẩm LEGO-001. Nội dung giúp xem thử cách liên kết tài liệu với sản phẩm và phiếu nhập tại chi nhánh Đông.',
  'Hướng dẫn lắp ráp LEGO City – dữ liệu minh họa. Sản phẩm LEGO-002. Bảo quản các chi tiết nhỏ trong hộp sau khi sử dụng.',
  'Hướng dẫn bảo quản bộ xếp hình gỗ cầu vồng – dữ liệu minh họa. Sản phẩm WOOD-001. Lau bằng khăn mềm và giữ sản phẩm khô ráo.',
  'Hướng dẫn bộ thí nghiệm khoa học – dữ liệu minh họa. Sản phẩm STEM-001. Thực hành với sự hướng dẫn của người lớn.',
];
const documents: Row[] = codes.map((branch_id, i) => ({
  id: `preview-document-${i + 1}`, branch_id, product_id: products[i].id,
  order_id: transactions.find(t => t.branch_id === branch_id && t.kind === 'purchase')!.id,
  filename: `${i === 0 ? 'chung-nhan-an-toan' : 'huong-dan'}-${products[i].sku.toLowerCase()}.txt`,
  mime: 'text/plain', size: new TextEncoder().encode(documentTexts[i]).length,
  text: documentTexts[i], status: i === 0 ? 'verified' : 'ready', error: null, author: 'admin',
  created_at: '2026-11-06T08:30:00Z', processed_at: '2026-11-06T08:31:00Z',
}));
const feedback: Row[] = codes.map((branch_id, i) => ({
  id: `preview-feedback-${i + 1}`, branch_id, product_id: products[i].id, rating: i === 1 ? 4 : 5,
  text: ['Bé rất thích hộp sáng tạo, nhiều cách lắp ghép. Phản hồi mẫu.', 'Mô hình xe đẹp, nên có thêm hướng dẫn lắp ráp. Phản hồi mẫu.', 'Màu sắc dễ thương, bề mặt gỗ nhẵn. Phản hồi mẫu.', 'Bộ thí nghiệm giúp cả nhà cùng học và chơi. Phản hồi mẫu.'][i],
  author: `nv.${branch_id.toLowerCase()}`, created_at: '2026-11-06T09:15:00Z',
}));
const normalize = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase();

export function previewNode(value: string | null): string {
  return value === 'CENTRAL' || codes.includes(value || '') ? value! : 'CENTRAL';
}

export async function previewApi<T = Row>(path: string, init: RequestInit = {}, context: PreviewContext): Promise<T> {
  const node = previewNode(context.node);
  const url = new URL(path, 'http://preview.invalid');
  const route = url.pathname;
  const method = (init.method || 'GET').toUpperCase();
  const result = (value: unknown) => structuredClone(value) as T;
  if (route === '/info' && method === 'GET') return result({ node, name: branches[node] || 'Trung tâm', branches, ocr_enabled: false });
  if (route === '/auth/login' && method === 'POST') {
    const body = JSON.parse(String(init.body || '{}'));
    const user = users.find(u => u.username === body.username);
    if (!user || body.password !== PREVIEW_PASSWORD) throw new Error('Tên đăng nhập hoặc mật khẩu xem thử không đúng.');
    if (node !== 'CENTRAL' && user.role !== 'admin' && user.branch_id !== node) throw new Error('Tài khoản thuộc chi nhánh khác.');
    return result({ access_token: `preview:${user.username}`, user });
  }
  const user = users.find(u => context.token === `preview:${u.username}`);
  if (!user) throw new Error('Vui lòng đăng nhập bản xem thử.');
  if (node !== 'CENTRAL' && user.role !== 'admin' && user.branch_id !== node) throw new Error('Tài khoản thuộc chi nhánh khác.');
  if (method !== 'GET') throw new Error(PREVIEW_READ_ONLY);
  if (route === '/auth/me') return result(user);
  const allowed = node !== 'CENTRAL' ? node : user.role !== 'admin' ? user.branch_id : null;
  const requested = url.searchParams.get('branch');
  if (requested && (!codes.includes(requested) || allowed && allowed !== requested)) throw new Error('Không có quyền xem chi nhánh này.');
  const selected = allowed || requested;
  const scoped = (rows: Row[]) => rows.filter(r => !selected || r.branch_id === selected);
  const centralOnly = () => { if (node !== 'CENTRAL') throw new Error('Mở trung tâm để xem tài liệu và phản hồi.'); };
  if (route === '/products') return result(products);
  if (route === '/stock') return result(scoped(stock));
  if (route === '/transactions') return result(scoped(transactions).sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, Math.max(1, Math.min(500, Number(url.searchParams.get('limit')) || 100))));
  if (route === '/partners') return result(scoped(partners));
  const scopedTransfers = transfers.filter(t => !selected || [t.source, t.destination].includes(selected));
  if (route === '/transfers') return result(scopedTransfers);
  if (route === '/dashboard') return result({
    product_count: products.length, in_transit: scopedTransfers.filter(t => t.status === 'in_transit').length,
    branches: (selected ? [selected] : codes).map(branch_id => ({
      branch_id, name: branches[branch_id], last_synced_at: snapshotTime,
      stock_units: stock.filter(s => s.branch_id === branch_id).reduce((sum, s) => sum + s.quantity, 0),
      low_stock: stock.filter(s => s.branch_id === branch_id && s.quantity < 10).length,
      transaction_count: transactions.filter(t => t.branch_id === branch_id).length,
      net_revenue: transactions.filter(t => t.branch_id === branch_id).reduce((sum, t) => sum + (t.kind === 'sale' ? t.total : t.kind === 'refund' ? -t.total : 0), 0),
    })),
  });
  if (route === '/users') {
    if (node !== 'CENTRAL' || user.role !== 'admin') throw new Error('Mở trung tâm bằng tài khoản quản trị.');
    return result(users);
  }
  if (route === '/sync') {
    if (user.role === 'cashier' || node === 'CENTRAL' && user.role !== 'admin') throw new Error('Cần quyền quản lý để xem đồng bộ.');
    return result({
      control: { id: 1, enabled: true, worker_seen_at: snapshotTime, last_error: null }, pending: 0, processed: node === 'CENTRAL' ? transactions.length + 3 : 16, last_received_at: snapshotTime, failed: [],
      reconciliations: node === 'CENTRAL' ? codes.map(branch_id => ({ id: `preview-reconcile-${branch_id}`, branch_id, status: 'matched', created_at: snapshotTime, details: { note: 'Kết quả minh họa, chưa chạy ETL thật.', stock_units: stock.filter(s => s.branch_id === branch_id).reduce((sum, s) => sum + s.quantity, 0) } })) : [],
    });
  }
  if (route === '/documents' || route.startsWith('/documents/')) {
    centralOnly();
    const visible = scoped(documents);
    const download = route.match(/^\/documents\/([^/]+)\/download$/);
    if (download) {
      const doc = visible.find(d => d.id === decodeURIComponent(download[1]));
      if (!doc) throw new Error('Không tìm thấy tài liệu trong phạm vi xem thử.');
      return result({ text: doc.text, mime: doc.mime, filename: doc.filename });
    }
    if (route === '/documents') return result(visible.filter(d => (!url.searchParams.get('product_id') || d.product_id === url.searchParams.get('product_id')) && normalize(d.filename + ' ' + d.text).includes(normalize(url.searchParams.get('q') || ''))));
  }
  if (route === '/feedback') { centralOnly(); return result(scoped(feedback)); }
  if (route === '/search') {
    centralOnly();
    const query = normalize(url.searchParams.get('q') || '');
    const docs = scoped(documents).filter(d => normalize(d.filename + ' ' + d.text).includes(query));
    const notes = scoped(feedback).filter(f => normalize(f.text).includes(query));
    const linkedIds = new Set([...docs, ...notes].map(r => r.product_id));
    return result({
      products: products.filter(p => linkedIds.has(p.id) || normalize(`${p.sku} ${p.name} ${p.category}`).includes(query)).map(p => ({
        ...p, stock: scoped(stock).filter(s => s.product_id === p.id),
        documents: docs.filter(d => d.product_id === p.id), feedback: notes.filter(f => f.product_id === p.id),
      })), documents: docs, feedback: notes,
    });
  }
  throw new Error('Màn hình này chưa có dữ liệu xem thử.');
}
