/* ==================== 全局状态 ==================== */
let currentTaskId = null;
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

    // 更新平台状态
    const container = document.getElementById('platformStatus');
    container.innerHTML = '';
    for (const [name, info] of Object.entries(config.platforms)) {
        const names = { xiaohongshu: '📕 小红书', douyin: '🎵 抖音', wechat: '💚 公众号' };
        const cls = info.logged_in ? 'logged-in' : 'not-logged';
        const text = info.logged_in ? '已登录' : '未登录';
        container.innerHTML += `<span class="platform-badge ${cls}">${names[name] || name} · ${text}</span>`;
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
