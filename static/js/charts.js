/* ECharts 图表工厂：统一浅色简洁风（A股习惯：涨红跌绿） */
'use strict';

const C = {
  primary: '#2563EB', up: '#E5484D', down: '#12A150', amber: '#F59E0B', purple: '#8B5CF6',
  muted: '#64748B', text: '#334155', grid: '#EEF1F6', axis: '#E2E8F0',
  palette: ['#2563EB', '#F59E0B', '#10B981', '#8B5CF6', '#EF4444', '#06B6D4', '#EC4899', '#84CC16', '#F97316', '#0EA5E9'],
};
const FONT = '"Inter","PingFang SC","Microsoft YaHei","Segoe UI",sans-serif';
const CHARTS = new Set();

function merge(a, b) {
  if (!b) return a;
  Object.keys(b).forEach(k => {
    const v = b[k];
    if (v && typeof v === 'object' && !Array.isArray(v) && a[k] && typeof a[k] === 'object' && !Array.isArray(a[k])) {
      a[k] = merge(Object.assign({}, a[k]), v);
    } else a[k] = v;
  });
  return a;
}

function mkChart(el, option, height) {
  if (typeof el === 'string') el = $(el);
  if (!el) return null;
  if (height) el.style.height = height + 'px';
  const old = echarts.getInstanceByDom(el);
  if (old) { CHARTS.delete(old); old.dispose(); }
  const c = echarts.init(el, null, { renderer: 'canvas' });
  c.setOption(option);
  CHARTS.add(c);
  return c;
}
function disposeCharts() { CHARTS.forEach(c => { try { c.dispose(); } catch (e) { /* ignore */ } }); CHARTS.clear(); }
let _rz;
window.addEventListener('resize', () => { clearTimeout(_rz); _rz = setTimeout(() => CHARTS.forEach(c => c.resize()), 120); });

/* ---------------- 公共配置 ---------------- */
const vf = {
  p4: v => isNum(v) ? v.toFixed(4) : '—',
  p3: v => isNum(v) ? v.toFixed(3) : '—',
  p2: v => isNum(v) ? v.toFixed(2) : '—',
  pc: v => isNum(v) ? (v > 0 ? '+' : '') + v.toFixed(2) + '%' : '—',
  pu: v => isNum(v) ? v.toFixed(1) + '%' : '—',
};

function baseOpt(extra) {
  return merge({
    color: C.palette,
    textStyle: { fontFamily: FONT, color: C.text },
    animationDuration: 350,
    tooltip: {
      trigger: 'axis', confine: true, backgroundColor: 'rgba(255,255,255,.97)', borderColor: '#E5E7EB', borderWidth: 1,
      padding: [8, 12], textStyle: { color: '#0F172A', fontSize: 12 },
      extraCssText: 'box-shadow:0 6px 20px rgba(15,23,42,.10);border-radius:10px;',
      axisPointer: { type: 'line', lineStyle: { color: '#CBD5E1' } },
    },
    legend: { top: 0, left: 0, right: 40, type: 'scroll', icon: 'roundRect', itemWidth: 12, itemHeight: 4, itemGap: 14,
      textStyle: { color: '#475569', fontSize: 12 } },
    grid: { left: 12, right: 18, top: 40, bottom: 12, containLabel: true },
    toolbox: { right: 0, top: -2, itemSize: 13, feature: { saveAsImage: { title: '保存图片', pixelRatio: 2, backgroundColor: '#fff' } },
      iconStyle: { borderColor: '#94A3B8' } },
  }, extra);
}
const AXIS = { axisLine: { lineStyle: { color: C.axis } }, axisTick: { show: false },
  axisLabel: { color: C.muted, hideOverlap: true, fontSize: 11 } };
const xCat = (data, extra) => merge(merge({ type: 'category', data, boundaryGap: false, splitLine: { show: false } }, AXIS), extra);
const xTime = extra => merge(merge({ type: 'time', splitLine: { show: false } }, AXIS), extra);
const yVal = extra => merge({ type: 'value', scale: true, axisLine: { show: false }, axisTick: { show: false },
  axisLabel: { color: C.muted, fontSize: 11 }, splitLine: { lineStyle: { color: C.grid } } }, extra);
const sLine = (name, data, color, extra) => merge({
  type: 'line', name, data, showSymbol: false, symbol: 'circle', symbolSize: 5, sampling: 'lttb',
  lineStyle: { width: 1.6, color }, itemStyle: { color }, emphasis: { disabled: true },
}, extra);
function dz(xIdx, startValue) {
  const inside = { type: 'inside', xAxisIndex: xIdx };
  const slider = {
    type: 'slider', xAxisIndex: xIdx, bottom: 4, height: 18, borderColor: 'transparent', backgroundColor: '#F1F5F9',
    fillerColor: 'rgba(37,99,235,.10)', dataBackground: { lineStyle: { color: '#CBD5E1' }, areaStyle: { color: '#E2E8F0' } },
    selectedDataBackground: { lineStyle: { color: '#93C5FD' }, areaStyle: { color: '#DBEAFE' } },
    handleStyle: { color: '#fff', borderColor: '#94A3B8' }, moveHandleSize: 4, textStyle: { color: C.muted, fontSize: 10 },
    brushSelect: false,
  };
  if (startValue != null) { inside.startValue = startValue; slider.startValue = startValue; }
  return [inside, slider];
}
const pairs = (xs, ys) => xs.map((x, i) => [x, ys[i]]);

/* ---------------- 价格 + 回撤 ---------------- */
function chartPriceDD(el, dates, price, dd, name, extraLines) {
  const series = [sLine(name, price, C.primary, { tooltip: { valueFormatter: vf.p4 } })];
  Object.entries(extraLines || {}).forEach(([k, v], i) =>
    series.push(sLine(k, v, C.palette[(i + 1) % C.palette.length], { lineStyle: { width: 1.2 }, tooltip: { valueFormatter: vf.p4 } })));
  series.push(sLine('回撤', dd, C.down, {
    xAxisIndex: 1, yAxisIndex: 1, lineStyle: { width: 1 }, areaStyle: { color: 'rgba(18,161,80,.14)' },
    tooltip: { valueFormatter: vf.pc },
  }));
  return mkChart(el, baseOpt({
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [{ left: 62, right: 20, top: 40, height: '55%' }, { left: 62, right: 20, top: '70%', bottom: 42 }],
    xAxis: [xCat(dates, { gridIndex: 0, axisLabel: { show: false } }), xCat(dates, { gridIndex: 1 })],
    yAxis: [yVal({ gridIndex: 0 }), yVal({ gridIndex: 1, scale: false, max: 0, splitNumber: 3, axisLabel: { formatter: '{value}%' } })],
    dataZoom: dz([0, 1]),
    series,
  }), 460);
}

/* ---------------- 滚动年化 ---------------- */
function chartRolling(el, dates, roll, years) {
  let i0 = roll.findIndex(v => v != null);
  if (i0 < 0) i0 = 0;
  const ds = dates.slice(i0), rs = roll.slice(i0);
  const lbl = { color: '#0F172A', backgroundColor: '#fff', borderColor: '#E2E8F0', borderWidth: 1, padding: [3, 7], borderRadius: 6, fontSize: 11 };
  return mkChart(el, baseOpt({
    legend: { show: false },
    grid: { bottom: 34 },
    xAxis: xCat(ds),
    yAxis: yVal({ axisLabel: { formatter: '{value}%' } }),
    visualMap: { show: false, seriesIndex: 0, dimension: 1, pieces: [{ lt: 0, color: C.down }, { gte: 0, color: C.up }] },
    dataZoom: dz(0),
    series: [sLine(years + ' 年滚动年化', rs, C.up, {
      areaStyle: { opacity: 0.12 }, tooltip: { valueFormatter: vf.pc },
      markLine: { silent: true, symbol: 'none', data: [
        { type: 'average', name: '均值', lineStyle: { color: C.muted, type: 'dashed' }, label: { formatter: p => '均值 ' + p.value.toFixed(2) + '%', position: 'insideStartTop', color: C.muted } },
        { yAxis: 0, lineStyle: { color: '#CBD5E1', type: 'solid' }, label: { show: false } }] },
      markPoint: { symbol: 'circle', symbolSize: 7, data: [
        { type: 'max', name: '最高', itemStyle: { color: C.up }, label: Object.assign({ formatter: p => '最高 ' + p.value.toFixed(2) + '%', position: 'top' }, lbl) },
        { type: 'min', name: '最低', itemStyle: { color: C.down }, label: Object.assign({ formatter: p => '最低 ' + p.value.toFixed(2) + '%', position: 'bottom' }, lbl) }] },
    })],
  }), 360);
}

/* ---------------- 回撤波段 ---------------- */
function chartDDPeriods(el, dates, price, periodsTbl) {
  const P = rowsToObjs(periodsTbl);
  const last = dates[dates.length - 1];
  const areas = P.map(p => [
    { xAxis: p['开始'], itemStyle: { color: 'rgba(229,72,77,.08)' },
      label: { show: true, position: 'insideTop', formatter: (p['回撤深度(%)'] || 0).toFixed(1) + '%', color: C.up, fontSize: 11 } },
    { xAxis: p['修复完成'] || last }]);
  return mkChart(el, baseOpt({
    legend: { show: false },
    grid: { bottom: 12 },
    xAxis: xCat(dates), yAxis: yVal(),
    series: [sLine('价格', price, C.primary, {
      tooltip: { valueFormatter: vf.p4 },
      markArea: { silent: true, data: areas },
      markLine: { silent: true, symbol: 'none', label: { show: false },
        lineStyle: { color: 'rgba(229,72,77,.5)', type: 'dotted' }, data: P.map(p => ({ xAxis: p['谷底'] })) },
    })],
  }), 340);
}

/* ---------------- 年度柱状 ---------------- */
function chartYearly(el, ytbl) {
  const Y = rowsToObjs(ytbl);
  return mkChart(el, baseOpt({
    grid: { top: 44 },
    tooltip: { axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: Y.map(r => String(r['年份'])), axisLine: { lineStyle: { color: C.axis } }, axisTick: { show: false },
      axisLabel: { color: C.muted, fontSize: 11 } },
    yAxis: yVal({ scale: false, axisLabel: { formatter: '{value}%' } }),
    series: [
      { type: 'bar', name: '年度涨幅', barMaxWidth: 26, tooltip: { valueFormatter: vf.pc },
        data: Y.map(r => {
          const v = r['年度涨幅(%)'];
          return { value: v, itemStyle: { color: v >= 0 ? C.up : C.down, borderRadius: v >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4] },
            label: { show: true, position: v >= 0 ? 'top' : 'bottom', formatter: p => (p.value > 0 ? '+' : '') + p.value.toFixed(1) + '%', fontSize: 10, color: '#475569' } };
        }) },
      { type: 'line', name: '年内最大回撤', data: Y.map(r => r['年度最大回撤(%)']), symbol: 'circle', symbolSize: 7,
        lineStyle: { color: C.muted, type: 'dashed', width: 1 }, itemStyle: { color: '#fff', borderColor: C.muted, borderWidth: 2 },
        tooltip: { valueFormatter: vf.pc } },
    ],
  }), 340);
}

/* ---------------- 均线 ---------------- */
function chartMA(el, dates, price, lines, name) {
  const colors = ['#2563EB', '#F59E0B', '#8B5CF6', '#10B981', '#EC4899', '#06B6D4', '#EF4444'];
  const series = [sLine(name, price, '#0F172A', { tooltip: { valueFormatter: vf.p4 } })];
  Object.entries(lines).forEach(([k, v], i) => series.push(sLine(k, v, colors[i % colors.length], { lineStyle: { width: 1.3 }, tooltip: { valueFormatter: vf.p4 } })));
  return mkChart(el, baseOpt({
    grid: { bottom: 34 }, xAxis: xCat(dates), yAxis: yVal(),
    dataZoom: dz(0, dates[Math.max(0, dates.length - 500)]), series,
  }), 460);
}

/* ---------------- RSI ---------------- */
function chartRSI(el, dates, price, rsi, pct) {
  const start = dates[Math.max(0, dates.length - 500)];
  return mkChart(el, baseOpt({
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [{ left: 58, right: 20, top: 40, height: '38%' }, { left: 58, right: 20, top: '54%', height: '17%' }, { left: 58, right: 20, top: '76%', bottom: 42 }],
    xAxis: [0, 1, 2].map(i => xCat(dates, { gridIndex: i, axisLabel: { show: i === 2 } })),
    yAxis: [yVal({ gridIndex: 0 }),
      yVal({ gridIndex: 1, scale: false, min: 0, max: 100, interval: 50 }),
      yVal({ gridIndex: 2, scale: false, min: 0, max: 100, interval: 50, axisLabel: { formatter: '{value}%' } })],
    dataZoom: dz([0, 1, 2], start),
    series: [
      sLine('价格', price, C.primary, { tooltip: { valueFormatter: vf.p4 } }),
      sLine('RSI(14)', rsi, C.purple, {
        xAxisIndex: 1, yAxisIndex: 1, lineStyle: { width: 1.2 }, tooltip: { valueFormatter: vf.p2 },
        markArea: { silent: true, data: [[{ yAxis: 70, itemStyle: { color: 'rgba(229,72,77,.07)' } }, { yAxis: 100 }],
          [{ yAxis: 0, itemStyle: { color: 'rgba(18,161,80,.07)' } }, { yAxis: 30 }]] },
        markLine: { silent: true, symbol: 'none', label: { show: true, position: 'insideEndTop', fontSize: 10 }, data: [
          { yAxis: 70, lineStyle: { color: C.up, type: 'dashed' }, label: { formatter: '超买 70', color: C.up } },
          { yAxis: 30, lineStyle: { color: C.down, type: 'dashed' }, label: { formatter: '超卖 30', color: C.down } }] },
      }),
      sLine('价格百分位', pct, C.amber, { xAxisIndex: 2, yAxisIndex: 2, lineStyle: { width: 1 }, areaStyle: { color: 'rgba(245,158,11,.12)' }, tooltip: { valueFormatter: vf.pu } }),
    ],
  }), 600);
}

/* ---------------- 仪表盘 ---------------- */
function chartGauge(el, value, title, lo = 30, hi = 70) {
  const v = isNum(value) ? value : 0;
  return mkChart(el, {
    series: [{
      type: 'gauge', startAngle: 205, endAngle: -25, min: 0, max: 100, radius: '95%', center: ['50%', '60%'], splitNumber: 5,
      axisLine: { lineStyle: { width: 14, color: [[lo / 100, '#BBF7D0'], [hi / 100, '#E2E8F0'], [1, '#FECACA']] } },
      pointer: { length: '56%', width: 5, itemStyle: { color: '#334155' } },
      anchor: { show: true, size: 10, itemStyle: { color: '#334155' } },
      axisTick: { show: false }, splitLine: { length: 8, distance: -14, lineStyle: { color: '#fff', width: 2 } },
      axisLabel: { distance: 20, color: C.muted, fontSize: 10, fontFamily: FONT },
      title: { offsetCenter: [0, '38%'], color: C.muted, fontSize: 12, fontFamily: FONT },
      detail: { offsetCenter: [0, '12%'], fontSize: 26, fontWeight: 700, fontFamily: FONT,
        color: v > hi ? C.up : v < lo ? C.down : '#0F172A', formatter: x => isNum(value) ? x.toFixed(1) : '—' },
      data: [{ value: v, name: title }],
    }],
  }, 200);
}

/* ---------------- 多条线（时间轴） ---------------- */
function chartLinesTime(el, seriesMap, opt = {}) {
  const series = Object.entries(seriesMap).map(([k, s], i) =>
    sLine(k, pairs(s.dates, s.values), C.palette[i % C.palette.length], {
      lineStyle: { width: k === opt.highlight ? 2.6 : 1.5 },
      tooltip: { valueFormatter: opt.pct ? vf.pc : vf.p4 },
    }));
  if (opt.zero && series.length) series[0].markLine = { silent: true, symbol: 'none', label: { show: false }, data: [{ yAxis: 0 }], lineStyle: { color: '#CBD5E1', type: 'solid' } };
  return mkChart(el, baseOpt({
    grid: { bottom: 12 },
    xAxis: xTime(), yAxis: yVal(opt.pct ? { axisLabel: { formatter: '{value}%' } } : {}),
    series,
  }), opt.height || 380);
}

/* ---------------- 多条线（类目轴，日期对齐） ---------------- */
function chartLinesCat(el, dates, seriesMap, opt = {}) {
  const series = Object.entries(seriesMap).map(([k, v], i) =>
    sLine(k, v, C.palette[i % C.palette.length], {
      lineStyle: { width: k === opt.highlight ? 2.6 : 1.6 },
      tooltip: { valueFormatter: opt.fmt || vf.p2 },
      markLine: opt.meanLines ? { silent: true, symbol: 'none', label: { show: false }, data: [{ type: 'average' }],
        lineStyle: { color: C.palette[i % C.palette.length], type: 'dashed', width: 1, opacity: 0.7 } } : undefined,
    }));
  return mkChart(el, baseOpt({ grid: { bottom: 34 }, xAxis: xCat(dates), yAxis: yVal(), dataZoom: dz(0), series }), opt.height || 380);
}

/* ---------------- 迷你图（指数小卡） ---------------- */
function chartMini(el, dates, close, ma, maName) {
  return mkChart(el, {
    textStyle: { fontFamily: FONT },
    grid: { left: 6, right: 6, top: 8, bottom: 6, containLabel: true },
    tooltip: { trigger: 'axis', confine: true, textStyle: { fontSize: 11 }, valueFormatter: vf.p2 },
    xAxis: xCat(dates, { axisLabel: { show: false }, axisLine: { show: false } }),
    yAxis: yVal({ axisLabel: { fontSize: 10 }, splitNumber: 3 }),
    series: [sLine('收盘', close, '#0F172A', { lineStyle: { width: 1.4 } }),
      sLine(maName, ma, C.primary, { lineStyle: { width: 1.2, type: 'dashed' } })],
  }, 170);
}

/* ---------------- 净值曲线（回测） ---------------- */
function chartEquity(el, nav, bench) {
  const series = Object.entries(bench).map(([k, s], i) => sLine(k, pairs(s.dates, s.values), C.palette[(i + 1) % C.palette.length],
    { lineStyle: { width: 1.2, type: 'dashed' } }));
  series.push(sLine('轮动策略', pairs(nav.dates, nav.value), C.primary, { lineStyle: { width: 2.6 }, z: 5 }));
  series.push(sLine('策略回撤', pairs(nav.dates, nav.drawdown), C.down, {
    xAxisIndex: 1, yAxisIndex: 1, lineStyle: { width: 1 }, areaStyle: { color: 'rgba(18,161,80,.14)' } }));
  const stratIdx = series.length - 2, ddIdx = series.length - 1;
  return mkChart(el, baseOpt({
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      formatter: ps => {
        if (!ps.length) return '';
        const d = ps[0].axisValueLabel || (ps[0].value && ps[0].value[0]);
        let s = `<div style="font-weight:600;margin-bottom:4px">${esc(String(d).slice(0, 10))}</div>`;
        ps.forEach(p => {
          const v = p.value[1];
          const txt = p.seriesIndex === ddIdx ? vf.pc(v) : vf.p3(v);
          s += `<div>${p.marker}${esc(p.seriesName)}：<b>${txt}</b></div>`;
          if (p.seriesIndex === stratIdx && nav.holdings[p.dataIndex]) s += `<div style="color:#64748B;margin:0 0 2px 14px">持有：${esc(nav.holdings[p.dataIndex])}</div>`;
        });
        return s;
      },
    },
    grid: [{ left: 58, right: 20, top: 40, height: '56%' }, { left: 58, right: 20, top: '71%', bottom: 42 }],
    xAxis: [xTime({ gridIndex: 0, axisLabel: { show: false } }), xTime({ gridIndex: 1 })],
    yAxis: [yVal({ gridIndex: 0, name: '净值', nameTextStyle: { color: C.muted, fontSize: 11 } }),
      yVal({ gridIndex: 1, scale: false, max: 0, splitNumber: 3, axisLabel: { formatter: '{value}%' } })],
    dataZoom: dz([0, 1]),
    series,
  }), 520);
}

/* ---------------- 环形图 ---------------- */
function chartDonut(el, labels, values, unit = '') {
  return mkChart(el, {
    color: C.palette, textStyle: { fontFamily: FONT },
    tooltip: { trigger: 'item', formatter: p => `${p.marker}${esc(p.name)}<br><b>${p.value}${unit}</b>（${p.percent}%）` },
    legend: { type: 'scroll', orient: 'vertical', right: 0, top: 'middle', icon: 'circle', itemWidth: 8, itemHeight: 8,
      textStyle: { color: '#475569', fontSize: 12, width: 150, overflow: 'truncate' } },
    series: [{ type: 'pie', radius: ['55%', '78%'], center: ['34%', '50%'], avoidLabelOverlap: true,
      itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 4 },
      label: { show: true, position: 'inside', formatter: p => p.percent >= 6 ? p.percent.toFixed(0) + '%' : '', color: '#fff', fontSize: 11, fontWeight: 600 },
      data: labels.map((l, i) => ({ name: l, value: values[i] })) }],
  }, 300);
}

/* ---------------- 月度热力图 ---------------- */
function chartHeatmap(el, monthly) {
  const months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月', '全年'];
  const cells = monthly.data.filter(d => d[0] < 12 && isNum(d[2])).map(d => Math.abs(d[2]));
  const m = Math.max(3, Math.min(15, cells.length ? Math.max(...cells) : 5));
  return mkChart(el, {
    textStyle: { fontFamily: FONT },
    tooltip: { confine: true, formatter: p => `${monthly.years[p.value[1]]} 年 ${months[p.value[0]]}：<b>${vf.pc(p.value[2])}</b>` },
    grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: months, position: 'top', axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: C.muted, fontSize: 11 }, splitArea: { show: false } },
    yAxis: { type: 'category', data: monthly.years, inverse: true, axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: C.muted, fontSize: 11 } },
    visualMap: { show: false, min: -m, max: m, dimension: 2, inRange: { color: [C.down, '#BBF7D0', '#FFFFFF', '#FECACA', C.up] } },
    series: [{ type: 'heatmap', data: monthly.data.map(d => [d[0], d[1], d[2]]),
      label: { show: true, fontSize: 10, color: '#0F172A', formatter: p => isNum(p.value[2]) ? p.value[2].toFixed(1) : '' },
      itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 4 } }],
  }, 40 + 30 * Math.max(3, monthly.years.length));
}

/* ---------------- 横向条形 ---------------- */
function chartHBar(el, names, values, opt = {}) {
  const items = names.map((n, i) => ({ n, v: values[i] })).filter(x => isNum(x.v)).sort((a, b) => a.v - b.v);
  const fmt = opt.fmt || vf.p2;
  return mkChart(el, baseOpt({
    legend: { show: false }, toolbox: { show: false },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: fmt },
    grid: { left: 8, right: 56, top: 8, bottom: 8, containLabel: true },
    xAxis: yVal({ scale: false, axisLabel: opt.pct ? { formatter: '{value}%' } : {} }),
    yAxis: { type: 'category', data: items.map(x => x.n), axisLine: { lineStyle: { color: C.axis } }, axisTick: { show: false },
      axisLabel: { color: '#334155', fontSize: 12, width: 170, overflow: 'truncate' } },
    series: [{ type: 'bar', barMaxWidth: 18, name: opt.name || '',
      data: items.map(x => ({ value: x.v, itemStyle: { color: opt.color || (x.v >= 0 ? C.up : C.down), borderRadius: x.v >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4] },
        label: { show: true, position: x.v >= 0 ? 'right' : 'left', formatter: p => fmt(p.value), fontSize: 11, color: '#475569' } })) }],
  }), Math.max(240, items.length * 32 + 30));
}

/* ---------------- 分组柱 ---------------- */
function chartGrouped(el, names, groups, overlay) {
  const series = Object.entries(groups).map(([k, v], i) => ({ type: 'bar', name: k, data: v, barMaxWidth: 16,
    itemStyle: { color: C.palette[i], borderRadius: [3, 3, 0, 0] }, tooltip: { valueFormatter: vf.p3 } }));
  if (overlay) series.push({ type: 'scatter', name: overlay.name, data: overlay.values, symbol: 'diamond', symbolSize: 12,
    itemStyle: { color: '#0F172A' }, tooltip: { valueFormatter: vf.p3 }, z: 5 });
  return mkChart(el, baseOpt({
    tooltip: { axisPointer: { type: 'shadow' } }, grid: { top: 44 },
    xAxis: { type: 'category', data: names.map(short), axisLine: { lineStyle: { color: C.axis } }, axisTick: { show: false },
      axisLabel: { color: C.muted, fontSize: 11, interval: 0, width: 90, overflow: 'truncate' } },
    yAxis: yVal({ scale: false }),
    series,
  }), 360);
}
