/* 通用工具：接口调用、格式化、表格、KPI、文件选择器、提示 */
'use strict';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const STATE = { picks: {} };
let STATUS = null;

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ---------------- 接口 ---------------- */
async function api(name, params = {}) {
  let r;
  try {
    r = await fetch('/api/' + name, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params) });
  } catch (e) {
    throw new Error('无法连接本地服务，请确认「启动面板.bat」的窗口没有关闭');
  }
  let data = null;
  try { data = await r.json(); } catch (e) { /* 非 JSON */ }
  if (!r.ok || (data && data.error)) throw new Error((data && data.error) || ('请求失败（' + r.status + '）'));
  return data;
}

async function exportXlsx(name, params, kind, filename) {
  toast('正在生成 Excel…');
  try {
    const r = await fetch('/api/export/' + name, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({}, params, { _kind: kind, _filename: filename })),
    });
    if (!r.ok) {
      let msg = '导出失败（' + r.status + '）';
      try { msg = (await r.json()).error || msg; } catch (e) { /* ignore */ }
      throw new Error(msg);
    }
    saveBlob(await r.blob(), filename);
    toast('已导出 ' + filename, 'ok');
  } catch (e) { toast(e.message, 'err'); }
}

function saveBlob(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
}

function downloadCSV(tbl, name) {
  const cell = v => {
    if (v == null) return '';
    const s = Array.isArray(v) ? v.join(' ') : String(v);
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const lines = [tbl.columns].concat(tbl.rows).map(r => r.map(cell).join(','));
  saveBlob(new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' }), name);
}

/* ---------------- 格式化 ---------------- */
const isNum = v => typeof v === 'number' && isFinite(v);
const F = {
  // 小数 -> 百分比，例如 0.0123 -> +1.23%
  pct(v, d = 2, sign = true) { return isNum(v) ? (sign && v > 0 ? '+' : '') + (v * 100).toFixed(d) + '%' : '—'; },
  // 已是百分数的值，例如 1.23 -> +1.23%
  pv(v, d = 2, sign = true) { return isNum(v) ? (sign && v > 0 ? '+' : '') + v.toFixed(d) + '%' : '—'; },
  num(v, d = 4) {
    if (!isNum(v)) return '—';
    return Math.abs(v) >= 1000
      ? v.toLocaleString('zh-CN', { minimumFractionDigits: Math.min(d, 2), maximumFractionDigits: Math.min(d, 2) })
      : v.toFixed(d);
  },
  int(v) { return isNum(v) ? String(Math.round(v)) : '—'; },
  money(v) { return isNum(v) ? v.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) : '—'; },
};
const tone = v => (!isNum(v) || v === 0) ? '' : (v > 0 ? 'up' : 'down');
const short = s => String(s || '').replace(/[（(][^()（）]*[)）]$/, '');
const pad2 = n => String(n).padStart(2, '0');
function stamp() {
  const d = new Date();
  return `${d.getFullYear()}${pad2(d.getMonth() + 1)}${pad2(d.getDate())}_${pad2(d.getHours())}${pad2(d.getMinutes())}${pad2(d.getSeconds())}`;
}
function today() { const d = new Date(); return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`; }
function daysAgo(n) { const d = new Date(Date.now() - n * 864e5); return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`; }

/* ---------------- 小组件 ---------------- */
function setHead(title, sub) {
  $('#page-title').textContent = title;
  $('#page-sub').textContent = sub || '';
  document.title = title + ' · A股投资工具箱';
}

function kpis(items) {
  return items.map(it => `<div class="kpi"><div class="l">${esc(it.l)}</div>` +
    `<div class="v ${it.t || ''}" title="${esc(String(it.v).replace(/<[^>]+>/g, ''))}">${it.v}</div>` +
    (it.h ? `<div class="h" title="${esc(String(it.h))}">${it.h}</div>` : '') + '</div>').join('');
}
function skelKpis(n) { return Array.from({ length: n }, () => '<div class="kpi skel"><div class="l">&nbsp;</div><div class="v">0</div></div>').join(''); }
function pill(text, t = 'mid') { return `<span class="pill ${t}">${esc(text)}</span>`; }
function errHtml(e) { return `<div class="card err">⚠️ ${esc(e && e.message ? e.message : e)}</div>`; }

function segHtml(id, options, current) {
  return `<div class="seg" id="${id}">` + options.map(([v, l]) =>
    `<button type="button" data-v="${esc(v)}" class="${String(v) === String(current) ? 'on' : ''}">${esc(l)}</button>`).join('') + '</div>';
}
function bindSeg(sel, cb) {
  const el = typeof sel === 'string' ? $(sel) : sel;
  if (!el) return;
  el.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b || b.classList.contains('on')) return;
    $$('button', el).forEach(x => x.classList.toggle('on', x === b));
    cb(b.dataset.v);
  });
}
function tabsHtml(options, current) {
  return options.map(([v, l]) => `<button type="button" data-v="${v}" class="${v === current ? 'on' : ''}">${esc(l)}</button>`).join('');
}
const bindTabs = bindSeg;

function toast(msg, type = 'info') {
  const box = $('#toasts');
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; }, type === 'err' ? 6000 : 3200);
  setTimeout(() => el.remove(), type === 'err' ? 6400 : 3600);
}

async function runBtn(btn, label, fn) {
  const old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>${esc(label)}`;
  try { return await fn(); } catch (e) { toast(e.message, 'err'); throw e; } finally { btn.disabled = false; btn.innerHTML = old; }
}

async function withBusy(el, fn) {
  el.classList.add('busy');
  try { return await fn(); } finally { el.classList.remove('busy'); }
}

function readB64(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result);
    r.onerror = () => rej(new Error('读取文件失败：' + file.name));
    r.readAsDataURL(file);
  });
}

function sparkSvg(vals, w = 110, h = 28) {
  const v = (vals || []).filter(isNum);
  if (v.length < 2) return '—';
  const lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
  const pts = v.map((x, i) => `${(i / (v.length - 1) * (w - 2) + 1).toFixed(1)},${(h - 2 - (x - lo) / span * (h - 4)).toFixed(1)}`).join(' ');
  const c = v[v.length - 1] >= v[0] ? '#E5484D' : '#12A150';
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline fill="none" stroke="${c}" stroke-width="1.5" points="${pts}"/></svg>`;
}

/* ---------------- 表格 ----------------
 * tbl = {columns: [...], rows: [[...]]}
 * opt.fmt = {列名: 'pct'|'pctu'|'pv'|'pvu'|'n2'|'n3'|'n4'|'int'|'money'|'rsi'|'bar100'|'spark'|'status'|'bool'|'text'|function(v)->{html, cls}}
 */
function rowsToObjs(tbl) {
  if (!tbl || !tbl.rows) return [];
  return tbl.rows.map(r => Object.fromEntries(tbl.columns.map((c, i) => [c, r[i]])));
}

function autoSpec(col, v) {
  if (!isNum(v)) return 'text';
  if (/%/.test(col)) return 'pv';
  if (Number.isInteger(v)) return 'int';
  return Math.abs(v) >= 1000 ? 'n2' : 'n4';
}

function fmtCell(v, spec, col) {
  if (typeof spec === 'function') return spec(v);
  spec = spec || autoSpec(col, v);
  const num = { cls: 'num' };
  switch (spec) {
    case 'pct': return { html: F.pct(v), cls: 'num ' + tone(v) };
    case 'pctu': return { html: F.pct(v, 2, false), cls: 'num' };
    case 'pv': return { html: F.pv(v), cls: 'num ' + tone(v) };
    case 'pvu': return { html: F.pv(v, 2, false), cls: 'num' };
    case 'n2': return Object.assign({ html: F.num(v, 2) }, num);
    case 'n3': return Object.assign({ html: F.num(v, 3) }, num);
    case 'n4': return Object.assign({ html: F.num(v, 4) }, num);
    case 'int': return Object.assign({ html: F.int(v) }, num);
    case 'money': return Object.assign({ html: F.money(v) }, num);
    case 'rsi': {
      if (!isNum(v)) return { html: '—' };
      const c = v > 70 ? 'var(--up)' : v < 30 ? 'var(--down)' : 'var(--primary)';
      return { html: `<span class="bar"><i style="width:${Math.max(0, Math.min(100, v))}%;background:${c}"></i></span>${v.toFixed(1)}` };
    }
    case 'bar100': {
      if (!isNum(v)) return { html: '—' };
      return { html: `<span class="bar"><i style="width:${Math.max(0, Math.min(100, v))}%"></i></span>${v.toFixed(2)}%` };
    }
    case 'spark': return { html: sparkSvg(v) };
    case 'status': {
      const t = { '成功': 'ok', '正常': 'mid', '超买': 'up', '超卖': 'down', '失败': 'bad', '无数据': 'mid', '数据不足': 'mid' }[v] || 'mid';
      return { html: v == null ? '—' : pill(v, t) };
    }
    case 'bool': return { html: v ? '<span class="down">✓ 是</span>' : '<span class="note">否</span>' };
    case 'wrap': return { html: esc(v == null ? '' : v), cls: 'wrap' };
    default: return { html: v == null || v === '' ? '<span class="note">—</span>' : esc(v) };
  }
}

function renderTable(el, tbl, opt = {}) {
  if (typeof el === 'string') el = $(el);
  if (!el) return;
  if (!tbl || !tbl.columns || !tbl.rows || !tbl.rows.length) { el.innerHTML = '<div class="empty">暂无数据</div>'; return; }
  const fmt = opt.fmt || {};
  const hide = new Set(opt.hide || []);
  const cols = tbl.columns.map((c, i) => ({ c, i })).filter(x => !hide.has(x.c));
  const st = { k: null, asc: false };
  const numCol = {};
  cols.forEach(x => {
    const s = fmt[x.c];
    const sample = (tbl.rows.find(r => r[x.i] != null) || [])[x.i];
    numCol[x.i] = (s && !['text', 'status', 'bool', 'spark', 'wrap', 'rsi', 'bar100'].includes(s) && typeof s !== 'function') || (!s && isNum(sample));
  });
  const cmp = (a, b) => {
    if (a == null && b == null) return 0;
    if (a == null) return 1;
    if (b == null) return -1;
    if (isNum(a) && isNum(b)) return a - b;
    return String(a).localeCompare(String(b), 'zh-CN');
  };
  const draw = () => {
    let rows = tbl.rows;
    if (st.k != null) {
      rows = rows.slice().sort((a, b) => {
        const r = cmp(a[st.k], b[st.k]);
        return (a[st.k] == null || b[st.k] == null) ? r : r * (st.asc ? 1 : -1);
      });
    }
    const th = cols.map(x => `<th data-k="${x.i}" class="${numCol[x.i] ? 'num' : ''}">${esc(x.c)}${st.k === x.i ? (st.asc ? ' ↑' : ' ↓') : ''}</th>`).join('');
    const body = rows.map((r, ri) => `<tr data-r="${ri}" class="${opt.onRow ? 'click' : ''}">` + cols.map(x => {
      const c = fmtCell(r[x.i], fmt[x.c], x.c);
      return `<td class="${c.cls || ''}">${c.html}</td>`;
    }).join('') + '</tr>').join('');
    el.innerHTML = `<div class="tbl-wrap" style="max-height:${opt.height || 520}px"><table class="tbl"><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table></div>`;
    $$('th', el).forEach(t => t.onclick = () => {
      const k = +t.dataset.k;
      if (st.k === k) st.asc = !st.asc; else { st.k = k; st.asc = false; }
      draw();
    });
    if (opt.onRow) {
      $$('tbody tr', el).forEach(tr => tr.onclick = () => {
        const r = rows[+tr.dataset.r];
        opt.onRow(Object.fromEntries(tbl.columns.map((c, i) => [c, r[i]])));
      });
    }
  };
  draw();
}

/* ---------------- 文件选择器 ---------------- */
class FilePicker {
  constructor(el, opt) {
    this.el = typeof el === 'string' ? $(el) : el;
    this.opt = Object.assign({ multi: false, key: 'default', defaultAll: false, preselect: null, defaultCount: 2, onChange: () => {} }, opt);
    this.files = [];
    this.sel = new Set();
  }
  async init() { await this.reload(); return this; }
  async reload() {
    try {
      const r = await api('files');
      this.files = r.files;
      this.dir = r.dir;
    } catch (e) { this.files = []; this.error = e.message; }
    const names = this.files.map(f => f.name);
    let init = this.opt.preselect ? [].concat(this.opt.preselect) : STATE.picks[this.opt.key];
    this.opt.preselect = null;
    init = (init || []).filter(n => names.includes(n));
    if (!init.length) init = this.opt.multi ? (this.opt.defaultAll ? names : names.slice(0, this.opt.defaultCount)) : names.slice(0, 1);
    if (!this.opt.multi) init = init.slice(0, 1);
    this.sel = new Set(init);
    STATE.picks[this.opt.key] = [...this.sel];
    this.render();
  }
  get value() {
    return this.opt.multi ? this.files.map(f => f.name).filter(n => this.sel.has(n)) : ([...this.sel][0] || null);
  }
  uploadHtml() { return '<label class="link">⬆ 上传文件<input type="file" hidden accept=".csv,.xlsx,.xls" multiple></label>'; }
  render() {
    if (!this.files.length) {
      this.el.innerHTML = `<div class="picker-empty">${this.error ? esc(this.error) + '。' : '数据文件夹里还没有行情文件。'}<a href="#/data">去数据中心下载</a> · ${this.uploadHtml()}</div>`;
    } else if (this.opt.multi) {
      this.el.innerHTML = '<div class="chips">' + this.files.map(f =>
        `<span class="chip ${this.sel.has(f.name) ? 'on' : ''}" data-n="${esc(f.name)}" title="${esc(f.name)} · ${esc(f.mtime)}">${esc(f.label)}</span>`).join('') +
        `</div><div class="picker-tools"><span class="link" data-a="all">全选</span><span class="link" data-a="none">清空</span>${this.uploadHtml()}` +
        `<span class="note">已选 ${this.sel.size} / ${this.files.length}</span></div>`;
      $$('.chip', this.el).forEach(c => c.onclick = () => {
        const n = c.dataset.n;
        if (this.sel.has(n)) this.sel.delete(n); else this.sel.add(n);
        this.render(); this.changed();
      });
      $$('[data-a]', this.el).forEach(a => a.onclick = () => {
        this.sel = new Set(a.dataset.a === 'all' ? this.files.map(f => f.name) : []);
        this.render(); this.changed();
      });
    } else {
      this.el.innerHTML = '<div class="picker-row"><select>' + this.files.map(f =>
        `<option value="${esc(f.name)}" ${this.sel.has(f.name) ? 'selected' : ''}>${esc(f.label)}${f.label !== f.name.replace(/\.\w+$/, '') ? '　·　' + esc(f.name) : ''}</option>`).join('') +
        `</select>${this.uploadHtml()}</div>`;
      $('select', this.el).onchange = e => { this.sel = new Set([e.target.value]); this.changed(); };
    }
    const inp = $('input[type=file]', this.el);
    if (inp) inp.onchange = () => this.upload(inp.files);
  }
  async upload(fileList) {
    let added = 0;
    for (const f of Array.from(fileList)) {
      try {
        const r = await api('upload', { name: f.name, content: await readB64(f) });
        toast((r.overwritten ? '已覆盖 ' : '已上传 ') + f.name, 'ok');
        if (this.opt.multi) this.sel.add(f.name); else this.sel = new Set([f.name]);
        added++;
      } catch (e) { toast(e.message, 'err'); }
    }
    STATE.picks[this.opt.key] = [...this.sel];
    await this.reload();
    if (added) this.changed();
    refreshStatus();
  }
  changed() { STATE.picks[this.opt.key] = [...this.sel]; this.opt.onChange(this.value); }
}

/* ---------------- 侧栏状态 ---------------- */
async function refreshStatus() {
  try {
    STATUS = await api('status');
    $('#side-foot').innerHTML =
      `<div class="row"><span class="dot ${STATUS.tickflow_key ? 'ok' : 'warn'}"></span>${STATUS.tickflow_key ? 'TickFlow 密钥已读取' : '未设置密钥（免费版）'}</div>` +
      `<div class="row"><span class="dot ${STATUS.data_dir_exists ? 'ok' : 'warn'}"></span>数据文件 ${STATUS.file_count} 个</div>` +
      `<div class="path" title="${esc(STATUS.data_dir)}">${esc(STATUS.data_dir)}</div>`;
  } catch (e) {
    $('#side-foot').innerHTML = `<div class="row"><span class="dot warn"></span>${esc(e.message)}</div>`;
  }
  return STATUS;
}
