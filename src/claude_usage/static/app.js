/* Claude Code Usage Dashboard */

let statsData = null;
let currentRange = '7d';
let currentTab = 'overview';
let dailyChart = null;
let realtimeTimer = null;

// Color palette for models
const MODEL_COLORS = [
    '#4a9eff', '#6366f1', '#a78bfa', '#818cf8',
    '#38bdf8', '#22d3ee', '#2dd4bf', '#34d399',
    '#a3e635', '#facc15', '#fb923c', '#f87171',
];

// ---------- Init ----------
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupTimeRange();
    fetchStats();
});

function setupTabs() {
    document.querySelectorAll('.tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            currentTab = btn.dataset.tab;
            document.getElementById('tab-' + currentTab).classList.add('active');

            // Show/hide time range for realtime tab
            const trg = document.getElementById('timeRangeGroup');
            trg.style.display = currentTab === 'realtime' ? 'none' : 'flex';

            if (currentTab === 'realtime') {
                fetchRealtime();
                startRealtimePolling();
            } else {
                stopRealtimePolling();
                if (statsData) renderCurrentTab();
            }
        });
    });
}

function setupTimeRange() {
    document.querySelectorAll('.range-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentRange = btn.dataset.range;
            if (statsData) renderCurrentTab();
        });
    });
}

// ---------- Data Fetching ----------
async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        statsData = await res.json();
        renderCurrentTab();
    } catch (e) {
        console.error('Failed to fetch stats:', e);
    }

    // Auto-refresh every 60 seconds
    setTimeout(fetchStats, 60000);
}

async function fetchRealtime() {
    try {
        const res = await fetch('/api/realtime');
        const data = await res.json();
        renderRealtime(data.active_sessions);
    } catch (e) {
        console.error('Failed to fetch realtime:', e);
    }
}

function startRealtimePolling() {
    stopRealtimePolling();
    realtimeTimer = setInterval(fetchRealtime, 5000);
}

function stopRealtimePolling() {
    if (realtimeTimer) {
        clearInterval(realtimeTimer);
        realtimeTimer = null;
    }
}

// ---------- Rendering ----------
function renderCurrentTab() {
    const data = statsData[currentRange] || statsData['all'];
    if (currentTab === 'overview') renderOverview(data);
    else if (currentTab === 'models') renderModels(data);
    else if (currentTab === 'code') renderCode(data);
}

function renderOverview(data) {
    setText('stat-sessions', formatNumber(data.total_sessions));
    setText('stat-messages', formatNumber(data.total_messages));
    setText('stat-tokens', formatTokens(data.total_tokens));
    setText('stat-tokens-detail',
        `${formatTokens(data.total_input_tokens)} in / ${formatTokens(data.total_output_tokens)} out`);
    setText('stat-active-days', data.active_days);
    setText('stat-current-streak', data.current_streak + 'd');
    setText('stat-longest-streak', data.longest_streak + 'd');
    setText('stat-peak-hour', data.peak_hour + ':00');
    setText('stat-favorite-model', data.favorite_model || '-');

    renderHeatmap(data.heatmap);
    renderFunFact(data);
}

function renderHeatmap(heatmap) {
    const container = document.getElementById('heatmap');
    container.innerHTML = '';

    // Always show last 52 weeks, regardless of filter
    const today = new Date();
    let startDate = new Date(today);
    startDate.setDate(today.getDate() - 7 * 52);

    // Align to Sunday
    startDate.setDate(startDate.getDate() - startDate.getDay());

    // Find max value for color scaling
    const values = Object.values(heatmap).filter(v => v > 0);
    const maxVal = values.length > 0 ? Math.max(...values) : 1;

    // Build weeks
    const d = new Date(startDate);
    while (d <= today) {
        const weekDiv = document.createElement('div');
        weekDiv.className = 'heatmap-week';

        for (let dow = 0; dow < 7; dow++) {
            const cell = document.createElement('div');
            cell.className = 'heatmap-cell';

            const dateStr = d.toISOString().split('T')[0];
            const count = heatmap[dateStr] || 0;

            cell.style.backgroundColor = getHeatmapColor(count, maxVal);
            cell.setAttribute('data-tooltip', `${dateStr}: ${count} 条消息`);

            weekDiv.appendChild(cell);
            d.setDate(d.getDate() + 1);
        }

        container.appendChild(weekDiv);
    }
}

function getHeatmapColor(count, maxVal) {
    if (count === 0) return '#ebedf0';
    const ratio = count / maxVal;
    if (ratio <= 0.25) return '#9be9a8';
    if (ratio <= 0.50) return '#40c463';
    if (ratio <= 0.75) return '#30a14e';
    return '#216e39';
}

function renderFunFact(data) {
    const el = document.getElementById('fun-fact');
    if (data.total_tokens > 0) {
        // Animal Farm is ~100k tokens
        const animalFarmTokens = 100000;
        const multiple = Math.round(data.total_tokens / animalFarmTokens);
        if (multiple > 0) {
            el.textContent = `You've used ~${multiple}x more tokens than Animal Farm.`;
            el.classList.add('visible');
        } else {
            el.classList.remove('visible');
        }
    } else {
        el.classList.remove('visible');
    }
}

function renderModels(data) {
    renderDailyChart(data.daily_tokens);
    renderModelsList(data.models, data.total_tokens);
}

function renderDailyChart(dailyTokens) {
    const ctx = document.getElementById('dailyChart').getContext('2d');

    // Collect all dates and models
    const dates = Object.keys(dailyTokens).sort();
    const allModels = new Set();
    dates.forEach(d => {
        Object.keys(dailyTokens[d]).forEach(m => allModels.add(m));
    });
    const models = Array.from(allModels);

    // Format date labels
    const labels = dates.map(d => {
        const date = new Date(d + 'T00:00:00');
        return `${date.getMonth() + 1}月${date.getDate()}日`;
    });

    // Build datasets - stacked by model
    const datasets = models.map((model, i) => ({
        label: model,
        data: dates.map(d => {
            const md = dailyTokens[d]?.[model];
            return md ? md.input_tokens + md.output_tokens : 0;
        }),
        backgroundColor: MODEL_COLORS[i % MODEL_COLORS.length],
        borderRadius: 4,
        borderSkipped: false,
    }));

    if (dailyChart) dailyChart.destroy();

    dailyChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => {
                            if (!items.length) return '';
                            return dates[items[0].dataIndex];
                        },
                        label: (item) => {
                            const date = dates[item.dataIndex];
                            const model = models[item.datasetIndex];
                            const md = dailyTokens[date]?.[model];
                            if (!md) return '';
                            return `${model}: ${formatTokens(md.input_tokens)} in · ${formatTokens(md.output_tokens)} out`;
                        },
                        footer: (items) => {
                            const date = dates[items[0].dataIndex];
                            let total = 0;
                            models.forEach(m => {
                                const md = dailyTokens[date]?.[m];
                                if (md) total += md.input_tokens + md.output_tokens;
                            });
                            return `Total: ${formatTokens(total)}`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    stacked: true,
                    grid: { display: false },
                    ticks: { font: { size: 11 } },
                },
                y: {
                    stacked: true,
                    grid: { color: '#f0f0f0' },
                    ticks: {
                        font: { size: 11 },
                        callback: v => formatTokens(v),
                    },
                },
            },
        },
    });
}

function renderModelsList(models, totalTokens) {
    const container = document.getElementById('models-list');
    container.innerHTML = '';

    models.forEach((m, i) => {
        const item = document.createElement('div');
        item.className = 'model-item';

        const dot = document.createElement('div');
        dot.className = 'model-dot';
        dot.style.backgroundColor = MODEL_COLORS[i % MODEL_COLORS.length];

        const name = document.createElement('div');
        name.className = 'model-name';
        name.textContent = m.model;

        const tokens = document.createElement('div');
        tokens.className = 'model-tokens';
        tokens.textContent = `${formatTokens(m.input_tokens)} in · ${formatTokens(m.output_tokens)} out`;

        const pct = document.createElement('div');
        pct.className = 'model-percentage';
        pct.textContent = m.percentage + '%';

        item.append(dot, name, tokens, pct);
        container.appendChild(item);
    });
}

// ---------- Code Tab ----------
let codeChart = null;

const CODE_LANG_COLORS = [
    '#22d3ee', '#a78bfa', '#facc15', '#4ade80',
    '#f87171', '#fb923c', '#38bdf8', '#c084fc',
    '#fbbf24', '#4ade80', '#67e8f9', '#fda4af',
    '#86efac', '#fcd34d', '#93c5fd', '#d8b4fe',
];

function renderCode(data) {
    const codeData = data.code_lines || { daily: {}, total: 0, languages: {} };
    setText('code-total', formatNumber(codeData.total));
    setText('code-langs', Object.keys(codeData.languages).length);

    renderCodeChart(codeData.daily);
    renderCodeLegend(codeData.languages);
}

function renderCodeChart(daily) {
    const ctx = document.getElementById('codeChart').getContext('2d');
    const dates = Object.keys(daily).sort();
    const allLangs = new Set();
    dates.forEach(d => Object.keys(daily[d]).forEach(l => allLangs.add(l)));
    const langs = Array.from(allLangs).sort((a, b) => {
        let totalA = 0, totalB = 0;
        dates.forEach(d => { totalA += Math.abs(daily[d][a] || 0); totalB += Math.abs(daily[d][b] || 0); });
        return totalB - totalA;
    });

    const labels = dates.map(d => {
        const dt = new Date(d + 'T00:00:00');
        return `${dt.getMonth() + 1}月${dt.getDate()}日`;
    });

    const datasets = langs.map((lang, i) => ({
        label: lang,
        data: dates.map(d => {
            const val = daily[d]?.[lang] || 0;
            return val >= 0 ? val : 0;
        }),
        backgroundColor: CODE_LANG_COLORS[i % CODE_LANG_COLORS.length],
        borderRadius: 3,
        borderSkipped: false,
        stack: 'stack1',
    }));

    if (codeChart) codeChart.destroy();

    codeChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (item) => {
                            const lang = langs[item.datasetIndex];
                            const val = item.raw;
                            return `${lang}: +${formatNumber(val)} 行`;
                        },
                        footer: (items) => {
                            const idx = items[0].dataIndex;
                            const date = dates[idx];
                            let total = 0;
                            langs.forEach(l => { total += daily[date]?.[l] || 0; });
                            return `当日净增: ${formatNumber(total)} 行`;
                        }
                    }
                }
            },
            scales: {
                x: { stacked: true, grid: { display: false }, ticks: { font: { size: 11 } } },
                y: {
                    stacked: true,
                    grid: { color: '#f0f0f0' },
                    ticks: { font: { size: 11 }, callback: v => formatNumber(v) },
                }
            }
        }
    });
}

function renderCodeLegend(languages) {
    const container = document.getElementById('code-legend');
    container.innerHTML = '';
    const sorted = Object.entries(languages).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));

    sorted.forEach(([lang, lines], i) => {
        const item = document.createElement('div');
        item.className = 'model-item';

        const dot = document.createElement('div');
        dot.className = 'model-dot';
        dot.style.backgroundColor = CODE_LANG_COLORS[i % CODE_LANG_COLORS.length];

        const name = document.createElement('div');
        name.className = 'model-name';
        name.textContent = lang;

        const tokens = document.createElement('div');
        tokens.className = 'model-tokens';
        tokens.textContent = `${formatNumber(Math.abs(lines))} 行`;

        const pct = document.createElement('div');
        pct.className = 'model-percentage';
        const total = Object.values(languages).reduce((s, v) => s + Math.abs(v), 0);
        pct.textContent = total > 0 ? Math.round(Math.abs(lines) / total * 100) + '%' : '0%';

        item.append(dot, name, tokens, pct);
        container.appendChild(item);
    });
}

function renderRealtime(sessions) {
    const container = document.getElementById('realtime-content');

    if (!sessions || sessions.length === 0) {
        container.innerHTML = `
            <div class="realtime-empty">
                <div class="icon">&#9678;</div>
                <p>当前没有活跃的 Claude Code 会话</p>
                <p style="font-size:13px;color:#bbb;margin-top:8px;">启动 Claude Code CLI 后，这里将实时显示会话状态</p>
            </div>`;
        return;
    }

    container.innerHTML = sessions.map(s => {
        const contextPct = s.context_percentage || 0;
        const barClass = contextPct > 80 ? 'context-bar-fill warning' : 'context-bar-fill';
        const startTime = s.started_at
            ? new Date(s.started_at).toLocaleString('zh-CN')
            : '-';
        const uptime = s.started_at
            ? formatDuration(Date.now() - s.started_at)
            : '-';

        let subagentsHtml = '';
        if (s.subagents && s.subagents.length > 0) {
            subagentsHtml = `
                <div class="subagents-section">
                    <div class="subagents-title">Subagents (${s.subagents.length})</div>
                    ${s.subagents.map(a => `
                        <div class="subagent-item">
                            <span class="subagent-type">${a.agentType || 'unknown'}</span>
                            <span>${a.description || ''}</span>
                        </div>
                    `).join('')}
                </div>`;
        } else if (s.subagent_count && s.subagent_count > 0) {
            subagentsHtml = `
                <div class="subagents-section">
                    <div class="subagents-title">Subagents (${s.subagent_count})</div>
                </div>`;
        }

        return `
        <div class="session-card">
            <div class="session-header">
                <div class="session-title">${escapeHtml(s.cwd || 'Claude Code Session')}</div>
                <div class="session-status">
                    <div class="status-dot"></div>
                    <span style="color:#40c463">运行中</span>
                </div>
            </div>
            <div class="session-meta">
                <div class="meta-item">
                    <div class="meta-label">PID</div>
                    <div class="meta-value">${s.pid || '-'}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">运行时长</div>
                    <div class="meta-value">${uptime}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">消息数</div>
                    <div class="meta-value">${s.message_count || 0}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">模型</div>
                    <div class="meta-value small-text">${s.last_model || '-'}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Input Tokens</div>
                    <div class="meta-value">${formatTokens(s.total_input_tokens || 0)}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Output Tokens</div>
                    <div class="meta-value">${formatTokens(s.total_output_tokens || 0)}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">版本</div>
                    <div class="meta-value small-text">${s.version || '-'}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Git 分支</div>
                    <div class="meta-value small-text">${escapeHtml(s.git_branch || '-')}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">入口</div>
                    <div class="meta-value small-text">${s.entrypoint || '-'}</div>
                </div>
            </div>
            <div class="context-bar-container">
                <div class="context-bar-label">
                    <span>上下文使用</span>
                    <span>${formatTokens(s.context_used || 0)} / ${formatTokens(s.context_window || 200000)} (${contextPct}%)</span>
                </div>
                <div class="context-bar">
                    <div class="${barClass}" style="width:${Math.min(contextPct, 100)}%"></div>
                </div>
            </div>
            ${subagentsHtml}
        </div>`;
    }).join('');
}

// ---------- Utilities ----------
function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function formatNumber(n) {
    if (n == null) return '-';
    return n.toLocaleString('en-US');
}

function formatTokens(n) {
    if (n == null || n === 0) return '0';
    if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'k';
    return n.toString();
}

function formatDuration(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ${hours % 24}h`;
    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    if (minutes > 0) return `${minutes}m`;
    return `${seconds}s`;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
