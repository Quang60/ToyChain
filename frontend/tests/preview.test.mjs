import test from 'node:test';
import assert from 'node:assert/strict';
import { previewApi, previewNode, PREVIEW_PASSWORD, PREVIEW_READ_ONLY } from '../src/preview.ts';

const admin = { node: 'CENTRAL', token: 'preview:admin' };
const read = (path, context = admin) => previewApi(path, {}, context);

test('preview login, node selection and all screen data are available', async () => {
  assert.equal(previewNode('not-a-branch'), 'CENTRAL');
  const login = await previewApi('/auth/login', { method: 'POST', body: JSON.stringify({ username: 'admin', password: PREVIEW_PASSWORD }) }, { node: 'CENTRAL' });
  assert.equal(login.access_token, admin.token);
  assert.equal((await read('/info')).node, 'CENTRAL');
  assert.equal((await read('/products')).length, 16);
  assert.equal((await read('/users')).length, 9);
  for (const endpoint of ['/transactions?limit=500', '/partners', '/transfers', '/documents', '/feedback']) assert.ok((await read(endpoint)).length, endpoint);
  assert.equal((await read('/sync')).reconciliations.length, 4);
  await assert.rejects(read('/auth/me', { node: 'CENTRAL', token: 'real-token' }), /đăng nhập/);
  await assert.rejects(previewApi('/auth/login', { method: 'POST', body: JSON.stringify({ username: 'admin', password: 'wrong' }) }, admin), /không đúng/);
});

test('four branch views agree with central stock and revenue; transfers conserve stock', async () => {
  const central = await read('/dashboard');
  assert.deepEqual(central.branches.map(b => b.branch_id), ['DONG', 'TAY', 'NAM', 'BAC']);
  const transactions = await read('/transactions');
  const transfer = (await read('/transfers')).find(t => t.status === 'in_transit');
  let totalUnits = 0;
  for (const summary of central.branches) {
    const context = { ...admin, node: summary.branch_id };
    const dashboard = await read('/dashboard', context);
    assert.deepEqual(dashboard.branches, [summary]);
    const stock = await read('/stock', context);
    assert.ok(stock.every(s => s.branch_id === summary.branch_id && s.quantity >= 0));
    assert.equal(summary.stock_units, stock.reduce((sum, s) => sum + s.quantity, 0));
    const ledger = await read('/transactions', context);
    assert.equal(summary.net_revenue, ledger.reduce((sum, t) => sum + (t.kind === 'sale' ? t.total : t.kind === 'refund' ? -t.total : 0), 0));
    totalUnits += summary.stock_units;
  }
  const ledgerUnits = transactions.reduce((sum, t) => sum + t.lines.reduce((n, l) => n + l.quantity, 0) * (t.kind === 'sale' ? -1 : 1), 0);
  assert.equal(totalUnits + transfer.lines.reduce((sum, l) => sum + l.quantity, 0), ledgerUnits);
});

test('structured/unstructured search joins product, scoped stock, documents and feedback', async () => {
  const result = await read('/search?q=chung%20nhan%20an%20toan');
  assert.equal(result.documents.length, 1);
  assert.equal(result.products[0].sku, 'LEGO-001');
  assert.equal(result.products[0].stock.length, 4);
  const doc = result.documents[0];
  assert.equal(doc.product_id, result.products[0].id);
  const download = await read(`/documents/${doc.id}/download`);
  assert.equal(download.text, doc.text);
  const byFeedback = await read('/search?q=h%E1%BB%99p%20s%C3%A1ng%20t%E1%BA%A1o');
  assert.ok(byFeedback.feedback.length);
  const tay = { node: 'CENTRAL', token: 'preview:ql.tay' };
  assert.equal((await read('/search?q=chung%20nhan%20an%20toan', tay)).documents.length, 0);
  await assert.rejects(read(`/documents/${doc.id}/download`, tay), /Không tìm thấy/);
  assert.deepEqual((await read('/dashboard', tay)).branches.map(b => b.branch_id), ['TAY']);
  await assert.rejects(read('/stock', { ...tay, node: 'DONG' }), /chi nhánh khác/);
  await assert.rejects(read('/stock?branch=DONG', tay), /Không có quyền/);
});

test('preview rejects all writes and returns isolated snapshots without changing data', async () => {
  const before = await read('/stock');
  for (const [method, path] of [['POST', '/transactions'], ['POST', '/documents'], ['PUT', '/products/preview-product-1'], ['POST', '/sync/control'], ['DELETE', '/feedback/id']]) {
    await assert.rejects(previewApi(path, { method, body: '{}' }, admin), { message: PREVIEW_READ_ONLY });
  }
  const changed = await read('/stock');
  changed[0].quantity = -999;
  assert.deepEqual(await read('/stock'), before);
  await assert.rejects(read('/unknown-endpoint'), /chưa có dữ liệu/);
});
