/* 页面与路由 */
'use strict';

let ROUTE_TOKEN = 0;
const alive = tk => tk === ROUTE_TOKEN;

const MODULES = [
  { r: 'data', ic: '📥', t: '数据中心', d: 'TickFlow 下载 ETF / A股 / 美股日线（前、后复权），东财场外基金历史净值，微盘股 BK1158 市值最小名单。', tags: ['ETFdataget', 'tickflow_US', 'jjjz', 'wpg30'] },
  { r: 'single', ic: '🔍', t: '单品种分析', d: '滚动年化收益、年度涨幅与回撤、全部回撤波段、多周期均线、RSI 与历史价格百分位。', tags: ['3年滚动年化', '均线工具', 'RSI百分位'] },
  { r: 'market', ic: '🌐', t: '指数与期货', d: '主要指数 MA 偏离率横向对比；股指 / 商品期货不同合约的价差走势与统计。', tags: ['指数MA20', '期货价差'] },
  { r: 'backtest', ic: '🔁', t: '轮动回测', d: '多基金动量轮动 v4（前 N 名、周/月调仓、滑点手续费）与双标的周度动量轮动。', tags: ['rotation_v4', 'dongliang'] },
  { r: 'spmo', ic: '🏆', t: 'SPMO 选基', d: '标准 / 三周期等权 / 40-35-25 加权三种风险调整动量评分，附 RSI 状态与建议权重。', tags: ['SPMO', '多周期', '+RSI'] },
  { r: 'settings', ic: '⚙️', t: '设置', d: '修改数据文件夹与报告输出文件夹，查看 TickFlow 密钥状态。', tags: ['数据目录', 'API 密钥'] },
];

/* ================================================================ 总览 */
async function pageOverview(v, q, tk) {
  setHead('总览', '数据文件夹中所有品种的最新状态，点击表格行可直接进入单品种分析');
  v.innerHTML = `<div class="kpis" id="ov-kpi">${skelKpis(4)}</div>
    <div class="grid g-7-5">
      <div class="card"><h3>📋 品种快照</h3><div id="ov-tbl" class="busy"></div></div>
      <div class="card"><h3>📈 近一年收益对比 <span class="sub">起点归零</span></h3><div id="ov-chart" class="chart" style="height:440px"></div></div>
    </div>
    <div class="sec-title">🧭 功能模块</div>
    <div class="grid g3">${MODULES.map(m => `<a class="mod card" href="#/${m.r}"><div class="mod-ic">${m.ic}</div><div><h4>${m.t}</h4><p>${m.d}</p>
      <div>${m.tags.map(t => `<span class="tag">${t}</span>`).join('')}</div></div></a>`).join('')}</div>`;
  let r;
  try { r = await api('overview'); } catch (e) { $('#ov-tbl').classList.remove('busy'); $('#ov-tbl').innerHTML = errHtml(e); $('#ov-kpi').innerHTML = ''; return; }
  if (!alive(tk)) return;
  $('#ov-tbl').classList.remove('busy');
  if (!r.rows.length) {
    $('#ov-kpi').innerHTML = '';
    $('#ov-tbl').innerHTML = `<div class="empty">数据文件夹 <code>${esc(r.data_dir)}</code> 里还没有可识别的行情文件。<br><a class="btn primary" href="#/data">去数据中心下载</a></div>`;
    return;
  }
  const rows = r.rows;
  const latest = rows.map(x => x.last_date).sort().pop();
  const best = rows.filter(x => isNum(x.r1m)).sort((a, b) => b.r1m - a.r1m)[0];
  const ob = rows.filter(x => isNum(x.rsi) && x.rsi > 70), os = rows.filter(x => isNum(x.rsi) && x.rsi < 30);
  const names = arr => arr.map(x => esc(short(x.name))).slice(0, 3).join('、') || '无';
  $('#ov-kpi').innerHTML = kpis([
    { l: '跟踪品种', v: rows.length, h: '数据最新到 ' + latest },
    { l: '近 1 月最强', v: best ? esc(short(best.name)) : '—', h: best ? F.pct(best.r1m) : '' },
    { l: '超买（RSI > 70）', v: ob.length + ' 只', t: ob.length ? 'up' : '', h: names(ob) },
    { l: '超卖（RSI < 30）', v: os.length + ' 只', t: os.length ? 'down' : '', h: names(os) },
  ]);
  const tbl = {
    columns: ['品种', '最新日期', '最新价', '近1月', '近3月', '今年以来', '近1年', '距高点', 'RSI(14)', '近一年走势'],
    rows: rows.map(x => [x.name, x.last_date, x.last, x.r1m, x.r3m, x.ytd, x.r1y, x.from_high, x.rsi, x.spark]),
  };
  renderTable('#ov-tbl', tbl, {
    height: 440,
    fmt: { '最新价': 'n4', '近1月': 'pct', '近3月': 'pct', '今年以来': 'pct', '近1年': 'pct', '距高点': 'pct', 'RSI(14)': 'rsi', '近一年走势': 'spark', '最新日期': 'text' },
    onRow: o => { const row = rows.find(x => x.name === o['品种']); if (row) location.hash = '#/single?file=' + encodeURIComponent(row.file); },
  });
  chartLinesTime($('#ov-chart'), r.curves, { pct: true, height: 440, zero: true });
}

/* ================================================================ 数据中心 */
async function pageData(v) {
  setHead('数据中心', '下载的数据保存到「数据文件夹」，各分析页可以直接选用');
  const tab = STATE.dataTab || 'cn';
  v.innerHTML = `<div class="tabs" id="dc-tabs">${tabsHtml([['cn', '🇨🇳 ETF / A股'], ['us', '🇺🇸 美股'], ['fund', '💰 场外基金净值'], ['board', '🔬 微盘股 BK1158']], tab)}</div><div id="dc-body"></div>`;
  const show = t => { disposeCharts(); ({ cn: dcKline, us: dcKline, fund: dcFund, board: dcBoard })[t]($('#dc-body'), t); };
  bindTabs('#dc-tabs', t => { STATE.dataTab = t; show(t); });
  show(tab);
}

function dcKline(b, t) {
  const us = t === 'us';
  const P = STATE['dc_' + t] = STATE['dc_' + t] || {
    codes: us ? 'SPMO, QQQ, SPY' : '512890, 159201, 159545, 159655, 159501, 518850, 513260, 159915',
    adjust: 'forward', inception: true, start: daysAgo(3650), end: today(),
  };
  b.innerHTML = `<div class="card">
    <div class="note">${us ? '来源：tickflow_USdata_fetcher.py · 数据源 TickFlow，自动加 .US 后缀，前复权' : '来源：ETFdataget.py / ETFdataget-后复权.py / datagetfree.py · 数据源 TickFlow'}</div>
    <div class="form" style="margin-top:12px"><div class="field grow"><label>代码（逗号、空格或换行分隔${us ? '' : '，可以不写 .SH / .SZ 后缀'}）</label><textarea id="k-codes" rows="3">${esc(P.codes)}</textarea></div></div>
    <div class="form" style="margin-top:12px">
      ${us ? '' : `<div class="field"><label>复权方式</label>${segHtml('k-adj', [['forward', '前复权'], ['backward', '后复权'], ['none', '不复权']], P.adjust)}</div>`}
      <div class="field"><label>&nbsp;</label><label class="check"><input type="checkbox" id="k-inc" ${P.inception ? 'checked' : ''}> 成立以来</label></div>
      <div class="field"><label>开始日期</label><input type="date" id="k-s" value="${P.start}" ${P.inception ? 'disabled' : ''}></div>
      <div class="field"><label>结束日期</label><input type="date" id="k-e" value="${P.end}"></div>
      <div class="field"><label>&nbsp;</label><button class="btn primary" id="k-go">⬇ 开始下载</button></div>
    </div>
    ${us ? '' : '<div class="note" style="margin-top:10px">💡 前复权适合看走势；后复权适合回测，能算出真实收益。后复权文件名会带「-后复权」。</div>'}
  </div><div id="k-res"></div>`;
  bindSeg('#k-adj', x => { P.adjust = x; });
  $('#k-inc').onchange = e => { P.inception = e.target.checked; $('#k-s').disabled = P.inception; };
  $('#k-go').onclick = () => runBtn($('#k-go'), '下载中…', async () => {
    P.codes = $('#k-codes').value; P.start = $('#k-s').value; P.end = $('#k-e').value;
    const r = await api('dl_tickflow', { codes: P.codes, market: us ? 'US' : 'CN', adjust: us ? 'forward' : P.adjust, start: P.inception ? null : P.start, end: P.end || null });
    const ok = r.table.rows.filter(x => x[1] === '成功').length;
    $('#k-res').innerHTML = `<div class="card"><h3>下载结果 <span class="sub">成功 ${ok} / ${r.table.rows.length} · 保存到 ${esc(r.dir)}</span></h3><div id="k-tbl"></div></div>
      ${Object.keys(r.curves).length ? '<div class="card"><h3>走势预览 <span class="sub">起点归一</span></h3><div id="k-chart" class="chart"></div></div>' : ''}`;
    renderTable('#k-tbl', r.table, { fmt: { '状态': 'status', '文件': 'wrap' } });
    if (Object.keys(r.curves).length) chartLinesTime($('#k-chart'), r.curves, { height: 360 });
    toast(`下载完成：成功 ${ok} 个`, ok ? 'ok' : 'err');
    refreshStatus();
  }).catch(() => {});
}

function dcFund(b) {
  const P = STATE.dc_fund = STATE.dc_fund || { codes: '110020, 161725', mode: 'all' };
  b.innerHTML = `<div class="card">
    <div class="note">来源：fund_complete_data_get.py / 批量脚本/jjjz.py · 数据源 东方财富基金净值接口</div>
    <div class="form" style="margin-top:12px">
      <div class="field grow"><label>基金代码（可批量）</label><textarea id="f-codes" rows="2">${esc(P.codes)}</textarea></div>
      <div class="field"><label>范围</label>${segHtml('f-mode', [['all', '全部历史'], ['latest', '最新 20 条']], P.mode)}</div>
      <div class="field"><label>&nbsp;</label><button class="btn primary" id="f-go">⬇ 获取净值</button></div>
    </div></div><div id="f-res"></div>`;
  bindSeg('#f-mode', x => { P.mode = x; });
  $('#f-go').onclick = () => runBtn($('#f-go'), '获取中…', async () => {
    P.codes = $('#f-codes').value;
    const r = await api('dl_fund', { codes: P.codes, latest_only: P.mode === 'latest' });
    const prev = Object.entries(r.previews);
    $('#f-res').innerHTML = `<div class="card"><h3>获取结果 <span class="sub">保存到 ${esc(r.dir)}</span></h3><div id="f-tbl"></div></div>` +
      prev.map(([c], i) => `<div class="card"><h3>${esc(c)} 累计净值与回撤</h3><div id="f-c${i}" class="chart"></div></div>`).join('');
    renderTable('#f-tbl', r.table, { fmt: { '状态': 'status', '最新累计净值': 'n4', '文件': 'wrap' } });
    prev.forEach(([c, p], i) => chartPriceDD($(`#f-c${i}`), p.dates, p.nav, p.dd, c + ' 累计净值'));
    refreshStatus();
  }).catch(() => {});
}

function dcBoard(b) {
  const P = STATE.dc_board = STATE.dc_board || { board: 'BK1158', top: 30 };
  b.innerHTML = `<div class="card">
    <div class="note">来源：wpg.py / wpg30.py · 东方财富板块成分，按总市值升序</div>
    <div class="form" style="margin-top:12px">
      <div class="field"><label>板块代码</label><input id="b-code" value="${esc(P.board)}" style="width:140px"></div>
      <div class="field"><label>取市值最小的前 N 只</label><input type="number" id="b-top" min="5" max="300" value="${P.top}"></div>
      <div class="field"><label>&nbsp;</label><button class="btn primary" id="b-go">获取名单</button></div>
    </div></div><div id="b-res"></div>`;
  const render = r => {
    const s = r.stats;
    $('#b-res').innerHTML = `<div class="kpis">${kpis([
      { l: '成分数量', v: s.count, h: '板块 ' + esc(r.board) },
      { l: '市值中位数', v: F.num(s.median, 2) + ' 亿' },
      { l: '最小市值', v: F.num(s.min, 2) + ' 亿', h: esc(s.min_name) },
      { l: '今日上涨占比', v: F.pct(s.up_ratio, 0, false), t: s.up_ratio > 0.5 ? 'up' : s.up_ratio < 0.5 ? 'down' : '' },
    ])}</div>
    <div class="grid g-7-5"><div class="card"><h3>名单</h3><div id="b-tbl"></div></div><div class="card"><h3>总市值（亿元）</h3><div id="b-chart"></div></div></div>
    <div class="actions"><button class="btn" id="b-csv">⬇ 下载 CSV</button><button class="btn" id="b-save">💾 保存到数据文件夹</button></div>`;
    const maxCap = Math.max(...r.table.rows.map(x => x[r.table.columns.indexOf('总市值(亿元)')] || 0));
    renderTable('#b-tbl', r.table, {
      height: 560,
      fmt: { '排名': 'int', '代码': 'text', '最新价': 'n2', '涨跌幅(%)': 'pv',
        '总市值(亿元)': x => ({ html: `<span class="bar"><i style="width:${isNum(x) ? x / maxCap * 100 : 0}%"></i></span>${F.num(x, 2)}` }) },
    });
    const objs = rowsToObjs(r.table);
    chartHBar($('#b-chart'), objs.map(o => o['名称']), objs.map(o => o['总市值(亿元)']), { color: C.primary, fmt: vf.p2 });
    $('#b-csv').onclick = () => downloadCSV(r.table, `${r.board}_lowest_${s.count}.csv`);
    $('#b-save').onclick = () => runBtn($('#b-save'), '保存中…', async () => {
      const x = await api('board_save', { board: P.board, top_n: P.top });
      toast('已保存：' + x.path, 'ok');
    }).catch(() => {});
  };
  if (STATE.boardRes) render(STATE.boardRes);
  $('#b-go').onclick = () => runBtn($('#b-go'), '获取中…', async () => {
    P.board = $('#b-code').value.trim() || 'BK1158'; P.top = +$('#b-top').value || 30;
    STATE.boardRes = await api('board', { board: P.board, top_n: P.top, refresh: true });
    render(STATE.boardRes);
  }).catch(e => { $('#b-res').innerHTML = errHtml(e.message + '。如持续失败，请检查网络或代理设置。'); });
}

/* ================================================================ 单品种分析 */
async function pageSingle(v, q, tk) {
  setHead('单品种分析', '适用于 ETF K线（收盘价）和场外基金（累计净值）');
  const P = STATE.single = STATE.single || { years: 3, hl: true, ma: [20, 60, 120, 250], base: '2024-09-30', tab: 'roll', start: '', end: '' };
  v.innerHTML = `<div class="card"><div class="form">
      <div class="field grow"><label>数据文件</label><div id="sg-pick"></div></div>
      <div class="field"><label>开始日期</label><input type="date" id="sg-s"></div>
      <div class="field"><label>结束日期</label><input type="date" id="sg-e"></div>
      <div class="field"><label>&nbsp;</label><button class="btn" id="sg-all">全部区间</button></div>
    </div></div><div id="sg-main"></div>`;
  let D = null, seq = 0;
  const params = () => ({ file: picker.value, start: P.start || null, end: P.end || null, years: P.years, high_low: P.hl, ma: P.ma, base_date: P.base });
  const picker = new FilePicker('#sg-pick', { key: 'single', preselect: q.get('file'), onChange: () => { P.start = P.end = ''; run(); } });
  await picker.init();
  if (!alive(tk)) return;
  $('#sg-s').onchange = e => { P.start = e.target.value; run(); };
  $('#sg-e').onchange = e => { P.end = e.target.value; run(); };
  $('#sg-all').onclick = () => { P.start = P.end = ''; run(); };

  async function run() {
    const main = $('#sg-main');
    if (!picker.value) { main.innerHTML = ''; return; }
    const my = ++seq;
    main.classList.add('busy');
    try {
      const d = await api('single', params());
      if (my !== seq || !alive(tk)) return;
      D = d;
      ['#sg-s', '#sg-e'].forEach(s => { $(s).min = D.range.min; $(s).max = D.range.max; });
      $('#sg-s').value = D.start; $('#sg-e').value = D.end;
      renderMain();
    } catch (e) {
      if (my === seq) { disposeCharts(); main.innerHTML = errHtml(e); }
    } finally { if (my === seq) main.classList.remove('busy'); }
  }

  function renderMain() {
    disposeCharts();
    const s = D.stats;
    $('#sg-main').innerHTML = `<div class="kpis">${kpis([
      { l: '品种', v: esc(D.name), h: '价格列：' + esc(D.price_label) },
      { l: '最新价', v: F.num(s['最新价']), h: s['最新日'] },
      { l: '区间涨幅', v: F.pct(s['区间涨幅']), t: tone(s['区间涨幅']), h: '自 ' + s['起始日'] },
      { l: '年化收益', v: F.pct(s['年化收益']), t: tone(s['年化收益']), h: '年化波动 ' + F.pct(s['年化波动'], 2, false) },
      { l: '最大回撤', v: F.pct(s['最大回撤']), t: 'down', h: '当前回撤 ' + F.pct(s['当前回撤']) },
    ])}</div>
    <div class="tabs" id="sg-tabs">${tabsHtml([['roll', '📈 滚动年化 & 回撤'], ['ma', '〰️ 均线系统'], ['rsi', '🌡️ RSI & 价格百分位']], P.tab)}</div>
    <div id="sg-body"></div>`;
    bindTabs('#sg-tabs', t => { P.tab = t; disposeCharts(); renderTab(); });
    renderTab();
  }
  function renderTab() { ({ roll: tabRoll, ma: tabMA, rsi: tabRSI })[P.tab]($('#sg-body')); }

  function tabRoll(b) {
    const rs = D.roll_stats, cur = D.current_dd;
    b.innerHTML = `<div class="card"><div class="form">
        <div class="field"><label>滚动窗口</label>${segHtml('sg-years', [[1, '1 年'], [2, '2 年'], [3, '3 年'], [5, '5 年']], P.years)}</div>
        <div class="field"><label>回撤波段识别</label><label class="check ${D.has_hl ? '' : 'dim'}"><input type="checkbox" id="sg-hl" ${P.hl && D.has_hl ? 'checked' : ''} ${D.has_hl ? '' : 'disabled'}> 按 K 线最高 / 最低价（ETF 口径）</label></div>
        <div class="note grow" style="align-self:center">来源：fund_3-Year Rolling / fund_analysis_gui_fixed / ETF-3-Year Rolling / 3yearsanddrawdown${D.has_hl ? '' : ' · 场外基金只有净值，自动按净值识别'}</div>
      </div></div>
      ${rs ? `<div class="kpis">${kpis([
        { l: '最新滚动年化', v: F.pct(rs.latest), t: tone(rs.latest), h: D.years + ' 年窗口' },
        { l: '历史最高', v: F.pct(rs.max), t: 'up', h: rs.max_date },
        { l: '历史最低', v: F.pct(rs.min), t: 'down', h: rs.min_date },
        { l: '均值', v: F.pct(rs.mean), t: tone(rs.mean) },
        { l: '正收益占比', v: F.pct(rs.pos_ratio, 1, false), h: `持有满 ${D.years} 年赚钱的概率` },
      ])}</div>` : `<div class="card note">数据不足 ${D.years} 年，无法计算滚动年化收益。</div>`}
      <div class="card"><h3>价格与回撤</h3><div id="c-pdd" class="chart"></div></div>
      ${rs ? `<div class="card"><h3>${D.years} 年滚动年化收益率</h3><div id="c-roll" class="chart"></div></div>` : ''}
      <div class="grid g2">
        <div class="card"><h3>最大的 5 次回撤波段</h3><div id="c-ddp" class="chart"></div></div>
        <div class="card"><h3>年度涨幅 & 年内最大回撤</h3><div id="c-yr" class="chart"></div></div>
      </div>
      <div class="card"><h3>回撤波段明细 <span class="sub">按深度排序，最多 60 条</span>
        ${cur ? `<span style="margin-left:auto;font-weight:400;font-size:13px">当前处于回撤中：自 <b>${cur.start}</b> 起最深 <b class="down">${F.pv(cur.depth)}</b>，谷底后已过 <b>${cur.days}</b> 天 ${pill('未修复', 'down')}</span>` : ''}</h3>
        <div id="t-per"></div></div>
      <details class="card"><summary>年度明细表</summary><div id="t-yr" style="margin-top:12px"></div></details>
      <div class="actions"><button class="btn" id="x-roll">⬇ 导出 Excel（滚动年化 + 年度统计 + 回撤波段）</button></div>`;
    bindSeg('#sg-years', y => { P.years = +y; run(); });
    const hl = $('#sg-hl');
    if (hl) hl.onchange = e => { P.hl = e.target.checked; run(); };
    chartPriceDD($('#c-pdd'), D.series.dates, D.series.price, D.series.drawdown, short(D.name));
    if (rs) chartRolling($('#c-roll'), D.series.dates, D.series.rolling, D.years);
    chartDDPeriods($('#c-ddp'), D.series.dates, D.series.price, D.top_periods);
    chartYearly($('#c-yr'), D.yearly);
    renderTable('#t-per', D.periods, { height: 340, fmt: { '是否已修复': 'bool', '开始': 'text', '谷底': 'text', '修复完成': 'text' } });
    renderTable('#t-yr', D.yearly, { fmt: { '年份': 'int', '是否已修复': 'bool', '最大回撤日期': 'text' } });
    $('#x-roll').onclick = () => exportXlsx('single', params(), 'roll', `${short(D.name)}_滚动年化与回撤_${stamp()}.xlsx`);
  }

  function tabMA(b) {
    const M = D.ma;
    const pt = { '多头排列': 'up', '空头排列': 'down', '交织震荡': 'mid' };
    b.innerHTML = `<div class="card"><div class="form">
        <div class="field grow"><label>均线周期（点击切换）</label><div class="chips" id="ma-chips">${[5, 10, 20, 30, 60, 120, 250].map(n =>
          `<span class="chip ${P.ma.includes(n) ? 'on' : ''}" data-n="${n}">MA${n}</span>`).join('')}</div></div>
        <div class="note" style="align-self:center">来源：fund_20&amp;60&amp;120&amp;250day_moving_average.py</div>
      </div></div>
      <div class="kpis">${kpis(M.latest.map(x => ({ l: 'MA' + x.n, v: F.num(x.ma), t: tone(x.dev),
        h: isNum(x.dev) ? `偏离 ${F.pv(x.dev)} · ${x.dev > 0 ? '价格在上方' : '价格在下方'}` : '数据不足' })))}</div>
      <div class="card"><h3>价格与均线 ${M.pattern ? '<span class="sub">均线形态</span>' + pill(M.pattern, pt[M.pattern]) : ''}</h3><div id="c-ma" class="chart"></div></div>
      <div class="actions"><button class="btn" id="x-ma">⬇ 导出 Excel（均线与偏离度）</button></div>`;
    $$('#ma-chips .chip').forEach(c => c.onclick = () => {
      const n = +c.dataset.n;
      const s = new Set(P.ma);
      if (s.has(n)) { if (s.size > 1) s.delete(n); } else s.add(n);
      P.ma = [...s].sort((a, b2) => a - b2);
      run();
    });
    chartMA($('#c-ma'), D.series.dates, D.series.price, M.lines, short(D.name));
    $('#x-ma').onclick = () => exportXlsx('single', params(), 'ma', `${short(D.name)}_均线_${stamp()}.xlsx`);
  }

  function tabRSI(b) {
    const I = D.indicator, L = I.latest;
    const st = { '超买': 'up', '超卖': 'down' }[L.status] || '';
    b.innerHTML = `<div class="card"><div class="form">
        <div class="field"><label>自定义涨幅基准日</label><input type="date" id="rsi-base" value="${esc(P.base)}"></div>
        <div class="note grow" style="align-self:center">原脚本固定为 2024-09-30，这里可以改 · 来源：fund_RSI&amp;percentile_analyzer.py</div>
      </div></div>
      <div class="grid g-side">
        <div class="card"><div id="g-rsi"></div><div id="g-pct"></div></div>
        <div>
          <div class="kpis">${kpis([
            { l: 'RSI 状态', v: esc(L.status), t: st, h: isNum(L.rsi) ? 'RSI = ' + L.rsi.toFixed(1) : '' },
            { l: '20 日涨幅', v: F.pv(L.r20), t: tone(L.r20), h: '60 日 ' + F.pv(L.r60) },
            { l: '今年以来', v: F.pv(L.ytd), t: tone(L.ytd) },
            { l: '自基准日', v: F.pv(L.base), t: tone(L.base), h: esc(P.base) },
            { l: '动量 / 波动（20 日）', v: isNum(L.mv) ? L.mv.toFixed(2) : '—', t: tone(L.mv), h: '20 日波动 ' + F.pv(L.vol20, 2, false) },
          ])}</div>
          <div class="card"><h3>价格 · RSI(14) · 历史价格百分位</h3><div id="c-rsi" class="chart"></div></div>
        </div>
      </div>
      <details class="card"><summary>逐日指标表（最近 250 个交易日）</summary><div id="t-ind" style="margin-top:12px"></div></details>
      <div class="actions"><button class="btn" id="x-rsi">⬇ 导出 Excel（每日完整指标）</button></div>`;
    $('#rsi-base').onchange = e => { P.base = e.target.value || '2024-09-30'; run(); };
    chartGauge($('#g-rsi'), L.rsi, 'RSI(14)');
    chartGauge($('#g-pct'), L.pct, '历史价格百分位', 20, 80);
    chartRSI($('#c-rsi'), D.series.dates, D.series.price, I.rsi, I.pct);
    renderTable('#t-ind', D.indicator_table, { height: 420, fmt: { '日期': 'text', '价格': 'n4', 'RSI(14)': 'n2', '价格百分位': 'n2', '动量/波动(20日)': 'n2', '状态': 'status' } });
    $('#x-rsi').onclick = () => exportXlsx('single', params(), 'rsi', `${short(D.name)}_RSI百分位_${stamp()}.xlsx`);
  }

  run();
}

/* ================================================================ 指数与期货 */
async function pageMarket(v) {
  setHead('指数与期货', '需要联网：指数数据来自 TickFlow + AkShare，期货来自 AkShare（新浪）');
  const tab = STATE.mkTab || 'idx';
  v.innerHTML = `<div class="tabs" id="mk-tabs">${tabsHtml([['idx', '📐 指数 MA 偏离率'], ['fut', '⚖️ 期货合约价差']], tab)}</div><div id="mk-body"></div>`;
  const show = t => { disposeCharts(); (t === 'idx' ? mkIndex : mkFutures)($('#mk-body')); };
  bindTabs('#mk-tabs', t => { STATE.mkTab = t; show(t); });
  show(tab);
}

function mkIndex(b) {
  const all = (STATUS && STATUS.index_names) || [];
  const P = STATE.idx = STATE.idx || { names: all.slice(), ma: 20, days: 60 };
  b.innerHTML = `<div class="card">
    <div class="note">来源：指数MA20分析工具_分列版.py · 偏离率 = (收盘 - MA) ÷ MA</div>
    <div class="form" style="margin-top:12px">
      <div class="field grow"><label>指数</label><div class="chips" id="ix-names">${all.map(n => `<span class="chip ${P.names.includes(n) ? 'on' : ''}" data-n="${esc(n)}">${esc(n)}</span>`).join('')}</div></div>
    </div>
    <div class="form" style="margin-top:12px">
      <div class="field"><label>均线天数</label><input type="number" id="ix-ma" min="5" max="250" value="${P.ma}"></div>
      <div class="field"><label>展示最近</label>${segHtml('ix-days', [[30, '30 日'], [60, '60 日'], [120, '120 日'], [250, '250 日']], P.days)}</div>
      <div class="field"><label>&nbsp;</label><button class="btn primary" id="ix-go">获取 / 刷新</button></div>
    </div></div><div id="ix-res"></div>`;
  $$('#ix-names .chip').forEach(c => c.onclick = () => { c.classList.toggle('on'); P.names = $$('#ix-names .chip.on').map(x => x.dataset.n); });
  bindSeg('#ix-days', d => { P.days = +d; if (STATE.idxRes) go(false); });
  const go = refresh => runBtn($('#ix-go'), '获取中…', async () => {
    P.ma = +$('#ix-ma').value || 20;
    if (!P.names.length) throw new Error('请至少选择一个指数');
    STATE.idxRes = await api('index', { names: P.names, ma: P.ma, days: P.days, refresh });
    renderIndex(STATE.idxRes);
  }).catch(() => {});
  $('#ix-go').onclick = () => go(true);
  if (STATE.idxRes) renderIndex(STATE.idxRes);
}

function renderIndex(r) {
  disposeCharts();
  const errs = Object.entries(r.errors || {});
  const L = rowsToObjs(r.latest);
  const el = $('#ix-res');
  if (!L.length) { el.innerHTML = (errs.length ? `<div class="warn-list">${errs.map(([n, e]) => `<div>⚠️ ${esc(n)}：${esc(e)}</div>`).join('')}</div>` : '') + '<div class="card empty">没有获取到任何指数数据</div>'; return; }
  const bk = `偏离率(%)`;
  const hot = L.reduce((a, x) => (x[bk] > a[bk] ? x : a), L[0]);
  const cold = L.reduce((a, x) => (x[bk] < a[bk] ? x : a), L[0]);
  el.innerHTML = (errs.length ? `<div class="warn-list">${errs.map(([n, e]) => `<div>⚠️ ${esc(n)}：${esc(e)}</div>`).join('')}</div>` : '') +
    `<div class="kpis">${kpis([
      { l: '指数数量', v: L.length, h: '最新 ' + L.map(x => x['日期']).sort().pop() },
      { l: `站上 MA${r.ma}`, v: `${L.filter(x => x[bk] > 0).length} / ${L.length}` },
      { l: '偏离最高', v: esc(hot['指数']), t: 'up', h: F.pv(hot[bk]) },
      { l: '偏离最低', v: esc(cold['指数']), t: 'down', h: F.pv(cold[bk]) },
    ])}</div>
    <div class="grid g-7-5" style="grid-template-columns:1fr 1.5fr">
      <div class="card"><h3>最新偏离率 <span class="sub">MA${r.ma}</span></h3><div id="ix-bar"></div></div>
      <div class="card"><h3>偏离率走势</h3><div id="ix-trend" class="chart"></div></div>
    </div>
    <div class="sec-title">收盘价与 MA${r.ma}</div>
    <div class="grid g4" id="ix-minis">${Object.entries(r.series).map(([n, s], i) => {
      const bv = s.bias[s.bias.length - 1];
      return `<div class="card" style="padding:14px 14px 8px;margin:0"><div style="display:flex;justify-content:space-between;align-items:baseline"><b style="font-size:13px">${esc(n)}</b><span class="${tone(bv)}" style="font-weight:600;font-size:13px">${F.pv(bv)}</span></div><div id="ix-m${i}"></div></div>`;
    }).join('')}</div>
    <details class="card" style="margin-top:16px"><summary>分列数据表（与原脚本导出格式一致）</summary><div id="ix-wide" style="margin-top:12px"></div></details>
    <div class="actions"><button class="btn" id="ix-csv">⬇ 下载分列 CSV</button></div>`;
  chartHBar($('#ix-bar'), L.map(x => x['指数']), L.map(x => x[bk]), { pct: true, fmt: vf.pc });
  const trend = {};
  Object.entries(r.series).forEach(([n, s]) => { trend[n] = { dates: s.dates, values: s.bias }; });
  chartLinesTime($('#ix-trend'), trend, { pct: true, height: Math.max(300, L.length * 32 + 30), zero: true });
  Object.entries(r.series).forEach(([n, s], i) => chartMini($(`#ix-m${i}`), s.dates, s.close, s.ma, 'MA' + r.ma));
  if (r.wide) renderTable('#ix-wide', r.wide, { height: 380, fmt: { '日期': 'text' } });
  $('#ix-csv').onclick = () => r.wide && downloadCSV(r.wide, `指数MA${r.ma}分析_分列版_${stamp()}.csv`);
}

function mkFutures(b) {
  const P = STATE.fut = STATE.fut || { contracts: 'IM2612 IM2703 IM2706', base: '' };
  const parse = s => s.toUpperCase().split(/[\s,，]+/).filter(Boolean);
  b.innerHTML = `<div class="card">
    <div class="note">来源：Futures_Spread_Analysis.py · 价差 = 基准合约 - 其他合约（按共同交易日对齐）</div>
    <div class="form" style="margin-top:12px">
      <div class="field grow"><label>合约（空格或逗号分隔）</label><input id="ft-c" value="${esc(P.contracts)}" placeholder="如 IC2612 IM2612 I2701 RB2701"></div>
      <div class="field"><label>基准合约</label><select id="ft-base"></select></div>
      <div class="field"><label>&nbsp;</label><button class="btn primary" id="ft-go">计算价差</button></div>
    </div>
    <div class="note" style="margin-top:10px">💡 备注里常用的：IC260x 中证500、IM260x 中证1000、I260x 铁矿石。合约代码 = 品种 + 年份后两位 + 月份。</div>
  </div><div id="ft-res"></div>`;
  const fill = () => {
    const cs = parse($('#ft-c').value);
    const cur = P.base && cs.includes(P.base) ? P.base : cs[0];
    $('#ft-base').innerHTML = cs.map(c => `<option ${c === cur ? 'selected' : ''}>${esc(c)}</option>`).join('');
  };
  fill();
  $('#ft-c').oninput = fill;
  $('#ft-go').onclick = () => runBtn($('#ft-go'), '获取中…', async () => {
    P.contracts = $('#ft-c').value; P.base = $('#ft-base').value;
    if (parse(P.contracts).length < 2) throw new Error('至少输入两个合约');
    STATE.futRes = await api('futures', { contracts: P.contracts, base: P.base, refresh: true });
    renderFutures(STATE.futRes);
  }).catch(() => {});
  if (STATE.futRes) renderFutures(STATE.futRes);
}

function renderFutures(r) {
  disposeCharts();
  const errs = Object.entries(r.errors || {});
  const b = r.base, N = r.names;
  const items = [{ l: '基准合约', v: esc(N[b] || b), h: '最新 ' + F.num(r.close[b][r.close[b].length - 1], 2) }];
  r.others.slice(0, 4).forEach(c => {
    const s = r.spread[c], p = r.spread_pct[c];
    const mean = s.filter(isNum).reduce((a, x) => a + x, 0) / Math.max(1, s.filter(isNum).length);
    items.push({ l: `${b} − ${c}`, v: (s[s.length - 1] > 0 ? '+' : '') + F.num(s[s.length - 1], 2), t: tone(s[s.length - 1]), h: `${F.pv(p[p.length - 1])} · 均值 ${F.num(mean, 2)}` });
  });
  const closeMap = {}, spreadMap = {};
  r.contracts.forEach(c => { closeMap[N[c] || c] = r.close[c]; });
  r.others.forEach(c => { spreadMap[`${b} − ${c}`] = r.spread[c]; });
  $('#ft-res').innerHTML = (errs.length ? `<div class="warn-list">${errs.map(([n, e]) => `<div>⚠️ ${esc(n)}：${esc(e)}</div>`).join('')}</div>` : '') +
    `<div class="kpis">${kpis(items)}</div>
    <div class="grid g2">
      <div class="card"><h3>合约收盘价</h3><div id="ft-close" class="chart"></div></div>
      <div class="card"><h3>价差走势 <span class="sub">虚线为区间均值</span></h3><div id="ft-spread" class="chart"></div></div>
    </div>
    <div class="card"><h3>价差统计</h3><div id="ft-stats"></div>
      <div class="note" style="margin-top:10px">各合约数据范围：${Object.entries(r.ranges).map(([c, x]) => `${esc(N[c] || c)} ${x[0]} ~ ${x[1]}`).join('；')}</div></div>
    <div class="actions"><button class="btn" id="ft-csv">⬇ 下载价差 CSV</button></div>`;
  chartLinesCat($('#ft-close'), r.dates, closeMap, { highlight: N[b] || b, height: 380 });
  chartLinesCat($('#ft-spread'), r.dates, spreadMap, { meanLines: true, height: 380 });
  renderTable('#ft-stats', r.stats, { fmt: { '价差': 'text', '最新': 'n2', '均值': 'n2', '最大': 'n2', '最小': 'n2', '最新%': 'pv', '均值%': 'pv', '当前分位': 'bar100', 'Z值': 'n2' } });
  $('#ft-csv').onclick = () => downloadCSV(r.table, `期货价差_${r.contracts.join('_')}_${stamp()}.csv`);
}

/* ================================================================ 轮动回测 */
async function pageBacktest(v, q, tk) {
  setHead('轮动回测', '动量轮动：定期买入过去 N 日涨幅最强的品种 · 建议使用后复权数据');
  const P = STATE.bt = STATE.bt || {
    mode: 'rotation', freq: 'week', lookback: 22, npos: 1, init: 100000, fee: 0.6, start: '', end: '',
    dsrc: 'local', code1: '159915.SZ', code2: '510880.SH', dlook: 22, dinit: 1000000, comm: 0.6, slip: 5, dstart: '2015-01-01', dend: today(),
  };
  STATE.btRes = STATE.btRes || {};
  v.innerHTML = `<div style="margin-bottom:16px">${segHtml('bt-mode', [['rotation', '多基金轮动 v4'], ['dual', '双标的动量轮动']], P.mode)}</div>
    <div id="bt-form"></div><div id="bt-res"></div>`;
  bindSeg('#bt-mode', m => { P.mode = m; disposeCharts(); render(); });

  async function render() {
    $('#bt-res').innerHTML = '';
    if (P.mode === 'rotation') await formRotation(); else await formDual();
    if (!alive(tk)) return;
    const last = STATE.btRes[P.mode];
    if (last) btResult($('#bt-res'), last.r, P.mode, last.params);
  }

  async function formRotation() {
    $('#bt-form').innerHTML = `<div class="card">
      <div class="note">来源：fund_rotation_tool_v4.py · 调仓日开盘成交（含 0.05% 滑点）、100 份整手、手续费按成交额计</div>
      <div class="form" style="margin-top:12px"><div class="field grow"><label>参与轮动的品种（至少 2 个）</label><div id="r-pick"></div></div></div>
      <div class="form" style="margin-top:14px">
        <div class="field"><label>调仓频率</label>${segHtml('r-freq', [['week', '每周（周一）'], ['month', '每月（月初）']], P.freq)}</div>
        <div class="field"><label>动量回看（交易日）</label><input type="number" id="r-lb" min="5" max="250" value="${P.lookback}"></div>
        <div class="field"><label>持仓数量（前 N 名等权）</label><input type="number" id="r-np" min="1" max="20" value="${P.npos}"></div>
        <div class="field"><label>初始资金</label><input type="number" id="r-init" min="10000" step="10000" value="${P.init}"></div>
        <div class="field"><label>手续费（万分之）</label><input type="number" id="r-fee" min="0" step="0.1" value="${P.fee}"></div>
        <div class="field"><label>开始（可选）</label><input type="date" id="r-s" value="${P.start}"></div>
        <div class="field"><label>结束（可选）</label><input type="date" id="r-e" value="${P.end}"></div>
        <div class="field"><label>&nbsp;</label><button class="btn primary" id="r-go">🚀 开始回测</button></div>
      </div></div>`;
    const picker = new FilePicker('#r-pick', { key: 'rotation', multi: true });
    await picker.init();
    bindSeg('#r-freq', f => { P.freq = f; });
    $('#r-go').onclick = () => runBtn($('#r-go'), '回测中…', async () => {
      Object.assign(P, { lookback: +$('#r-lb').value || 22, npos: +$('#r-np').value || 1, init: +$('#r-init').value || 100000,
        fee: +$('#r-fee').value || 0, start: $('#r-s').value, end: $('#r-e').value });
      if (picker.value.length < 2) throw new Error('至少选择 2 个品种');
      const params = { files: picker.value, frequency: P.freq, lookback: P.lookback, num_positions: P.npos, initial: P.init,
        fee_bp: P.fee, start: P.start || null, end: P.end || null };
      const r = await api('rotation', params);
      STATE.btRes.rotation = { r, params };
      btResult($('#bt-res'), r, 'rotation', params);
    }).catch(() => {});
  }

  async function formDual() {
    $('#bt-form').innerHTML = `<div class="card">
      <div class="note">来源：donglianglhcv2.py · 每周一开盘前按上周五收盘计算动量择强，周一开盘换仓；单边成本 = 佣金 + 滑点</div>
      <div class="form" style="margin-top:12px"><div class="field"><label>数据来源</label>${segHtml('d-src', [['local', '本地文件'], ['online', '在线获取（TickFlow 后复权）']], P.dsrc)}</div></div>
      <div id="d-src-body" style="margin-top:12px"></div>
      <div class="form" style="margin-top:14px">
        <div class="field"><label>动量回看（交易日）</label><input type="number" id="d-lb" min="5" max="250" value="${P.dlook}"></div>
        <div class="field"><label>初始资金</label><input type="number" id="d-init" min="10000" step="100000" value="${P.dinit}"></div>
        <div class="field"><label>佣金（万分之）</label><input type="number" id="d-comm" min="0" step="0.1" value="${P.comm}"></div>
        <div class="field"><label>滑点（万分之）</label><input type="number" id="d-slip" min="0" step="0.5" value="${P.slip}"></div>
        <div class="field"><label>&nbsp;</label><button class="btn primary" id="d-go">🚀 开始回测</button></div>
      </div></div>`;
    let picker = null;
    const srcBody = async () => {
      if (P.dsrc === 'local') {
        $('#d-src-body').innerHTML = '<div class="form"><div class="field grow"><label>选择两个品种</label><div id="d-pick"></div></div></div>';
        picker = new FilePicker('#d-pick', { key: 'dual', multi: true });
        await picker.init();
      } else {
        picker = null;
        $('#d-src-body').innerHTML = `<div class="form">
          <div class="field"><label>标的 1</label><input id="d-c1" value="${esc(P.code1)}" style="width:140px"></div>
          <div class="field"><label>标的 2</label><input id="d-c2" value="${esc(P.code2)}" style="width:140px"></div>
          <div class="field"><label>开始日期</label><input type="date" id="d-s" value="${P.dstart}"></div>
          <div class="field"><label>结束日期</label><input type="date" id="d-e" value="${P.dend}"></div>
          <div class="note" style="align-self:center">需要 TickFlow 密钥；免费版数据条数有限</div></div>`;
      }
    };
    await srcBody();
    bindSeg('#d-src', s => { P.dsrc = s; srcBody(); });
    $('#d-go').onclick = () => runBtn($('#d-go'), '回测中…', async () => {
      Object.assign(P, { dlook: +$('#d-lb').value || 22, dinit: +$('#d-init').value || 1000000, comm: +$('#d-comm').value || 0, slip: +$('#d-slip').value || 0 });
      const params = { source: P.dsrc, lookback: P.dlook, initial: P.dinit, comm_bp: P.comm, slip_bp: P.slip };
      if (P.dsrc === 'local') {
        if (!picker || picker.value.length !== 2) throw new Error('请恰好选择两个品种');
        params.files = picker.value;
      } else {
        Object.assign(P, { code1: $('#d-c1').value.trim(), code2: $('#d-c2').value.trim(), dstart: $('#d-s').value, dend: $('#d-e').value });
        Object.assign(params, { code1: P.code1, code2: P.code2, start: P.dstart || null, end: P.dend || null });
      }
      const r = await api('dual', params);
      STATE.btRes.dual = { r, params };
      btResult($('#bt-res'), r, 'dual', params);
    }).catch(() => {});
  }

  render();
}

function btResult(el, r, kind, params) {
  disposeCharts();
  const m = r.metrics, init = r.init;
  const yearlyFmt = {};
  if (r.yearly) r.yearly.columns.forEach(c => { yearlyFmt[c] = c === '年份' ? 'int' : 'pct'; });
  el.innerHTML = `<div class="sec-title">回测结果 <span class="sub">${r.start} ~ ${r.end}</span></div>
    <div class="kpis">${kpis([
      { l: '期末资产', v: F.money(m['期末资产']), t: tone(m['累计收益']), h: '初始 ' + F.money(init) },
      { l: '累计收益', v: F.pct(m['累计收益']), t: tone(m['累计收益']) },
      { l: '年化收益', v: F.pct(m['年化收益']), t: tone(m['年化收益']), h: '年化波动 ' + F.pct(m['年化波动'], 2, false) },
      { l: '最大回撤', v: F.pct(m['最大回撤']), t: 'down', h: '卡玛比率 ' + m['卡玛比率'] },
      { l: '夏普 / 索提诺', v: `${m['夏普比率']} / ${m['索提诺比率']}`, h: '月度胜率 ' + F.pct(m['月度胜率'], 1, false) },
      { l: '调仓次数', v: m['调仓次数'], h: `年均 ${m['年化换手次数']} 次` + (isNum(m['累计手续费']) ? ` · 手续费 ${F.money(m['累计手续费'])}` : '') },
    ])}</div>
    <div class="card"><h3>净值曲线 <span class="sub">起点 = 1，虚线为单独持有各标的</span></h3><div id="c-eq" class="chart"></div></div>
    <div class="grid g-7-5">
      <div>
        <div class="card"><h3>策略 vs 单独持有</h3><div id="t-cmp"></div></div>
        <div class="card"><h3>月度收益热力图 <span class="sub">单位 %，最后一列为全年</span></h3><div id="c-hm"></div></div>
      </div>
      <div>
        <div class="card"><h3>持仓时间分布 <span class="sub">交易日</span></h3><div id="c-hold"></div></div>
        ${r.yearly ? '<div class="card"><h3>年度表现</h3><div id="t-yr"></div></div>' : ''}
      </div>
    </div>
    <details class="card"><summary>📒 调仓记录（${r.trades.rows.length} 条）</summary><div id="t-tr" style="margin-top:12px"></div></details>
    <div class="actions"><button class="btn" id="x-bt">⬇ 导出 Excel</button><button class="btn" id="s-bt">💾 保存报告到输出文件夹</button></div>`;
  chartEquity($('#c-eq'), r.nav, r.bench);
  renderTable('#t-cmp', r.comparison, { fmt: { '累计收益': 'pct', '年化收益': 'pct', '最大回撤': 'pct', '夏普比率': 'n2' } });
  chartHeatmap($('#c-hm'), r.monthly);
  chartDonut($('#c-hold'), r.holding.labels, r.holding.values, ' 天');
  if (r.yearly) renderTable('#t-yr', r.yearly, { fmt: yearlyFmt });
  renderTable('#t-tr', r.trades, { height: 440, fmt: { '日期': 'text', '成本': x => ({ html: F.pct(x, 3, false), cls: 'num' }), '卖出': 'wrap', '买入': 'wrap' } });
  const tag = kind === 'rotation' ? '多基金' : '双标的';
  $('#x-bt').onclick = () => exportXlsx(kind, params, 'xlsx', `轮动回测_${tag}_${stamp()}.xlsx`);
  $('#s-bt').onclick = () => runBtn($('#s-bt'), '保存中…', async () => {
    const x = await api('save_report', { kind, params });
    toast('已保存到 ' + x.path, 'ok');
  }).catch(() => {});
}

/* ================================================================ SPMO */
const SPMO_DESC = {
  weighted: '近 1 年 40% + 近 6 月 35% + 近 3 月 25%（SPMO多周期403525加权.py / SPMO+RSI.py）',
  equal: '近 1 年、近 6 月、近 3 月三个评分简单平均（SPMO多周期.py）',
  standard: '过去 12 个月剔除最近 1 个月的动量，不足一年用成立以来（SPMO.py / SPMO近一年.py）',
};

async function pageSpmo(v, q, tk) {
  setHead('SPMO 选基', '评分 = 年化动量 ÷ 年化波动率（剔除最近一段，避免短期反转），按正分比例分配权重');
  const P = STATE.spmo = STATE.spmo || { method: 'weighted', top: 10, rsi: true };
  v.innerHTML = `<div class="card">
    <div class="form"><div class="field grow"><label>基金池（点击选择）</label><div id="sp-pick"></div></div></div>
    <div class="form" style="margin-top:14px">
      <div class="field"><label>评分方法</label>${segHtml('sp-m', [['weighted', '三周期加权 40/35/25'], ['equal', '三周期等权'], ['standard', '标准 12-1 月']], P.method)}</div>
      <div class="field"><label>组合入选数量</label><input type="number" id="sp-top" min="1" max="30" value="${P.top}" style="width:100px"></div>
      <div class="field"><label>&nbsp;</label><label class="check"><input type="checkbox" id="sp-rsi" ${P.rsi ? 'checked' : ''}> 显示 RSI 状态</label></div>
    </div>
    <div class="note" id="sp-desc" style="margin-top:10px"></div></div><div id="sp-res"></div>`;
  const desc = () => { $('#sp-desc').textContent = 'ℹ️ ' + SPMO_DESC[P.method] + '。波动率统一用最近 250 个交易日（不足则用全部）。'; };
  desc();
  let seq = 0;
  const picker = new FilePicker('#sp-pick', { key: 'spmo', multi: true, defaultAll: true, onChange: () => run() });
  await picker.init();
  if (!alive(tk)) return;
  bindSeg('#sp-m', x => { P.method = x; desc(); run(); });
  $('#sp-top').onchange = e => { P.top = Math.max(1, +e.target.value || 10); run(); };
  $('#sp-rsi').onchange = e => { P.rsi = e.target.checked; run(); };

  async function run() {
    const res = $('#sp-res');
    const files = picker.value;
    if (!files.length) { disposeCharts(); res.innerHTML = '<div class="card empty">请至少选择一个品种</div>'; return; }
    const my = ++seq;
    res.classList.add('busy');
    const params = { files, method: P.method, top_n: P.top, with_rsi: P.rsi };
    try {
      const r = await api('spmo', params);
      if (my !== seq || !alive(tk)) return;
      renderSpmo(res, r, params);
    } catch (e) { if (my === seq) { disposeCharts(); res.innerHTML = errHtml(e); } } finally { if (my === seq) res.classList.remove('busy'); }
  }
  run();
}

function renderSpmo(el, r, params) {
  disposeCharts();
  const T = rowsToObjs(r.table);
  const lead = T[0];
  const pos = T.filter(x => x['综合评分'] > 0).length;
  const maxW = Math.max(...r.top.weights.filter(isNum));
  el.innerHTML = `<div class="kpis">${kpis([
      { l: '参与评分', v: T.length + ' 只', h: '数据最新 ' + r.latest_date },
      { l: '第一名', v: esc(short(lead['名称'])), t: 'up', h: '评分 ' + lead['综合评分'].toFixed(3) },
      { l: '正动量', v: `${pos} / ${T.length}`, t: pos > T.length / 2 ? 'up' : 'down', h: '评分 > 0 的数量' },
      { l: '组合集中度', v: F.pv(maxW, 1, false), h: '最大单只权重' },
    ])}</div>
    <div class="grid g-7-5">
      <div class="card"><h3>综合评分排名</h3><div id="sp-bar"></div></div>
      <div class="card"><h3>建议组合 <span class="sub">前 ${r.top.names.length} 名，按正分比例分配</span></h3><div id="sp-donut"></div></div>
    </div>
    ${r.scores.s1 ? '<div class="card"><h3>三周期评分对比</h3><div id="sp-group" class="chart"></div></div>' : ''}
    <div class="card"><h3>完整排名表</h3><div id="sp-tbl"></div>
      ${r.hot.length ? `<div style="margin-top:12px;font-size:13px">⚠️ 动量靠前但已超买，追高需谨慎：${r.hot.map(h => pill(short(h), 'up')).join(' ')}</div>` : ''}
      <div class="note" style="margin-top:10px">与原脚本的差别：负分品种的建议权重记为 0（原脚本可能算出负权重）；TickFlow 的 close 列也能识别。</div></div>
    <div class="actions"><button class="btn" id="sp-xlsx">⬇ 导出 Excel</button><button class="btn" id="sp-csv">⬇ 下载 CSV</button></div>`;
  chartHBar($('#sp-bar'), r.scores.names.map(short), r.scores.total, { fmt: vf.p3 });
  const w = r.top.names.map((n, i) => [short(n), r.top.weights[i]]).filter(x => x[1] > 0);
  chartDonut($('#sp-donut'), w.map(x => x[0]), w.map(x => x[1]), '%');
  if (r.scores.s1) chartGrouped($('#sp-group'), r.scores.names, { '近1年': r.scores.s1, '近6月': r.scores.s6, '近3月': r.scores.s3 }, { name: '综合', values: r.scores.total });
  const fmt = { '排名': 'int', '最新日期': 'text', '最新价': 'n4', '综合评分': 'n3', 'SPMO(近1年)': 'n3', 'SPMO(近6月)': 'n3', 'SPMO(近3月)': 'n3',
    '年化波动(%)': 'pvu', '数据天数': 'int', '口径': 'text', 'RSI(14)': 'rsi', 'RSI状态': 'status', '建议权重(%)': 'bar100' };
  renderTable('#sp-tbl', r.table, { fmt });
  $('#sp-xlsx').onclick = () => exportXlsx('spmo', params, 'xlsx', `SPMO_${r.method}_${stamp()}.xlsx`);
  $('#sp-csv').onclick = () => downloadCSV(r.table, `SPMO_${r.method}_${stamp()}.csv`);
}

/* ================================================================ 设置 */
async function pageSettings(v) {
  setHead('设置', '数据文件夹、报告输出文件夹与 API 密钥');
  const s = await refreshStatus() || {};
  v.innerHTML = `<div class="card"><h3>📁 文件夹</h3>
      <div class="form">
        <div class="field grow"><label>数据文件夹（分析页从这里读取 CSV / Excel，下载也保存到这里）</label><input id="st-data" value="${esc(s.data_dir || '')}"></div>
      </div>
      <div class="form" style="margin-top:12px">
        <div class="field grow"><label>报告输出文件夹（回测「保存报告」写到这里）</label><input id="st-out" value="${esc(s.output_dir || '')}"></div>
      </div>
      <div class="actions" style="margin:14px 0 0"><button class="btn primary" id="st-save">保存设置</button></div>
      <div class="note" style="margin-top:10px">设置保存在面板文件夹的 settings.json（已加入 .gitignore，不会上传）。</div></div>
    <div class="card"><h3>🔑 TickFlow 密钥 ${s.tickflow_key ? pill('已读取', 'ok') : pill('未设置', 'mid')}</h3>
      <p class="note" style="font-size:13px;line-height:1.8;margin:0">面板<b>只从环境变量</b> <code>TICKFLOW_API_KEY</code> 读取密钥，代码和配置文件里都不保存。${s.tickflow_key ? '' : '没设置时会使用免费版，能下载的数据条数有限。'}<br>
      设置方法：在命令行运行一次 <code>setx TICKFLOW_API_KEY "你的密钥"</code>，然后<b>关闭并重新打开</b>「启动面板.bat」。</p></div>
    <div class="card"><h3>ℹ️ 关于</h3><p class="note" style="font-size:13px;line-height:1.8;margin:0">
      A股投资工具箱 v${esc(s.version || '')} · FastAPI + ECharts · 默认端口 8520（被占用时自动顺延，可用环境变量 <code>INVEST_PORT</code> 指定）<br>
      数据仅供研究参考，不构成投资建议。</p></div>`;
  $('#st-save').onclick = () => runBtn($('#st-save'), '保存中…', async () => {
    await api('settings', { data_dir: $('#st-data').value, output_dir: $('#st-out').value });
    STATE.picks = {};
    await refreshStatus();
    toast('设置已保存', 'ok');
  }).catch(() => {});
}

/* ================================================================ 路由 */
const ROUTES = { overview: pageOverview, data: pageData, single: pageSingle, market: pageMarket, backtest: pageBacktest, spmo: pageSpmo, settings: pageSettings };

async function route() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [path, qs] = raw.split('?');
  const name = ROUTES[path] ? path : 'overview';
  $$('.nav a').forEach(a => a.classList.toggle('active', a.dataset.r === name));
  disposeCharts();
  const v = $('#view');
  v.innerHTML = '';
  const tk = ++ROUTE_TOKEN;
  window.scrollTo(0, 0);
  try { await ROUTES[name](v, new URLSearchParams(qs || ''), tk); } catch (e) { console.error(e); if (alive(tk)) v.innerHTML = errHtml(e); }
}

window.addEventListener('hashchange', route);
window.addEventListener('DOMContentLoaded', async () => {
  if (typeof echarts === 'undefined') {
    $('#view').innerHTML = errHtml('图表库 vendor/echarts.min.js 没有加载成功，请确认 static/vendor 文件夹完整');
    return;
  }
  await refreshStatus();
  route();
});
