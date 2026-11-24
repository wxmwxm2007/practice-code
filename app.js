/* =========================================================
   WebLog Sentinel — 前端交互
   职责：上传日志 → 调后端 API → 用 ECharts 渲染图表 → 表格筛选与导出
   ========================================================= */

const state = {
  data: null,
  alerts: [],
  groups: [],
  level: '',
  category: '',
  keyword: '',
  view: 'detail',
  page: 1,
  pageSize: 20,
  charts: {},
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

/* ---------- 工具函数 ---------- */
function escapeHtml(str) {
  return String(str == null ? '' : str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function truncate(str, n) {
  str = String(str || '');
  return str.length > n ? str.slice(0, n - 1) + '…' : str;
}

function fmtNumber(n) {
  return Number(n || 0).toLocaleString('zh-CN');
}

function fmtPercent(v, digits = 2) {
  return (Number(v || 0) * 100).toFixed(digits) + '%';
}

function fmtBytes(n) {
  if (!n) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return n.toFixed(i ? 1 : 0) + ' ' + units[i];
}

let toastTimer = null;
function toast(msg, isError = false) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.toggle('error', isError);
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}

function showLoading(text) {
  $('#loading-text').textContent = text || '正在解析日志、执行异常检测…';
  $('#loading').classList.remove('hidden');
  const bar = $('#progress-bar');
  bar.style.width = '8%';
  // 后端很快，这里只是给用户一个“在干活”的可视反馈
  let w = 8;
  window._progressTimer = setInterval(() => {
    w = Math.min(w + Math.random() * 18, 88);
    bar.style.width = w + '%';
  }, 160);
}

function hideLoading() {
  clearInterval(window._progressTimer);
  $('#progress-bar').style.width = '100%';
  setTimeout(() => $('#loading').classList.add('hidden'), 320);
}

/* ---------- 数据请求 ---------- */
async function analyzeFile(file) {
  if (!file) return;
  if (file.size > 100 * 1024 * 1024) {
    toast('文件超过 100MB 上限，请拆分后再上传', true);
    return;
  }
  showLoading(`正在解析 ${file.name} …`);
  const fd = new FormData();
  fd.append('file', file);
  try {
    const resp = await fetch('/api/analyze', { method: 'POST', body: fd });
    const json = await resp.json();
    if (!json.ok) throw new Error(json.error || '分析失败');
    hideLoading();
    render(json.data);
  } catch (err) {
    hideLoading();
    toast(err.message || '请求失败，请确认后端服务已启动', true);
  }
}

async function loadDemo() {
  showLoading('正在加载演示日志…');
  try {
    const resp = await fetch('/api/demo', { method: 'POST' });
    const json = await resp.json();
    if (!json.ok) throw new Error(json.error || '演示数据加载失败');
    hideLoading();
    render(json.data);
  } catch (err) {
    hideLoading();
    toast(err.message || '演示数据加载失败', true);
  }
}

/* ---------- 主渲染 ---------- */
function render(data) {
  state.data = data;
  state.alerts = data.anomalies.alerts;
  state.groups = data.anomalies.groups;
  state.level = '';
  state.category = '';
  state.keyword = '';
  state.page = 1;
  state.view = 'detail';

  $('#landing').classList.add('hidden');
  $('#result').classList.remove('hidden');

  renderFileBar(data);
  renderKpis(data);
  renderFilters(data);
  renderTable();
  renderSide(data);

  // 容器刚从 display:none 变成可见，等一帧再初始化 ECharts，避免宽度为 0
  requestAnimationFrame(() => renderCharts(data));

  if (data.meta.failed > 0) {
    toast(`有 ${data.meta.failed} 行无法解析（共 ${data.meta.total_lines} 行），已跳过`, true);
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderFileBar(data) {
  const m = data.meta;
  const ov = data.overview;
  const st = ov.start_time ? ov.start_time.replace('T', ' ').slice(0, 16) : '-';
  const et = ov.end_time ? ov.end_time.replace('T', ' ').slice(0, 16) : '-';
  $('#file-name').textContent = m.filename;
  $('#file-meta').innerHTML =
    `${fmtNumber(m.parsed)} 行已解析 · ${fmtBytes(m.file_size)} · ` +
    `解析 ${m.parse_ms} ms / 全流程 ${m.total_ms} ms · ` +
    `${escapeHtml(st)} 至 ${escapeHtml(et)}`;
}

function renderKpis(data) {
  const ov = data.overview;
  const an = data.anomalies.summary;
  const cards = [
    { label: '总请求数', value: fmtNumber(ov.total_requests), cls: '' },
    { label: '独立 IP', value: fmtNumber(ov.unique_ips), cls: '' },
    { label: '错误率 (4xx/5xx)', value: fmtPercent(ov.error_rate, 1), cls: ov.error_rate >= 0.2 ? 'orange' : 'green' },
    { label: '告警总数', value: fmtNumber(an.total), cls: 'orange' },
    { label: '高危告警', value: fmtNumber(an.high), cls: 'red' },
    { label: '受影响 IP', value: fmtNumber(an.affected_ips), cls: 'purple' },
  ];
  $('#kpis').innerHTML = cards.map((c) => `
    <div class="kpi ${c.cls}">
      <div class="label">${c.label}</div>
      <div class="value">${c.value}</div>
    </div>`).join('');
}

/* ---------- 图表 ---------- */
const CHART_TEXT = '#93a4bd';
const CHART_LINE = 'rgba(120,170,255,0.16)';

function baseGrid(extra = {}) {
  return Object.assign({ left: 46, right: 18, top: 34, bottom: 28, containLabel: true }, extra);
}

function getChart(id) {
  const dom = document.getElementById(id);
  if (!dom) return null;
  let inst = echarts.getInstanceByDom(dom);
  if (!inst) inst = echarts.init(dom, null, { renderer: 'canvas' });
  state.charts[id] = inst;
  return inst;
}

function renderCharts(data) {
  renderTrend(data.trend);
  renderStatus(data.status);
  renderTopIps(data.top_ips);
  renderTopUrls(data.top_urls);
  renderMethods(data.methods);
  renderLevels(data.anomalies.summary);
  renderUa(data.ua_top);
}

function renderTrend(trend) {
  const inst = getChart('chart-trend');
  if (!inst) return;
  const gLabel = { minute: '按分钟', hour: '按小时', day: '按天' }[trend.granularity] || '按小时';
  $('#trend-tag').textContent = gLabel;

  const maxPoint = Math.max(...trend.total, 1);
  inst.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(12,20,34,0.96)',
      borderColor: 'rgba(120,170,255,0.3)',
      textStyle: { color: '#e6edf7', fontSize: 12 },
    },
    legend: { right: 6, top: 0, itemWidth: 12, itemHeight: 8, textStyle: { color: CHART_TEXT, fontSize: 11 } },
    grid: baseGrid({ top: 40, bottom: 24 }),
    xAxis: {
      type: 'category',
      data: trend.labels,
      boundaryGap: false,
      axisLabel: { color: CHART_TEXT, fontSize: 10, hideOverlap: true },
      axisLine: { lineStyle: { color: CHART_LINE } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      max: Math.ceil(maxPoint * 1.15),
      axisLabel: { color: CHART_TEXT, fontSize: 10 },
      splitLine: { lineStyle: { color: CHART_LINE } },
      axisLine: { show: false },
    },
    series: [
      {
        name: '总请求',
        type: 'line',
        smooth: 0.3,
        showSymbol: false,
        data: trend.total,
        lineStyle: { width: 2, color: '#38bdf8' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(56,189,248,0.30)' },
            { offset: 1, color: 'rgba(56,189,248,0.02)' },
          ]),
        },
      },
      {
        name: '异常请求 (4xx/5xx)',
        type: 'line',
        smooth: 0.3,
        showSymbol: false,
        data: trend.errors,
        lineStyle: { width: 1.6, color: '#f4525b', type: 'dashed' },
        itemStyle: { color: '#f4525b' },
      },
    ],
  }, true);
  inst.resize();
}

function statusColor(code) {
  if (code >= 500) return '#f4525b';
  if (code >= 400) return '#fb923c';
  if (code >= 300) return '#fbbf24';
  if (code >= 200) return '#34d399';
  return '#8b9bb4';
}

function renderStatus(status) {
  const inst = getChart('chart-status');
  if (!inst) return;
  const data = status.codes.map((c) => ({
    name: String(c.code),
    value: c.count,
    itemStyle: { color: statusColor(c.code) },
  }));
  const total = status.codes.reduce((s, c) => s + c.count, 0) || 1;

  inst.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(12,20,34,0.96)',
      borderColor: 'rgba(120,170,255,0.3)',
      textStyle: { color: '#e6edf7', fontSize: 12 },
      formatter: (p) => `${p.name} 状态码<br/>${fmtNumber(p.value)} 次（${(p.value / total * 100).toFixed(1)}%）`,
    },
    legend: {
      type: 'scroll',
      bottom: 0,
      left: 'center',
      itemWidth: 9,
      itemHeight: 9,
      textStyle: { color: CHART_TEXT, fontSize: 10 },
    },
    series: [{
      type: 'pie',
      radius: ['42%', '66%'],
      center: ['50%', '44%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#0d1420', borderWidth: 2 },
      label: { show: false },
      emphasis: { scaleSize: 6 },
      data,
    }],
  }, true);
  inst.resize();
}

function renderTopIps(items) {
  const inst = getChart('chart-ip');
  if (!inst) return;
  // ECharts 横向条形图默认从下往上排，这里反转一次让第 1 名显示在顶部
  const sorted = items.slice().reverse();

  inst.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(12,20,34,0.96)',
      borderColor: 'rgba(120,170,255,0.3)',
      textStyle: { color: '#e6edf7', fontSize: 12 },
      formatter: (ps) => {
        const p = ps[0];
        return `${p.name}<br/>${fmtNumber(p.value)} 次请求`;
      },
    },
    grid: baseGrid({ left: 8, right: 58, top: 8, bottom: 8 }),
    xAxis: {
      type: 'value',
      axisLabel: { color: CHART_TEXT, fontSize: 10 },
      splitLine: { lineStyle: { color: CHART_LINE } },
      axisLine: { show: false },
    },
    yAxis: {
      type: 'category',
      data: sorted.map((x) => x.ip),
      axisLabel: { color: CHART_TEXT, fontSize: 10.5, fontFamily: 'Consolas, monospace' },
      axisLine: { lineStyle: { color: CHART_LINE } },
      axisTick: { show: false },
    },
    series: [{
      type: 'bar',
      barWidth: 12,
      data: sorted.map((x, i) => ({
        value: x.count,
        itemStyle: {
          color: i === sorted.length - 1 && sorted.length > 1
            ? new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: 'rgba(244,82,91,0.35)' }, { offset: 1, color: '#f4525b' }])
            : new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: 'rgba(56,189,248,0.18)' }, { offset: 1, color: '#38bdf8' }]),
          borderRadius: [0, 6, 6, 0],
        },
      })),
      label: { show: true, position: 'right', color: CHART_TEXT, fontSize: 10.5, formatter: (p) => fmtNumber(p.value) },
    }],
  }, true);
  inst.resize();
}

function renderTopUrls(items) {
  const inst = getChart('chart-url');
  if (!inst) return;
  const sorted = items.slice().reverse();

  inst.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(12,20,34,0.96)',
      borderColor: 'rgba(120,170,255,0.3)',
      textStyle: { color: '#e6edf7', fontSize: 12 },
      formatter: (ps) => {
        const p = ps[0];
        const raw = sorted[p.dataIndex];
        return `${raw ? escapeHtml(raw.url) : escapeHtml(p.name)}<br/>${fmtNumber(p.value)} 次请求`;
      },
    },
    grid: baseGrid({ left: 8, right: 58, top: 8, bottom: 8 }),
    xAxis: {
      type: 'value',
      splitNumber: 2,
      axisLabel: { color: CHART_TEXT, fontSize: 10, formatter: (v) => (v >= 1000 ? `${v / 1000}k` : v) },
      splitLine: { lineStyle: { color: CHART_LINE } },
      axisLine: { show: false },
    },
    yAxis: {
      type: 'category',
      data: sorted.map((x) => truncate(x.url, 22)),
      axisLabel: { color: CHART_TEXT, fontSize: 10.5, fontFamily: 'Consolas, monospace', width: 110, overflow: 'truncate' },
      axisLine: { lineStyle: { color: CHART_LINE } },
      axisTick: { show: false },
    },
    series: [{
      type: 'bar',
      barWidth: 12,
      data: sorted.map((x) => ({
        value: x.count,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: 'rgba(34,211,238,0.16)' }, { offset: 1, color: '#22d3ee' }]),
          borderRadius: [0, 6, 6, 0],
        },
      })),
      label: { show: true, position: 'right', color: CHART_TEXT, fontSize: 10.5, formatter: (p) => fmtNumber(p.value) },
    }],
  }, true);
  inst.resize();
}

function renderMethods(items) {
  const inst = getChart('chart-method');
  if (!inst) return;
  const colors = { GET: '#38bdf8', POST: '#a78bfa', HEAD: '#34d399', PUT: '#fb923c', DELETE: '#f4525b' };

  inst.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(12,20,34,0.96)',
      borderColor: 'rgba(120,170,255,0.3)',
      textStyle: { color: '#e6edf7', fontSize: 12 },
    },
    grid: baseGrid({ left: 40, right: 24, top: 20, bottom: 24 }),
    xAxis: {
      type: 'category',
      data: items.map((x) => x.method),
      axisLabel: { color: CHART_TEXT, fontSize: 11 },
      axisLine: { lineStyle: { color: CHART_LINE } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: CHART_TEXT, fontSize: 10 },
      splitLine: { lineStyle: { color: CHART_LINE } },
    },
    series: [{
      type: 'bar',
      barWidth: 34,
      data: items.map((x) => ({
        value: x.count,
        itemStyle: {
          color: colors[x.method] || '#7dd3fc',
          borderRadius: [6, 6, 0, 0],
          opacity: 0.85,
        },
      })),
      label: { show: true, position: 'top', color: CHART_TEXT, fontSize: 10.5, formatter: (p) => fmtNumber(p.value) },
    }],
  }, true);
  inst.resize();
}

function renderLevels(sum) {
  const inst = getChart('chart-level');
  if (!inst) return;
  const data = [
    { name: '高危', value: sum.high, itemStyle: { color: '#f4525b' } },
    { name: '中危', value: sum.medium, itemStyle: { color: '#fb923c' } },
    { name: '低危', value: sum.low, itemStyle: { color: '#fbbf24' } },
  ];

  inst.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(12,20,34,0.96)',
      borderColor: 'rgba(120,170,255,0.3)',
      textStyle: { color: '#e6edf7', fontSize: 12 },
      formatter: (p) => `${p.name}：${fmtNumber(p.value)} 条`,
    },
    legend: { bottom: 0, left: 'center', itemWidth: 9, itemHeight: 9, textStyle: { color: CHART_TEXT, fontSize: 10 } },
    title: {
      text: fmtNumber(sum.total),
      subtext: '告警总数',
      left: 'center',
      top: '32%',
      textStyle: { color: '#e6edf7', fontSize: 20, fontWeight: 700 },
      subtextStyle: { color: '#8b9bb4', fontSize: 11 },
    },
    series: [{
      type: 'pie',
      radius: ['52%', '72%'],
      center: ['50%', '44%'],
      itemStyle: { borderColor: '#0d1420', borderWidth: 2 },
      label: { show: false },
      data,
    }],
  }, true);
  inst.resize();
}

function shortUa(ua) {
  // 长 UA 只显示有辨识度的浏览器名 + 版本，图表标签才读得懂
  if (!ua) return '(空 UA)';
  const patterns = [/Edg\/[\d.]+/, /Chrome\/[\d.]+/, /Firefox\/[\d.]+/,
                    /MicroMessenger\/[\d.]+/, /Baiduspider\/[\d.]+/, /Version\/[\d.]+/];
  const hit = patterns.map((re) => ua.match(re)).find(Boolean);
  const mobile = /iPhone/.test(ua) ? 'iPhone' : (/Android/.test(ua) ? 'Android' : '');
  if (hit) return (mobile ? mobile + ' ' : '') + hit[0];
  if (mobile) return mobile;
  return truncate(ua, 18);
}

function renderUa(items) {
  const inst = getChart('chart-ua');
  if (!inst) return;
  const sorted = items.slice().reverse();

  inst.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(12,20,34,0.96)',
      borderColor: 'rgba(120,170,255,0.3)',
      textStyle: { color: '#e6edf7', fontSize: 12 },
      formatter: (ps) => {
        const raw = sorted[ps[0].dataIndex];
        return `${escapeHtml(raw ? raw.ua : ps[0].name)}<br/>${fmtNumber(ps[0].value)} 次请求`;
      },
    },
    grid: baseGrid({ left: 8, right: 52, top: 8, bottom: 8 }),
    xAxis: {
      type: 'value',
      splitNumber: 2,
      axisLabel: { color: CHART_TEXT, fontSize: 10, formatter: (v) => (v >= 1000 ? `${v / 1000}k` : v) },
      splitLine: { lineStyle: { color: CHART_LINE } },
      axisLine: { show: false },
    },
    yAxis: {
      type: 'category',
      data: sorted.map((x) => shortUa(x.ua)),
      axisLabel: { color: CHART_TEXT, fontSize: 10, width: 108, overflow: 'truncate' },
      axisLine: { lineStyle: { color: CHART_LINE } },
      axisTick: { show: false },
    },
    series: [{
      type: 'bar',
      barWidth: 11,
      data: sorted.map((x) => ({
        value: x.count,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: 'rgba(167,139,250,0.16)' }, { offset: 1, color: '#a78bfa' }]),
          borderRadius: [0, 6, 6, 0],
        },
      })),
      label: { show: true, position: 'right', color: CHART_TEXT, fontSize: 10, formatter: (p) => fmtNumber(p.value) },
    }],
  }, true);
  inst.resize();
}

/* ---------- 表格 ---------- */
function renderFilters(data) {
  const cats = [...new Set(state.alerts.map((a) => a.category))];
  $('#category-filter').innerHTML = '<option value="">全部类别</option>' +
    cats.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
  $('#category-filter').value = '';
  $('#alert-search').value = '';
  $$('#level-filter .pill').forEach((p) => p.classList.toggle('active', p.dataset.level === ''));
  $$('.seg').forEach((s) => s.classList.toggle('active', s.dataset.view === 'detail'));
  $('#alert-count').textContent = `${fmtNumber(state.alerts.length)} 条告警 · ${fmtNumber(state.groups.length)} 组`;
}

function getFiltered() {
  const kw = state.keyword.trim().toLowerCase();
  const source = state.view === 'detail' ? state.alerts : state.groups;
  return source.filter((a) => {
    if (state.level && a.level !== state.level) return false;
    if (state.category && a.category !== state.category) return false;
    if (!kw) return true;
    const hay = state.view === 'detail'
      ? [a.ip, a.url, a.rule_names.join(' '), a.evidence, a.category].join(' ')
      : [a.ip, a.rules, a.category].join(' ');
    return hay.toLowerCase().includes(kw);
  });
}

function statusClass(code) {
  if (code >= 500) return 's5';
  if (code >= 400) return 's4';
  if (code >= 300) return 's3';
  if (code >= 200) return 's2';
  return 'faint';
}

function fmtLogTime(t) {
  // '07/Sep/2026:02:10:00 +0800' → '09-07 02:10'
  if (!t || t === '-') return '-';
  const months = { Jan: '01', Feb: '02', Mar: '03', Apr: '04', May: '05', Jun: '06',
                   Jul: '07', Aug: '08', Sep: '09', Oct: '10', Nov: '11', Dec: '12' };
  const m = String(t).match(/(\d{2})\/(\w{3})\/(\d{4}):(\d{2}:\d{2})/);
  if (!m) return t;
  return `${months[m[2]] || m[2]}-${m[1]} ${m[4]}`;
}

function renderTable() {
  const rows = getFiltered();
  const thead = state.view === 'detail'
    ? ['等级', 'IP', '时间', '请求', '状态', '命中规则', '证据']
    : ['等级', 'IP', '类别', '命中规则', '告警次数'];

  $('#alert-table thead').innerHTML = thead.map((h) => `<th>${h}</th>`).join('');

  const totalPages = Math.max(1, Math.ceil(rows.length / state.pageSize));
  if (state.page > totalPages) state.page = totalPages;
  const start = (state.page - 1) * state.pageSize;
  const pageRows = rows.slice(start, start + state.pageSize);

  let html = '';
  if (!pageRows.length) {
    html = `<tr><td class="empty-row" colspan="${thead.length}">没有符合条件的告警</td></tr>`;
  } else if (state.view === 'detail') {
    html = pageRows.map((a) => {
      const req = `${a.method || '-'} ${a.url || '-'}`;
      return `
      <tr>
        <td><span class="lv ${a.level}" title="${escapeHtml(a.id)}">${escapeHtml(a.level_label)}</span></td>
        <td class="mono">${escapeHtml(a.ip)}</td>
        <td class="mono dim">${escapeHtml(fmtLogTime(a.time))}</td>
        <td><span class="mono ellipsis" title="${escapeHtml(req)}">${escapeHtml(req)}</span></td>
        <td><span class="status-code ${statusClass(a.status)} mono">${a.status || '-'}</span></td>
        <td class="dim"><span class="ellipsis" style="max-width:180px" title="${escapeHtml(a.rule_names.join('、'))}">${escapeHtml(a.rule_names.join('、'))}</span></td>
        <td class="faint"><span class="ellipsis" style="max-width:190px" title="${escapeHtml(a.evidence)}">${escapeHtml(a.evidence)}</span></td>
      </tr>`;
    }).join('');
  } else {
    html = pageRows.map((g) => `
      <tr>
        <td><span class="lv ${g.level}">${escapeHtml(g.level_label)}</span></td>
        <td class="mono">${escapeHtml(g.ip)}</td>
        <td class="dim">${escapeHtml(g.category)}</td>
        <td class="dim">${escapeHtml(g.rules)}</td>
        <td class="mono">${fmtNumber(g.count)}</td>
      </tr>`).join('');
  }
  $('#alert-table tbody').innerHTML = html;

  $('#pager').innerHTML = `
    <span>共 ${fmtNumber(rows.length)} 条 · 第 ${state.page}/${totalPages} 页</span>
    <button id="prev-page" ${state.page <= 1 ? 'disabled' : ''}>上一页</button>
    <button id="next-page" ${state.page >= totalPages ? 'disabled' : ''}>下一页</button>`;
  const prev = $('#prev-page');
  const next = $('#next-page');
  if (prev) prev.onclick = () => { state.page--; renderTable(); };
  if (next) next.onclick = () => { state.page++; renderTable(); };
}

/* ---------- 侧栏 ---------- */
function renderSide(data) {
  const an = data.anomalies;

  const freq = an.high_freq_ips.slice(0, 5);
  $('#mini-freq').innerHTML = freq.length
    ? freq.map((x) => `
      <div class="mini-row">
        <span class="k mono" title="${escapeHtml(x.ip)}">${escapeHtml(x.ip)}</span>
        <span class="v">${fmtNumber(x.peak_per_minute)} 次/分</span>
      </div>`).join('')
    : '<div class="mini-empty">没有可疑的高频 IP</div>';

  let attackHtml = '';
  if (an.bruteforce.length) {
    attackHtml += an.bruteforce.slice(0, 3).map((b) => `
      <div class="mini-row">
        <span class="k mono">${escapeHtml(b.ip)}</span>
        <span class="v" style="color:${b.success ? '#ff8b92' : '#ffb377'}">
          爆破 ${b.fails} 次${b.success ? ' · 有成功' : ''}
        </span>
      </div>`).join('');
  }
  if (an.scanner_ips.length) {
    attackHtml += an.scanner_ips.slice(0, 3).map((s) => `
      <div class="mini-row">
        <span class="k mono">${escapeHtml(s.ip)}</span>
        <span class="v">404 ${fmtPercent(s.rate, 0)} · ${fmtNumber(s.total)} 次</span>
      </div>`).join('');
  }
  if (an.error_rate_ips.length && !an.scanner_ips.length) {
    attackHtml += an.error_rate_ips.slice(0, 3).map((e) => `
      <div class="mini-row">
        <span class="k mono">${escapeHtml(e.ip)}</span>
        <span class="v">错误率 ${fmtPercent(e.error_rate, 0)}</span>
      </div>`).join('');
  }
  $('#mini-attack').innerHTML = attackHtml || '<div class="mini-empty">没有发现扫描或爆破行为</div>';

  $('#rule-list').innerHTML = an.rules.map((r) => `
    <div class="rule-item">
      <div class="rule-top">
        <span class="rule-id">${escapeHtml(r.id)}</span>
        <span class="rule-name">${escapeHtml(r.name)}</span>
      </div>
      <div class="rule-pattern" title="${escapeHtml(r.pattern)}">${escapeHtml(truncate(r.pattern, 46))}</div>
    </div>`).join('');

  const th = an.thresholds;
  $('#thresholds').innerHTML = `
    <div>每分钟请求阈值 <b>${th.high_freq_per_minute}</b></div>
    <div>错误率阈值 <b>${fmtPercent(th.error_rate, 0)}</b></div>
    <div>错误率最小样本 <b>${th.error_min_requests}</b></div>
    <div>爆破失败次数 <b>${th.bruteforce_fails}</b></div>`;

  renderRuleModal(an.rules, th);
}

function renderRuleModal(rules, th) {
  $('#rule-modal-list').innerHTML = rules.map((r) => `
    <div class="rule-item">
      <div class="rule-top">
        <span class="lv ${r.level}">${escapeHtml({ high: '高危', medium: '中危', low: '低危' }[r.level] || r.level)}</span>
        <span class="rule-id">${escapeHtml(r.id)}</span>
        <span class="rule-name">${escapeHtml(r.name)}</span>
        <span class="badge">${escapeHtml(r.type)}</span>
      </div>
      <div class="rule-pattern">${escapeHtml(r.pattern)}</div>
    </div>`).join('') + `
    <div class="thresholds">
      <div>高频阈值 <b>${th.high_freq_per_minute} 次/分</b></div>
      <div>错误率阈值 <b>${fmtPercent(th.error_rate, 0)}</b></div>
      <div>最小样本 <b>${th.error_min_requests}</b></div>
      <div>爆破失败次数 <b>${th.bruteforce_fails}</b></div>
      <div>404 占比阈值 <b>${fmtPercent(th.scan_404_rate, 0)}</b></div>
    </div>`;
}

/* ---------- 事件绑定 ---------- */
function bindEvents() {
  // 三处上传入口共用同一个处理函数
  ['#file-input', '#file-input-top', '#file-input-again'].forEach((sel) => {
    const el = $(sel);
    if (el) el.addEventListener('change', (e) => {
      analyzeFile(e.target.files[0]);
      e.target.value = '';
    });
  });

  const dz = $('#dropzone');
  ['dragenter', 'dragover'].forEach((ev) => dz.addEventListener(ev, (e) => {
    e.preventDefault();
    dz.classList.add('hover');
  }));
  ['dragleave', 'drop'].forEach((ev) => dz.addEventListener(ev, (e) => {
    e.preventDefault();
    dz.classList.remove('hover');
  }));
  dz.addEventListener('drop', (e) => {
    const f = e.dataTransfer.files[0];
    if (f) analyzeFile(f);
  });
  dz.addEventListener('click', (e) => {
    // 点 <label> 时浏览器已经会触发一次 input，这里不再重复触发
    if (e.target.closest('label')) return;
    $('#file-input').click();
  });

  $('#btn-demo').onclick = loadDemo;
  $('#btn-demo-top').onclick = loadDemo;

  // 规则弹窗
  $('#btn-rules').onclick = () => $('#rules-modal').classList.remove('hidden');
  $('#btn-close-rules').onclick = () => $('#rules-modal').classList.add('hidden');
  $('#rules-modal').addEventListener('click', (e) => {
    if (e.target.id === 'rules-modal') e.target.classList.add('hidden');
  });

  // 等级筛选
  $$('#level-filter .pill').forEach((btn) => {
    btn.onclick = () => {
      state.level = btn.dataset.level;
      state.page = 1;
      $$('#level-filter .pill').forEach((b) => b.classList.toggle('active', b === btn));
      renderTable();
    };
  });

  $('#category-filter').onchange = (e) => {
    state.category = e.target.value;
    state.page = 1;
    renderTable();
  };

  let searchTimer = null;
  $('#alert-search').addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.keyword = e.target.value;
      state.page = 1;
      renderTable();
    }, 200);
  });

  // 明细 / 聚合视图切换
  $$('.seg').forEach((seg) => {
    seg.onclick = () => {
      state.view = seg.dataset.view;
      state.page = 1;
      $$('.seg').forEach((s) => s.classList.toggle('active', s === seg));
      renderTable();
    };
  });

  // 导出
  $('#btn-export-alerts').onclick = () => {
    if (!state.data) return;
    const level = state.level ? `?level=${state.level}` : '';
    window.location.href = `/api/export/anomalies.csv${level}`;
    toast('CSV 已开始下载（UTF-8-SIG，Excel 可直接打开）');
  };

  $('#btn-export-stats').onclick = () => {
    if (!state.data) return;
    window.location.href = '/api/export/stats.csv';
    toast('统计 CSV 已开始下载');
  };

  // 窗口尺寸变化时重排所有图表
  let resizeTimer = null;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      Object.values(state.charts).forEach((c) => c && c.resize());
    }, 150);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  bindEvents();
  // 页面打开时先拉一次规则清单，让"检测规则"弹窗在未分析日志时也能看
  fetch('/api/rules').then((r) => r.json()).then((j) => {
    if (j.ok) renderRuleModal(j.data.rules, j.data.thresholds);
  }).catch(() => {});

  // 演示彩蛋：访问 /?demo=1 自动加载演示日志，现场演示可以省掉一次点击
  const params = new URLSearchParams(window.location.search);
  if (params.get('demo') === '1') loadDemo();
});
