/* ==================== 全局状态 ==================== */
let currentTaskId = null;
let ws = null;

/* ==================== 初始化 ==================== */
document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    loadTasks();
    connectWebSocket();

    document.getElementById('aiTemp').addEventListener('input', e => {
        document.getElementById('aiTempVal').textContent = e.target.value;
    });
});

/* ==================== 页面切换 ==================== */
function switchPage(page) {
    // 隐藏所有页面
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    // 取消所有 tab 选中
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

    // 显示目标页面
    document.getElementById(`page-${page}`).classList.add('active');
    // 高亮 tab
    event.target.classList.add('active');

    // 切换到设置时加载配置
    if (page === 'settings') {
        loadSettings();
        loadKeywordLibraries();
    }
    // 切换到热点时加载热点
    if (page === 'hotspot') {
        loadHotspots();
    }
}

/* ==================== WebSocket ==================== */
function connectWebSocket() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        switch (msg.type) {
            case 'status':
                addLog(msg.message, 'info');
                break;
            case 'task_update':
                handleTaskUpdate(msg.task);
                break;
        }
    };
    ws.onclose = () => setTimeout(connectWebSocket, 3000);
}

/* ==================== 热点采集 ==================== */
async function loadHotspots() {
    const container = document.getElementById('hotspotList');
    container.innerHTML = '<div class="empty-state">⏳ 加载中...</div>';

    try {
        const source = document.getElementById('hotspotSource').value;
        const res = await fetch(`/api/hotspots?sources=${source}`);
        const data = await res.json();
        const hotspots = data.hotspots || [];

        if (hotspots.length === 0) {
            container.innerHTML = '<div class="empty-state">暂无热点数据</div>';
            return;
        }

        container.innerHTML = hotspots.map((h, i) => `
            <div class="hotspot-item" onclick="useHotspot('${h.title.replace(/'/g, "\\'")}')">
                <span class="hotspot-rank">${i + 1}</span>
                <div class="hotspot-info">
                    <span class="hotspot-title">${h.title}</span>
                    <span class="hotspot-meta">${h.source} · ${h.category || '综合'} · 🔥${h.heat}</span>
                </div>
            </div>
        `).join('');

        addLog(`🔥 加载 ${hotspots.length} 条热点`, 'success');
    } catch (e) {
        container.innerHTML = '<div class="empty-state">加载失败: ' + e.message + '</div>';
    }
}

function useHotspot(title) {
    // 切换到创作页面并填入主题
    switchPage('create');
    document.querySelectorAll('.tab-btn')[1].classList.add('active');
    document.getElementById('topicInput').value = title;
    addLog(`📌 已填入热点: ${title}`, 'info');
}

/* ==================== 分类资讯 ==================== */
async function loadNews(category) {
    const container = document.getElementById(`news-${category}`);
    container.innerHTML = '<div class="empty-state">⏳ 加载中...</div>';

    // 用热点采集器获取对应分类
    try {
        const res = await fetch(`/api/hotspots?sources=baidu,toutiao`);
        const data = await res.json();
        const hotspots = (data.hotspots || []).filter(h => {
            const cat = (h.category || '').toLowerCase();
            if (category === 'ai') return cat.includes('科技') || cat.includes('ai') || cat.includes('人工');
            if (category === 'finance') return cat.includes('财经') || cat.includes('金融') || cat.includes('股');
            if (category === 'tech') return cat.includes('科技') || cat.includes('互联网') || cat.includes('数码');
            return true;
        });

        if (hotspots.length === 0) {
            // 不过滤，直接显示前5条
            const items = (data.hotspots || []).slice(0, 5);
            renderNews(container, items, category);
        } else {
            renderNews(container, hotspots.slice(0, 5), category);
        }
    } catch (e) {
        container.innerHTML = '<div class="empty-state">加载失败</div>';
    }
}

function renderNews(container, items, category) {
    if (items.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无数据</div>';
        return;
    }
    container.innerHTML = items.map(h => `
        <div class="news-item" onclick="useHotspot('${h.title.replace(/'/g, "\\'")}')">
            <span class="news-title">${h.title}</span>
            <span class="news-meta">${h.source} · ${h.heat}</span>
        </div>
    `).join('');
}

/* ==================== 高级选项 ==================== */
function toggleAdvanced() {
    const panel = document.getElementById('advancedPanel');
    const arrow = document.getElementById('advancedArrow');
    panel.classList.toggle('hidden');
    arrow.textContent = panel.classList.contains('hidden') ? '▼' : '▲';
}

/* ==================== 设置子页面切换 ==================== */
function switchSettingsTab(tab) {
    document.querySelectorAll('.settings-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.settings-nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`panel-${tab}`).classList.add('active');
    event.target.classList.add('active');
}

/* ==================== 标签输入 ==================== */
function addTopicTag(e, list) {
    if (e.key !== 'Enter') return;
    const input = e.target;
    const text = input.value.trim();
    if (!text) return;
    const listEl = document.getElementById(`topic${list === 'whitelist' ? 'Whitelist' : 'Blacklist'}`);
    const tag = document.createElement('span');
    tag.className = 'tag editable';
    tag.innerHTML = `${text} <button onclick="this.parentElement.remove()">×</button>`;
    listEl.appendChild(tag);
    input.value = '';
}

function getTagList(id) {
    const el = document.getElementById(id);
    if (!el) return [];
    return Array.from(el.querySelectorAll('.tag')).map(t => t.textContent.replace('×', '').trim());
}

/* ==================== 定时任务 ==================== */
function renderSchedules(schedules) {
    const container = document.getElementById('scheduleList');
    if (!schedules || schedules.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无定时任务，点击下方添加</div>';
        return;
    }
    const repeatLabels = { daily: '每天', workday: '工作日', weekend: '周末', mon: '周一', wed: '周三', fri: '周五' };
    container.innerHTML = schedules.map((s, i) => `
        <div class="schedule-item">
            <div class="schedule-info">
                <h4>${s.name}</h4>
                <p>⏰ ${s.time} · ${repeatLabels[s.repeat] || s.repeat} · 📱 ${(s.platforms || []).join(', ')}</p>
                <p>来源: ${s.source}</p>
            </div>
            <div class="schedule-actions">
                <label class="switch"><input type="checkbox" ${s.enabled ? 'checked' : ''} onchange="toggleSchedule(${i})"><span class="slider"></span></label>
                <button class="btn btn-sm" onclick="removeSchedule(${i})" style="color:var(--danger)">删除</button>
            </div>
        </div>
    `).join('');
}

function addSchedule() {
    const name = document.getElementById('newScheduleName').value.trim();
    const source = document.getElementById('newScheduleSource').value;
    const time = document.getElementById('newScheduleTime').value;
    const repeat = document.getElementById('newScheduleRepeat').value;
    const platformChecks = document.querySelectorAll('#panel-schedule .mini-tag input:checked');
    const platforms = Array.from(platformChecks).map(c => c.value);

    if (!name || !platforms.length) {
        addLog('⚠️ 请填写名称并选择至少一个平台', 'warning');
        return;
    }

    const schedules = window._config?.schedules || [];
    schedules.push({ name, source, time, repeat, platforms, enabled: true });
    window._config = window._config || {};
    window._config.schedules = schedules;

    document.getElementById('newScheduleName').value = '';
    renderSchedules(schedules);
    saveSettings();
}

function toggleSchedule(index) {
    if (window._config?.schedules?.[index]) {
        window._config.schedules[index].enabled = !window._config.schedules[index].enabled;
        saveSettings();
    }
}

function removeSchedule(index) {
    if (window._config?.schedules) {
        window._config.schedules.splice(index, 1);
        renderSchedules(window._config.schedules);
        saveSettings();
    }
}

/* ==================== 多账号 ==================== */
function renderAccounts(accounts) {
    const container = document.getElementById('accountsList');
    if (!accounts || accounts.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无账号，点击下方添加</div>';
        return;
    }
    const platformNames = { xiaohongshu: '📕 小红书', douyin: '🎵 抖音', wechat: '💚 公众号', kuaishou: '🔥 快手', bilibili: '📺 B站', wechat_video: '📱 视频号' };
    const styleNames = { informative: '📚 科普', entertaining: '😄 搞笑', professional: '💼 专业', emotional: '💭 情感', trending: '🔥 吐槽', custom: '✍️ 自定义' };
    container.innerHTML = accounts.map((a, i) => `
        <div class="account-item">
            <div class="account-info">
                <h4>${platformNames[a.platform] || a.platform} - ${a.name}</h4>
                <p>风格: ${styleNames[a.style] || a.style} · 每日上限: ${a.daily_limit || 1}条</p>
            </div>
            <button class="btn btn-sm" onclick="removeAccount(${i})" style="color:var(--danger)">删除</button>
        </div>
    `).join('');
}

function addAccount() {
    const platform = document.getElementById('newAccountPlatform').value;
    const name = document.getElementById('newAccountName').value.trim();
    const style = document.getElementById('newAccountStyle').value;
    const dailyLimit = parseInt(document.getElementById('newAccountLimit').value) || 1;

    if (!name) {
        addLog('⚠️ 请填写账号名称', 'warning');
        return;
    }

    const accounts = window._config?.accounts || [];
    accounts.push({ platform, name, style, daily_limit: dailyLimit });
    window._config = window._config || {};
    window._config.accounts = accounts;

    document.getElementById('newAccountName').value = '';
    renderAccounts(accounts);
    saveSettings();
}

function removeAccount(index) {
    if (window._config?.accounts) {
        window._config.accounts.splice(index, 1);
        renderAccounts(window._config.accounts);
        saveSettings();
    }
}

/* ==================== 违禁词检测 ==================== */
async function checkKeywords() {
    const text = document.getElementById('keywordTestText').value.trim();
    const platformChecks = document.querySelectorAll('#panel-keywords .mini-tag input:checked');
    const platforms = Array.from(platformChecks).map(c => c.value);
    const resultDiv = document.getElementById('keywordResult');

    if (!text) {
        resultDiv.innerHTML = '<span style="color:var(--warning)">请先粘贴内容</span>';
        return;
    }

    resultDiv.innerHTML = '<div class="empty-state">🔍 检测中...</div>';

    try {
        const res = await fetch('/api/check-keywords', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, platforms }),
        });
        const data = await res.json();

        const riskColors = { safe: 'var(--success)', low: 'var(--primary)', medium: 'var(--warning)', high: 'var(--danger)' };
        const riskLabels = { safe: '✅ 安全', low: '低风险', medium: '⚠️ 中风险', high: '🚨 高风险' };
        const riskIcons = { high: '🔴', medium: '🟡', spam: '🟣' };

        let html = `
            <div class="keyword-result-card" style="border-left: 4px solid ${riskColors[data.risk_level]}">
                <div class="keyword-result-header">
                    <span style="font-size:18px;font-weight:700;color:${riskColors[data.risk_level]}">${riskLabels[data.risk_level]}</span>
                    <span style="font-size:24px;font-weight:700">${data.score}</span>
                </div>
                <p style="color:var(--text-muted);font-size:13px;margin:8px 0">${data.summary}</p>
        `;

        if (data.issues.length > 0) {
            html += '<div class="keyword-issues">';
            data.issues.forEach(issue => {
                const reps = (issue.replacements || []).map(r => `<code>${r}</code>`).join(', ');
                html += `
                    <div class="keyword-issue">
                        <span>${riskIcons[issue.risk] || '⚪'} <strong>${issue.word}</strong></span>
                        <span class="issue-platform">${issue.platforms.join(', ')}</span>
                        <span class="issue-replacement">→ 建议替换: ${reps}</span>
                    </div>
                `;
            });
            html += '</div>';
        }

        html += '</div>';
        resultDiv.innerHTML = html;

    } catch (e) {
        resultDiv.innerHTML = `<span style="color:var(--danger)">检测失败: ${e.message}</span>`;
    }
}

async function loadKeywordLibraries() {
    const container = document.getElementById('keywordLibraries');
    const names = { common: '通用', xiaohongshu: '📕 小红书', douyin: '🎵 抖音', wechat: '💚 公众号' };
    try {
        const res = await fetch('/api/keywords');
        const data = await res.json();
        let html = '';
        for (const [platform, words] of Object.entries(data)) {
            const highCount = (words.high_risk || []).length;
            const medCount = (words.medium_risk || []).length;
            html += `
                <div class="keyword-lib-item">
                    <strong>${names[platform] || platform}</strong>
                    <span style="color:var(--text-muted);font-size:12px">🔴 ${highCount} 个高风险 · 🟡 ${medCount} 个中风险</span>
                </div>
            `;
        }
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<div class="empty-state">加载失败</div>';
    }
}

async function saveCustomKeywords() {
    const platform = document.getElementById('customKeywordPlatform').value;
    const risk = document.getElementById('customKeywordRisk').value;
    const input = document.getElementById('customKeywordInput').value;
    const words = input.split('\n').map(w => w.trim()).filter(w => w);

    if (!words.length) {
        addLog('⚠️ 请输入违禁词', 'warning');
        return;
    }

    try {
        await fetch('/api/keywords/custom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ words: { [platform]: { [risk]: words } } }),
        });
        document.getElementById('customKeywordInput').value = '';
        addLog(`✅ 已保存 ${words.length} 个自定义违禁词`, 'success');
        loadKeywordLibraries();
    } catch (e) {
        addLog(`❌ 保存失败: ${e.message}`, 'error');
    }
}

/* ==================== 审核时自动检测违禁词 ==================== */
async function autoCheckBeforeReview(task) {
    if (!document.getElementById('checkKeywords')?.checked) return;

    const platforms = Object.keys(task.articles || {});
    for (const platform of platforms) {
        const article = task.articles[platform];
        if (!article?.content) continue;

        try {
            const res = await fetch('/api/check-keywords', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: article.title + '\n' + article.content, platforms: [platform] }),
            });
            const result = await res.json();

            if (result.risk_level === 'high') {
                addLog(`🚨 [${platform}] 高风险内容！${result.summary}`, 'error');
            } else if (result.risk_level === 'medium') {
                addLog(`⚠️ [${platform}] 检测到风险词: ${result.summary}`, 'warning');
            }
            // 把检测结果附加到 task 上
            if (!task.keyword_check) task.keyword_check = {};
            task.keyword_check[platform] = result;
        } catch (e) {}
    }
}

/* ==================== API 调用 ==================== */
async function loadConfig() {
    const res = await fetch('/api/config');
    const config = await res.json();

    const container = document.getElementById('platformStatus');
    container.innerHTML = '';
    for (const [name, info] of Object.entries(config.platforms || {})) {
        const names = { xiaohongshu: '📕', douyin: '🎵', wechat: '💚', kuaishou: '🔥', bilibili: '📺', wechat_video: '📱' };
        const cls = info.logged_in ? 'logged-in' : 'not-logged';
        container.innerHTML += `<span class="platform-badge ${cls}">${names[name] || ''} ${name.slice(0,4)}</span>`;
    }
}

async function loadSettings() {
    const res = await fetch('/api/config');
    const data = await res.json();
    window._config = data;

    // AI 配置
    const ai = data.ai || {};
    document.getElementById('aiProvider').value = ai.provider || 'openai';
    document.getElementById('aiBaseUrl').value = ai.base_url || '';
    document.getElementById('aiModel').value = ai.model || 'gpt-4o';
    document.getElementById('aiTemp').value = ai.temperature || 0.7;
    document.getElementById('aiTempVal').textContent = ai.temperature || 0.7;

    // 图片配置
    const img = data.image || {};
    document.getElementById('imgProvider').value = img.provider || 'dall-e';
    document.getElementById('imgBaseUrl').value = img.base_url || '';
    document.getElementById('imgSize').value = img.size || '1024x1024';
    document.getElementById('imgCount').value = img.count || 2;

    // 平台配置
    const pContainer = document.getElementById('platformSettings');
    pContainer.innerHTML = '';
    const names = { xiaohongshu: '📕 小红书', douyin: '🎵 抖音', wechat: '💚 公众号', kuaishou: '🔥 快手', bilibili: '📺 B站', wechat_video: '📱 视频号' };
    for (const [name, cfg] of Object.entries(data.platforms || {})) {
        const statusCls = cfg.logged_in ? 'logged-in' : 'not-logged';
        const statusText = cfg.logged_in ? '✅ 已登录' : '⚠️ 未登录';
        pContainer.innerHTML += `
            <div class="platform-config">
                <div class="platform-header">
                    <span>${names[name] || name}</span>
                    <div class="platform-header-right">
                        <span class="platform-badge ${statusCls}">${statusText}</span>
                        <button class="btn btn-sm" onclick="loginPlatform('${name}')">🔐 登录</button>
                    </div>
                </div>
            </div>
        `;
    }

    // 发布策略
    const pub = data.publish || {};
    document.getElementById('reviewBefore').checked = pub.review_before_publish !== false;
    document.getElementById('autoGenerate').checked = pub.auto_generate || false;
    document.getElementById('maxDaily').value = pub.max_daily_posts || 5;
    document.getElementById('intervalMin').value = pub.interval_minutes || 30;
    document.getElementById('retryCount').value = pub.retry_count || 2;
    document.getElementById('dedupMode').value = pub.dedup_mode || 'strict';

    // 定时任务
    renderSchedules(data.schedules || []);

    // 多账号
    renderAccounts(data.accounts || []);

    // 内容偏好
    const content = data.content || {};
    document.getElementById('contentTone').value = content.tone || 'natural';
    document.getElementById('defaultWordCount').value = content.word_count || 500;

    // 白名单/黑名单
    if (content.whitelist) {
        const wl = document.getElementById('topicWhitelist');
        wl.innerHTML = content.whitelist.map(t => `<span class="tag editable">${t} <button onclick="this.parentElement.remove()">×</button></span>`).join('');
    }
    if (content.blacklist) {
        const bl = document.getElementById('topicBlacklist');
        bl.innerHTML = content.blacklist.map(t => `<span class="tag editable">${t} <button onclick="this.parentElement.remove()">×</button></span>`).join('');
    }
}

async function saveSettings() {
    const settings = {
        ai: {
            provider: document.getElementById('aiProvider').value,
            api_key: document.getElementById('aiApiKey').value,
            base_url: document.getElementById('aiBaseUrl').value,
            model: document.getElementById('aiModel').value,
            temperature: parseFloat(document.getElementById('aiTemp').value),
        },
        image: {
            provider: document.getElementById('imgProvider').value,
            api_key: document.getElementById('imgApiKey').value,
            base_url: document.getElementById('imgBaseUrl').value,
            size: document.getElementById('imgSize').value,
            count: parseInt(document.getElementById('imgCount').value) || 2,
        },
        publish: {
            review_before_publish: document.getElementById('reviewBefore').checked,
            auto_generate: document.getElementById('autoGenerate').checked,
            max_daily_posts: parseInt(document.getElementById('maxDaily').value),
            interval_minutes: parseInt(document.getElementById('intervalMin').value),
            retry_count: parseInt(document.getElementById('retryCount').value),
            dedup_mode: document.getElementById('dedupMode').value,
        },
        schedules: window._config?.schedules || [],
        accounts: window._config?.accounts || [],
        content: {
            tone: document.getElementById('contentTone').value,
            word_count: parseInt(document.getElementById('defaultWordCount').value),
            whitelist: getTagList('topicWhitelist'),
            blacklist: getTagList('topicBlacklist'),
        },
    };

    const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
    });
    const data = await res.json();
    if (data.status === 'success') {
        addLog('✅ 设置已保存', 'success');
    } else {
        addLog('❌ 保存失败: ' + (data.error || '未知错误'), 'error');
    }
}

async function testConnection() {
    const apiKey = document.getElementById('aiApiKey').value;
    const baseUrl = document.getElementById('aiBaseUrl').value;
    const model = document.getElementById('aiModel').value;

    addLog('🔌 正在测试连接...', 'info');

    try {
        const res = await fetch('/api/test-ai', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey, base_url: baseUrl, model }),
        });
        const data = await res.json();
        if (data.ok) {
            addLog(`✅ 连接成功: ${data.message}`, 'success');
        } else {
            addLog(`❌ 连接失败: ${data.message}`, 'error');
        }
    } catch (e) {
        addLog(`❌ 测试失败: ${e.message}`, 'error');
    }
}

async function loginPlatform(platform) {
    addLog(`🔐 正在启动 ${platform} 登录...`, 'info');
    try {
        const res = await fetch(`/api/platform/${platform}/login`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'waiting') {
            addLog(`📱 请在浏览器中扫码登录 ${platform}`, 'info');
        } else if (data.status === 'success') {
            addLog(`✅ ${platform} 登录成功`, 'success');
            loadConfig();
            loadSettings();
        }
    } catch (e) {
        addLog(`❌ 登录失败: ${e.message}`, 'error');
    }
}

/* ==================== 任务管理 ==================== */
async function startTask() {
    const topic = document.getElementById('topicInput').value.trim();
    if (!topic) {
        addLog('⚠️ 请输入文章主题', 'warning');
        return;
    }

    const checkboxes = document.querySelectorAll('#page-create .platform-tag input:checked');
    const platforms = Array.from(checkboxes).map(cb => cb.value);
    const auto = document.getElementById('autoPublish').checked;

    addLog(`🚀 开始生成: ${topic}`, 'info');

    const res = await fetch('/api/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, platforms, auto }),
    });
    const data = await res.json();
    if (data.error) {
        addLog(`❌ ${data.error}`, 'error');
        return;
    }
    currentTaskId = data.task_id;
    addLog(`✅ 任务已创建: #${data.task_id}`, 'success');
    loadTasks();

    // 等待 5 秒后检查违禁词
    if (document.getElementById('checkKeywords')?.checked) {
        setTimeout(async () => {
            try {
                const res = await fetch(`/api/task/${data.task_id}`);
                const task = await res.json();
                if (task.articles && Object.keys(task.articles).length > 0) {
                    await autoCheckBeforeReview(task);
                }
            } catch (e) {}
        }, 5000);
    }
}

async function loadTasks() {
    const res = await fetch('/api/tasks');
    const tasks = await res.json();
    renderTaskList(tasks);
}

function renderTaskList(tasks) {
    const container = document.getElementById('taskList');
    if (!tasks.length) {
        container.innerHTML = '<div class="empty-state">暂无任务</div>';
        return;
    }
    const statusLabels = { generating: '生成中', reviewing: '待审核', publishing: '发布中', done: '已完成', error: '出错' };
    container.innerHTML = tasks.slice(0, 10).map(task => {
        const time = task.created_at ? new Date(task.created_at).toLocaleString() : '';
        const cls = `status-${task.status}`;
        return `
            <div class="task-item" onclick="showTaskDetail('${task.id}')">
                <div class="task-topic">${task.topic}</div>
                <div class="task-meta">
                    <span>${time}</span>
                    <span class="task-status ${cls}">${statusLabels[task.status] || task.status}</span>
                </div>
            </div>
        `;
    }).join('');
}

async function showTaskDetail(taskId) {
    const res = await fetch(`/api/task/${taskId}`);
    const task = await res.json();
    currentTaskId = taskId;
    if (task.articles && Object.keys(task.articles).length > 0) {
        showReviewModal(task);
    }
}

/* ==================== 审核弹窗 ==================== */
function showReviewModal(task) {
    const modal = document.getElementById('reviewModal');
    const body = document.getElementById('reviewBody');
    const names = { xiaohongshu: '📕 小红书', douyin: '🎵 抖音', wechat: '💚 公众号', kuaishou: '🔥 快手', bilibili: '📺 B站', wechat_video: '📱 视频号' };
    const riskColors = { safe: 'var(--success)', low: 'var(--primary)', medium: 'var(--warning)', high: 'var(--danger)' };

    body.innerHTML = '';
    for (const [platform, article] of Object.entries(task.articles)) {
        const tags = (article.tags || []).map(t => `<span class="tag">#${t}</span>`).join('');

        // 违禁词检测结果
        const kwCheck = (task.keyword_check || {})[platform];
        let kwHtml = '';
        if (kwCheck) {
            const color = riskColors[kwCheck.risk_level] || 'var(--text-muted)';
            kwHtml = `<div class="review-kw-check" style="background:rgba(0,0,0,0.2);border-radius:6px;padding:8px 12px;margin-bottom:12px;border-left:3px solid ${color}">
                <span style="font-weight:600;color:${color}">违禁词检测: ${kwCheck.summary}</span>
                ${kwCheck.suggestions.length ? '<div style="margin-top:4px;font-size:12px;color:var(--text-muted)">' + kwCheck.suggestions.slice(0, 3).join(' · ') + '</div>' : ''}
            </div>`;
        }

        body.innerHTML += `
            <div class="review-card" data-platform="${platform}">
                <h3>${names[platform] || platform}</h3>
                ${kwHtml}
                <div class="form-group">
                    <label>标题</label>
                    <input type="text" class="form-input edit-title" value="${article.title || ''}">
                </div>
                <div class="form-group">
                    <label>正文</label>
                    <textarea class="edit-content" style="min-height:120px">${article.content || ''}</textarea>
                </div>
                <div class="form-group">
                    <label>标签</label>
                    <div class="style-tags">${tags}</div>
                </div>
            </div>
        `;
    }
    modal.classList.remove('hidden');
}

function closeModal() {
    document.getElementById('reviewModal').classList.add('hidden');
}

async function approvePublish() {
    if (!currentTaskId) return;
    const edits = {};
    document.querySelectorAll('.review-card').forEach(card => {
        const platform = card.dataset.platform;
        edits[platform] = {
            title: card.querySelector('.edit-title').value,
            content: card.querySelector('.edit-content').value,
        };
    });

    const res = await fetch(`/api/task/${currentTaskId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ edits }),
    });
    const data = await res.json();
    if (data.status === 'publishing') {
        addLog('📤 审核通过，开始发布...', 'success');
        closeModal();
    }
}

/* ==================== 文章复刻 ==================== */
async function cloneArticle() {
    const url = document.getElementById('cloneUrl').value.trim();
    const resultDiv = document.getElementById('cloneResult');
    if (!url) { resultDiv.innerHTML = '<span style="color:var(--danger)">请输入文章链接</span>'; return; }

    resultDiv.innerHTML = '<div class="empty-state">⏳ 抓取分析中...</div>';
    addLog('🔗 开始抓取文章...', 'info');

    try {
        const res = await fetch('/api/clone', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        const data = await res.json();
        if (data.error) { resultDiv.innerHTML = `<span style="color:var(--danger)">${data.error}</span>`; return; }

        const a = data.article, s = data.style;
        resultDiv.innerHTML = `
            <div class="clone-result-card">
                <h4>${a.title}</h4>
                <p class="hint">${a.platform} · ${a.author || '未知作者'}</p>
                <div class="style-tags">
                    <span class="tag">标题: ${s.title_style}</span>
                    <span class="tag">语气: ${s.tone}</span>
                    <span class="tag">结构: ${s.structure}</span>
                </div>
                <p class="hint" style="margin-top:8px">${(a.content || '').substring(0, 150)}...</p>
                <button class="btn btn-primary" style="margin-top:12px" onclick="generateFromClone()">✨ 基于此风格生成</button>
            </div>
        `;
        window._clonedArticle = a;
        window._clonedStyle = s;
        addLog('✅ 文章分析完成', 'success');
    } catch (e) {
        resultDiv.innerHTML = `<span style="color:var(--danger)">抓取失败: ${e.message}</span>`;
    }
}

async function generateFromClone() {
    if (!window._clonedArticle) return;
    const platforms = Array.from(document.querySelectorAll('#page-create .platform-tag input:checked')).map(cb => cb.value);

    addLog('✨ 基于复刻风格生成中...', 'info');
    try {
        const res = await fetch('/api/clone/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ article: window._clonedArticle, style: window._clonedStyle, count: 3, platforms }),
        });
        const data = await res.json();
        if (data.results) {
            for (const [p, a] of Object.entries(data.results)) {
                addLog(`✅ [${p}] ${a.title}`, 'success');
            }
        }
    } catch (e) {
        addLog(`❌ 生成失败: ${e.message}`, 'error');
    }
}

/* ==================== 日志 ==================== */
function addLog(text, type = 'info') {
    const area = document.getElementById('logArea');
    const time = new Date().toLocaleTimeString();
    area.innerHTML += `<div class="log-item log-${type}"><span class="log-time">[${time}]</span>${text}</div>`;
    area.scrollTop = area.scrollHeight;
}
