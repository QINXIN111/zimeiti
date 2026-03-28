/* ==================== 全局状态 ==================== */
let currentTaskId = null;
let currentConfig = {};
let ws = null;

/* ==================== 初始化 ==================== */
document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    loadTasks();
    connectWebSocket();
});

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
            case 'config_updated':
                loadConfig();
                addLog('✅ 配置已更新', 'success');
                break;
        }
    };

    ws.onclose = () => {
        setTimeout(connectWebSocket, 3000);
    };
}

/* ==================== API 调用 ==================== */
async function loadConfig() {
    const res = await fetch('/api/config');
    const config = await res.json();
    currentConfig = config;

    // 更新平台状态（顶部）
    const container = document.getElementById('platformStatus');
    container.innerHTML = '';
    for (const [name, info] of Object.entries(config.platforms)) {
        const names = { xiaohongshu: '📕 小红书', douyin: '🎵 抖音', wechat: '💚 公众号' };
        const cls = info.logged_in ? 'logged-in' : 'not-logged';
        const text = info.logged_in ? '已登录' : '未登录';
        container.innerHTML += `<span class="platform-badge ${cls}">${names[name] || name} · ${text}</span>`;
    }

    // 更新设置面板中的平台状态
    if (config.platforms) {
        for (const [name, info] of Object.entries(config.platforms)) {
            const statusEl = document.getElementById(`platform-${name}-status`);
            if (statusEl) {
                statusEl.textContent = info.logged_in ? '✅ 已登录' : '❌ 未登录';
                statusEl.className = `platform-login-status ${info.logged_in ? 'logged' : 'not-logged'}`;
            }
        }
    }

    // 填充 AI 配置
    if (config.ai) {
        document.getElementById('aiProvider').value = config.ai.provider || 'openai';
        document.getElementById('aiApiKey').value = config.ai.api_key || '';
        document.getElementById('aiBaseUrl').value = config.ai.base_url || '';
        document.getElementById('aiModel').value = config.ai.model || '';
        document.getElementById('aiTemperature').value = config.ai.temperature || 0.7;
    }

    // 填充发布策略
    if (config.publish) {
        document.getElementById('reviewBeforePublish').checked = config.publish.review_before_publish !== false;
        document.getElementById('maxDailyPosts').value = config.publish.max_daily_posts || 3;
        document.getElementById('intervalMinutes').value = config.publish.interval_minutes || 60;
    }
}

async function loadTasks() {
    const res = await fetch('/api/tasks');
    const tasks = await res.json();
    renderTaskList(tasks);
}

async function startTask() {
    const topic = document.getElementById('topicInput').value.trim();
    if (!topic) {
        addLog('⚠️ 请输入文章主题', 'warning');
        return;
    }

    const checkboxes = document.querySelectorAll('.platform-tag input:checked');
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
}

async function approveTask(taskId, edits) {
    const res = await fetch(`/api/task/${taskId}/approve`, {
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

/* ==================== 任务更新处理 ==================== */
function handleTaskUpdate(task) {
    // 添加日志
    const statusTexts = {
        generating: '✍️ 正在生成内容...',
        reviewing: '👀 内容待审核',
        publishing: '📤 正在发布...',
        done: '✅ 全部完成！',
        error: `❌ 出错: ${task.error || '未知错误'}`,
    };
    if (statusTexts[task.status]) {
        addLog(statusTexts[task.status], task.status === 'error' ? 'error' : 'info');
    }

    // 更新任务列表
    loadTasks();

    // 如果是审核状态，弹出审核窗口
    if (task.status === 'reviewing' && task.articles) {
        showReviewModal(task);
    }
}

/* ==================== 审核弹窗 ==================== */
function showReviewModal(task) {
    const modal = document.getElementById('reviewModal');
    const body = document.getElementById('reviewBody');
    const platformNames = { xiaohongshu: '📕 小红书', douyin: '🎵 抖音', wechat: '💚 公众号' };

    body.innerHTML = '';
    for (const [platform, article] of Object.entries(task.articles)) {
        const tags = (article.tags || []).map(t => `<span class="review-tag">#${t}</span>`).join('');

        body.innerHTML += `
            <div class="review-card" data-platform="${platform}">
                <h3>${platformNames[platform] || platform}</h3>
                <div class="review-field">
                    <label>标题</label>
                    <input type="text" class="edit-title" value="${escapeHtml(article.title || '')}">
                </div>
                <div class="review-field">
                    <label>正文</label>
                    <textarea class="edit-content">${escapeHtml(article.content || '')}</textarea>
                </div>
                <div class="review-field">
                    <label>标签</label>
                    <div class="review-tags">${tags}</div>
                </div>
                ${task.images && task.images[platform] ? `<div class="review-field"><label>配图</label><img src="${task.images[platform]}" style="max-width:200px;border-radius:8px;margin-top:8px;"></div>` : ''}
            </div>
        `;
    }

    modal.classList.remove('hidden');
    currentTaskId = task.id;
}

function closeModal() {
    document.getElementById('reviewModal').classList.add('hidden');
}

function approvePublish() {
    if (!currentTaskId) return;

    // 收集编辑修改
    const edits = {};
    document.querySelectorAll('.review-card').forEach(card => {
        const platform = card.dataset.platform;
        edits[platform] = {
            title: card.querySelector('.edit-title').value,
            content: card.querySelector('.edit-content').value,
        };
    });

    approveTask(currentTaskId, edits);
}

/* ==================== 日志 ==================== */
function addLog(text, type = 'info') {
    const area = document.getElementById('logArea');
    const time = new Date().toLocaleTimeString();
    area.innerHTML += `<div class="log-item log-${type}"><span class="log-time">[${time}]</span>${escapeHtml(text)}</div>`;
    area.scrollTop = area.scrollHeight;
}

/* ==================== 任务列表渲染 ==================== */
function renderTaskList(tasks) {
    const container = document.getElementById('taskList');
    if (!tasks.length) {
        container.innerHTML = '<div class="empty-state">暂无任务</div>';
        return;
    }

    const statusLabels = {
        generating: '生成中',
        reviewing: '待审核',
        publishing: '发布中',
        done: '已完成',
        error: '出错',
        cancelled: '已取消',
    };

    container.innerHTML = tasks.map(task => {
        const time = task.created_at ? new Date(task.created_at).toLocaleString() : '';
        const statusCls = `status-${task.status}`;
        return `
            <div class="task-item ${task.id === currentTaskId ? 'active' : ''}"
                 onclick="showTaskDetail('${task.id}')">
                <div class="task-topic">${escapeHtml(task.topic)}</div>
                <div class="task-meta">
                    <span>${time}</span>
                    <span class="task-status ${statusCls}">${statusLabels[task.status] || task.status}</span>
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
        if (task.status === 'reviewing') {
            showReviewModal(task);
        } else {
            showReviewModal(task);
        }
    } else {
        addLog(`任务 #${taskId}: ${task.topic}`, 'info');
    }
}

/* ==================== 工具函数 ==================== */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/* ==================== 设置面板 ==================== */
function openSettings() {
    document.getElementById('settingsModal').classList.remove('hidden');
    loadConfig();
}

function closeSettings() {
    document.getElementById('settingsModal').classList.add('hidden');
}

function switchTab(tabName) {
    // 切换标签按钮样式
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // 切换内容显示
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabName}`);
    });
}

async function loginPlatform(platform) {
    addLog(`🔐 正在启动浏览器登录 ${platform}...`, 'info');

    const res = await fetch(`/api/platform/${platform}/login`, {
        method: 'POST',
    });

    const data = await res.json();
    if (data.error) {
        addLog(`❌ ${data.error}`, 'error');
        return;
    }

    addLog(data.message, 'success');

    // 3秒后刷新平台状态
    setTimeout(() => {
        loadConfig();
    }, 3000);
}

async function saveSettings() {
    const config = {
        ai: {
            provider: document.getElementById('aiProvider').value,
            api_key: document.getElementById('aiApiKey').value,
            base_url: document.getElementById('aiBaseUrl').value,
            model: document.getElementById('aiModel').value,
            temperature: parseFloat(document.getElementById('aiTemperature').value),
        },
        publish: {
            review_before_publish: document.getElementById('reviewBeforePublish').checked,
            max_daily_posts: parseInt(document.getElementById('maxDailyPosts').value),
            interval_minutes: parseInt(document.getElementById('intervalMinutes').value),
        },
    };

    addLog('💾 正在保存配置...', 'info');

    const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
    });

    const data = await res.json();
    if (data.error) {
        addLog(`❌ ${data.error}`, 'error');
        return;
    }

    addLog('✅ 配置保存成功', 'success');
    closeSettings();
}

/* ==================== 热点采集 ==================== */
async function loadHotspots() {
    const container = document.getElementById('hotspotList');
    container.innerHTML = '<div class="empty-state">⏳ 加载中...</div>';

    try {
        const res = await fetch('/api/hotspots');
        const data = await res.json();
        const hotspots = data.hotspots || [];

        if (hotspots.length === 0) {
            container.innerHTML = '<div class="empty-state">暂无热点数据</div>';
            return;
        }

        const categoryEmojis = {
            '娱乐': '🎬', '社会': '📰', '科技': '💻', '财经': '💰',
            '体育': '⚽', '游戏': '🎮', '汽车': '🚗', '美食': '🍜',
            '旅游': '✈️', '综合': '📌'
        };

        container.innerHTML = hotspots.slice(0, 15).map((h, i) => `
            <div class="hotspot-item" onclick="useHotspot('${h.title.replace(/'/g, "\\'")}')">
                <span class="hotspot-rank">${i + 1}</span>
                <div class="hotspot-info">
                    <span class="hotspot-title">${h.title}</span>
                    <span class="hotspot-meta">${categoryEmojis[h.category] || '📌'} ${h.source} · 🔥${h.heat}</span>
                </div>
            </div>
        `).join('');

        addLog(`🔥 加载 ${hotspots.length} 条热点`, 'success');
    } catch (e) {
        container.innerHTML = '<div class="empty-state">加载失败</div>';
        addLog(`❌ 热点加载失败: ${e.message}`, 'error');
    }
}

function useHotspot(title) {
    document.getElementById('topicInput').value = title;
    addLog(`📌 已填入热点: ${title}`, 'info');
    document.getElementById('topicInput').scrollIntoView({ behavior: 'smooth' });
}

/* ==================== 文章复刻 ==================== */
async function cloneArticle() {
    const url = document.getElementById('cloneUrl').value.trim();
    const resultDiv = document.getElementById('cloneResult');

    if (!url) {
        resultDiv.innerHTML = '<span class="log-error">请输入文章链接</span>';
        return;
    }

    resultDiv.innerHTML = '<div class="empty-state">⏳ 抓取分析中...</div>';
    addLog('🔗 开始抓取文章...', 'info');

    try {
        const res = await fetch('/api/clone', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        const data = await res.json();

        if (data.error) {
            resultDiv.innerHTML = `<span class="log-error">${data.error}</span>`;
            return;
        }

        const article = data.article;
        const style = data.style;

        resultDiv.innerHTML = `
            <div class="clone-result-card">
                <h4>${article.title}</h4>
                <p class="hint">${article.platform} · ${article.author || '未知作者'}</p>
                <div class="style-tags">
                    <span class="tag">标题: ${style.title_style}</span>
                    <span class="tag">语气: ${style.tone}</span>
                    <span class="tag">结构: ${style.structure}</span>
                    ${style.has_emoji ? '<span class="tag">含Emoji</span>' : ''}
                    ${style.has_hashtags ? '<span class="tag">含标签</span>' : ''}
                </div>
                <p class="hint" style="margin-top: 8px;">${article.content.substring(0, 200)}...</p>
                <button class="btn btn-primary" style="margin-top: 12px;" onclick="generateFromClone()">
                    ✨ 基于此风格生成新内容
                </button>
            </div>
        `;

        // 存储复刻数据供后续使用
        window._clonedArticle = article;
        window._clonedStyle = style;

        addLog('✅ 文章分析完成', 'success');
    } catch (e) {
        resultDiv.innerHTML = `<span class="log-error">抓取失败: ${e.message}</span>`;
        addLog(`❌ 抓取失败: ${e.message}`, 'error');
    }
}

async function generateFromClone() {
    if (!window._clonedArticle) return;

    const platforms = [];
    document.querySelectorAll('.platform-tag input:checked').forEach(cb => {
        platforms.push(cb.value);
    });

    addLog('✨ 基于复刻风格生成中...', 'info');

    try {
        const res = await fetch('/api/clone/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                article: window._clonedArticle,
                style: window._clonedStyle,
                count: 3,
                platforms,
            }),
        });
        const data = await res.json();

        if (data.results) {
            for (const [platform, article] of Object.entries(data.results)) {
                addLog(`✅ [${platform}] ${article.title}`, 'success');
            }
            // 填入第一个平台的内容到主题框
            const firstPlatform = platforms[0];
            if (data.results[firstPlatform]) {
                document.getElementById('topicInput').value = data.results[firstPlatform].title;
            }
        }
    } catch (e) {
        addLog(`❌ 生成失败: ${e.message}`, 'error');
    }
}
