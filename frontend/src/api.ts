export type Row = Record<string, any>;
export const isPreview = import.meta.env.MODE === 'preview' && import.meta.env.VITE_UI_PREVIEW === 'true';
export const TOKEN_KEY = isPreview ? 'toychain-preview-token' : 'toychain-token';
export const money = (n: number) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(n);
export const when = (s?: string) => s ? new Date(/[Zz]|[+-]\d\d:\d\d$/.test(s) ? s : s + 'Z').toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : 'Chưa có dữ liệu';
export const branchNames: Record<string,string> = { CENTRAL:'Trung tâm', DONG:'Đông', TAY:'Tây', NAM:'Nam', BAC:'Bắc' };
export const labels: Record<string,string> = { sale:'Bán hàng', purchase:'Nhập hàng', refund:'Trả hàng', adjustment:'Điều chỉnh', in_transit:'Đang chuyển', received:'Đã nhận', pending:'Chờ xử lý', processing:'Đang xử lý', ready:'Đã trích xuất', needs_ocr:'Cần OCR', verified:'Đã xác nhận', error:'Lỗi xử lý', matched:'Khớp dữ liệu', difference:'Cần đối soát', unreachable:'Chưa kết nối', admin:'Quản trị', manager:'Quản lý', cashier:'Thu ngân', supplier:'Nhà cung cấp', customer:'Khách hàng' };
export async function api<T = Row>(path: string, init: RequestInit = {}): Promise<T> {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (isPreview) {
    const { previewApi, previewNode } = await import('./preview');
    return previewApi<T>(path, init, { token, node: previewNode(new URL(window.location.href).searchParams.get('node')) });
  }
  const headers: Record<string,string> = { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers as Record<string,string> };
  if (init.body && !(init.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch('/api' + path, { ...init, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((e:Row) => `${e.loc?.slice(1).join('.')}: ${e.msg}`).join('; ') : `Lỗi kết nối (${response.status})`);
  }
  return response.json();
}
export const post = <T = Row>(path: string, body: unknown, key?: string) => api<T>(path, { method:'POST', body: JSON.stringify(body), headers: key ? { 'Idempotency-Key': key } : {} });
export function openNode(node: string) {
  if (!Object.hasOwn(branchNames, node)) return;
  if (isPreview) {
    const url = new URL(window.location.href);
    url.searchParams.set('node', node);
    window.location.assign(url);
    return;
  }
  const ports: Record<string,string> = { CENTRAL:'8080', DONG:'8101', TAY:'8102', NAM:'8103', BAC:'8104' };
  const url = new URL(window.location.href); url.port = ports[node]; url.pathname = '/'; window.location.assign(url);
}
export async function downloadDocument(row: Row) {
  let blob: Blob;
  if (isPreview) {
    const sample = await api('/documents/' + encodeURIComponent(row.id) + '/download');
    blob = new Blob([sample.text], { type: sample.mime + ';charset=utf-8' });
  } else {
    const response = await fetch('/api/documents/' + encodeURIComponent(row.id) + '/download', { headers: { Authorization: 'Bearer ' + sessionStorage.getItem(TOKEN_KEY) } });
    if (!response.ok) throw new Error('Không tải được tệp gốc.');
    blob = await response.blob();
  }
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = row.filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
