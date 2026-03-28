"""自媒体助手 - 可视化 Web 管理平台"""

import asyncio
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 线程池，用于执行同步阻塞的 Playwright 操作
_executor = ThreadPoolExecutor(max_workers=3)

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
DRAFTS_DIR = ROOT_DIR / "output" / "drafts"
DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="自媒体助手", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(ROOT_DIR / "web" / "static")), name="static")
templates = Jinja2Templates(directory=str(ROOT_DIR / "web" / "templates"))

# 任务存储（简单内存版）
tasks: dict = {}
# WebSocket 连接管理
connections: list[WebSocket] = []


def load_config():
    config_path = ROOT_DIR / "config" / "settings.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def get_platforms_status(config: dict) -> dict:
    """获取各平台登录状态"""
    platforms = config.get("platforms", {})
    status = {}
    for name, cfg in platforms.items():
        cookies_file = ROOT_DIR / cfg.get("cookies_file", f"config/cookies/{name}.json")
        status[name] = {
            "enabled": cfg.get("enabled", True),
            "logged_in": cookies_file.exists(),
        }
    return status


async def broadcast(message: dict):
    """向所有 WebSocket 客户端广播消息"""
    disconnected = []
    for ws in connections:
        try:
            await ws.send_json(message)
        except:
            disconnected.append(ws)
    for ws in disconnected:
        connections.remove(ws)


# ==================== 页面路由 ====================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ==================== API 路由 ====================

@app.get("/api/config")
async def api_config():
    """获取当前配置"""
    config = load_config()
    return {
        "platforms": get_platforms_status(config),
        "publish": config.get("publish", {}),
        "ai_provider": config.get("ai", {}).get("provider", "未配置"),
        "ai": config.get("ai", {}),
        "image": config.get("image", {}),
    }


@app.post("/api/config")
async def api_config_save(request: Request):
    """保存配置到 settings.yaml"""
    body = await request.json()
    config = load_config()

    # 更新 AI 配置
    if "ai" in body:
        config.setdefault("ai", {}).update(body["ai"])

    # 更新图片配置
    if "image" in body:
        config.setdefault("image", {}).update(body["image"])

    # 更新发布策略
    if "publish" in body:
        config.setdefault("publish", {}).update(body["publish"])

    # 更新平台配置
    if "platforms" in body:
        config.setdefault("platforms", {}).update(body["platforms"])

    # 写回文件
    config_path = ROOT_DIR / "config" / "settings.yaml"
    os.makedirs(config_path.parent, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    await broadcast({"type": "config_updated", "config": {
        "platforms": get_platforms_status(config),
        "ai_provider": config.get("ai", {}).get("provider", "未配置"),
    }})

    return {"status": "success"}


@app.get("/api/tasks")
async def api_tasks():
    """获取任务列表"""
    task_list = []
    for tid, task in sorted(tasks.items(), key=lambda x: x[1].get("created_at", ""), reverse=True):
        task_list.append({
            "id": tid,
            "topic": task.get("topic", ""),
            "platforms": task.get("platforms", []),
            "status": task.get("status", "pending"),
            "results": task.get("results", {}),
            "created_at": task.get("created_at", ""),
            "articles": task.get("articles", {}),
        })
    return task_list


@app.post("/api/publish")
async def api_publish(request: Request):
    """创建发布任务"""
    body = await request.json()
    topic = body.get("topic", "").strip()
    platforms = body.get("platforms", [])
    auto = body.get("auto", False)

    if not topic:
        return JSONResponse({"error": "请输入主题"}, status_code=400)

    task_id = uuid.uuid4().hex[:8]
    tasks[task_id] = {
        "id": task_id,
        "topic": topic,
        "platforms": platforms,
        "status": "generating",
        "results": {},
        "articles": {},
        "images": {},
        "created_at": datetime.now().isoformat(),
    }

    # 异步执行任务
    asyncio.create_task(run_task(task_id, topic, platforms, auto))

    return {"task_id": task_id, "status": "started"}


@app.get("/api/task/{task_id}")
async def api_task_detail(task_id: str):
    """获取任务详情"""
    if task_id not in tasks:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return tasks[task_id]


@app.post("/api/task/{task_id}/approve")
async def api_task_approve(task_id: str, request: Request):
    """审核通过，开始发布"""
    if task_id not in tasks:
        return JSONResponse({"error": "任务不存在"}, status_code=404)

    body = await request.json()
    edits = body.get("edits", {})

    # 应用编辑修改
    task = tasks[task_id]
    if edits:
        for platform, data in edits.items():
            if platform in task["articles"]:
                task["articles"][platform].update(data)

    task["status"] = "publishing"
    await broadcast({"type": "task_update", "task": task})

    asyncio.create_task(publish_task(task_id))

    return {"status": "publishing"}


@app.post("/api/task/{task_id}/cancel")
async def api_task_cancel(task_id: str):
    """取消任务"""
    if task_id in tasks:
        tasks[task_id]["status"] = "cancelled"
        await broadcast({"type": "task_update", "task": tasks[task_id]})
    return {"status": "cancelled"}


@app.post("/api/platform/{platform}/login")
async def api_platform_login(platform: str):
    """触发平台登录流程（启动 Playwright 浏览器）"""
    import sys
    sys.path.insert(0, str(ROOT_DIR))

    platform_map = {
        "xiaohongshu": ("小红书", "https://www.xiaohongshu.com"),
        "douyin": ("抖音", "https://www.douyin.com"),
        "wechat": ("微信公众号", "https://mp.weixin.qq.com"),
    }

    if platform not in platform_map:
        return JSONResponse({"error": f"不支持的平台: {platform}"}, status_code=400)

    name, url = platform_map[platform]

    def do_login():
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=False)  # 非无头模式，让用户扫码
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        # 导航到平台
        page.goto(url)

        # 等待用户登录（最多 5 分钟）
        print(f"[{platform}] 等待用户登录...")
        time.sleep(300)  # 5 分钟超时

        # 保存 cookies
        cookies = context.cookies()
        cookies_dir = ROOT_DIR / "config" / "cookies"
        cookies_dir.mkdir(parents=True, exist_ok=True)
        cookies_file = cookies_dir / f"{platform}.json"

        with open(cookies_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        print(f"[{platform}] 登录成功，cookies 已保存")

        browser.close()
        pw.stop()

        return True

    # 在线程池中执行同步的 Playwright
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, do_login)

    return {"status": "started", "message": f"正在启动浏览器登录 {name}，请扫码..."}


@app.get("/api/drafts")
async def api_drafts():
    """获取历史草稿"""
    drafts = []
    if DRAFTS_DIR.exists():
        for d in sorted(DRAFTS_DIR.iterdir(), reverse=True):
            if d.is_dir():
                meta = {}
                for f in d.glob("*.json"):
                    with open(f, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                        meta[f.stem] = {"title": data.get("title", "")}
                drafts.append({"date": d.name, "platforms": meta})
    return drafts[:20]


# ==================== 热点采集 ====================

@app.get("/api/hotspots")
async def api_hotspots(sources: str = "weibo,baidu,toutiao"):
    """获取实时热点列表"""
    import sys
    sys.path.insert(0, str(ROOT_DIR))
    from collectors.hotspots import HotspotCollector

    collector = HotspotCollector()
    source_list = sources.split(",")
    hotspots = await asyncio.to_thread(collector.collect_all, source_list)
    return {"hotspots": hotspots[:30], "updated_at": datetime.now().isoformat()}


# ==================== 文章复刻 ====================

@app.post("/api/clone")
async def api_clone_article(request: Request):
    """抓取文章并分析风格"""
    body = await request.json()
    url = body.get("url", "").strip()

    if not url:
        return JSONResponse({"error": "请提供文章链接"}, status_code=400)

    import sys
    sys.path.insert(0, str(ROOT_DIR))
    from collectors.article import ArticleCloner

    cloner = ArticleCloner()
    article = await asyncio.to_thread(cloner.fetch_article, url)
    style = await asyncio.to_thread(cloner.analyze_style, article)

    return {
        "article": article,
        "style": style,
    }


@app.post("/api/clone/generate")
async def api_clone_generate(request: Request):
    """基于复刻的文章风格生成新内容"""
    body = await request.json()
    article = body.get("article", {})
    style = body.get("style", {})
    count = body.get("count", 3)
    platforms = body.get("platforms", ["xiaohongshu"])

    import sys
    sys.path.insert(0, str(ROOT_DIR))
    from generators.article import ArticleGenerator

    config = load_config()
    gen = ArticleGenerator(config)

    # 构建风格描述
    style_desc = f"标题风格: {style.get('title_style', '陈述式')}, 语气: {style.get('tone', '中性')}, 结构: {style.get('structure', '自由格式')}"

    # 基于原文主题生成新内容
    topic = f"参考这篇内容风格（{style_desc}），主题类似但内容不同：{article.get('title', '')}"
    results = await asyncio.to_thread(gen.generate_batch, topic, platforms)

    return {"results": results}


# ==================== 任务执行 ====================

async def run_task(task_id: str, topic: str, platforms: list, auto: bool):
    """执行 AI 生成任务"""
    task = tasks[task_id]
    config = load_config()

    # 如果未指定平台，使用所有启用的平台
    if not platforms:
        platforms = [name for name, cfg in config.get("platforms", {}).items() if cfg.get("enabled", True)]
        task["platforms"] = platforms

    loop = asyncio.get_event_loop()

    try:
        # 导入生成模块
        import sys
        sys.path.insert(0, str(ROOT_DIR))
        from generators.article import ArticleGenerator
        from generators.image import ImageGenerator

        # 生成文章（阻塞 IO，丢到线程池）
        await broadcast({"type": "status", "task_id": task_id, "message": "✍️ 正在生成文章..."})
        article_gen = ArticleGenerator(config)
        loop = asyncio.get_event_loop()
        articles = await loop.run_in_executor(
            _executor, lambda: article_gen.generate_batch(topic, platforms)
        )
        task["articles"] = articles

        await broadcast({"type": "task_update", "task": task})

        # 生成配图（阻塞 IO，丢到线程池）
        await broadcast({"type": "status", "task_id": task_id, "message": "🎨 正在生成配图..."})
        img_gen = ImageGenerator(config)
        for platform in platforms:
            article = articles.get(platform, {})
            img_prompt = article.get("image_prompt", topic)
            try:
                img_path = await loop.run_in_executor(
                    _executor,
                    lambda ip=img_prompt, pl=platform: img_gen.generate(ip, f"{pl}_{int(time.time())}.png"),
                )
                task["images"][platform] = img_path
            except Exception as e:
                task["images"][platform] = None

        task["status"] = "reviewing" if not auto else "publishing"
        await broadcast({"type": "task_update", "task": task})

        if auto:
            await publish_task(task_id)

    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)
        await broadcast({"type": "task_update", "task": task})


async def publish_task(task_id: str):
    """执行发布任务"""
    task = tasks[task_id]
    config = load_config()

    try:
        import sys
        sys.path.insert(0, str(ROOT_DIR))
        from publishers.xiaohongshu import XiaohongshuPublisher
        from publishers.douyin import DouyinPublisher
        from publishers.wechat import WechatPublisher
        from publishers.kuaishou import KuaishouPublisher
        from publishers.bilibili import BilibiliPublisher
        from publishers.wechat_video import WechatVideoPublisher

        publisher_map = {
            "xiaohongshu": XiaohongshuPublisher,
            "douyin": DouyinPublisher,
            "wechat": WechatPublisher,
            "kuaishou": KuaishouPublisher,
            "bilibili": BilibiliPublisher,
            "wechat_video": WechatVideoPublisher,
        }

        platforms = task["platforms"]
        for platform in platforms:
            await broadcast({
                "type": "status",
                "task_id": task_id,
                "message": f"📤 正在发布到 {platform}...",
            })

            publisher_cls = publisher_map.get(platform)
            if not publisher_cls:
                task["results"][platform] = {"success": False, "error": "暂不支持"}
                continue

            article = task["articles"].get(platform, {})
            publisher = publisher_cls(config)

            # 用线程池执行同步阻塞的 Playwright 操作，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            try:
                success = await loop.run_in_executor(
                    _executor,
                    lambda p=publisher, a=article, t=task, pl=platform: p.publish(
                        title=a.get("title", ""),
                        content=a.get("content", ""),
                        image_path=t["images"].get(pl),
                        tags=a.get("tags"),
                    ),
                )
                task["results"][platform] = {"success": success}
            except Exception as e:
                task["results"][platform] = {"success": False, "error": str(e)}

            await broadcast({"type": "task_update", "task": task})

            # 发布间隔
            if platform != platforms[-1]:
                interval = config.get("publish", {}).get("interval_minutes", 60)
                await broadcast({
                    "type": "status",
                    "task_id": task_id,
                    "message": f"⏳ 等待 {interval} 分钟后发布下一个平台...",
                })

        task["status"] = "done"
        await broadcast({"type": "task_update", "task": task})

    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)
        await broadcast({"type": "task_update", "task": task})


# ==================== 违禁词检测 ====================

@app.post("/api/check-keywords")
async def api_check_keywords(request: Request):
    """检测文本违禁词"""
    body = await request.json()
    text = body.get("text", "")
    platforms = body.get("platforms", None)

    if not text:
        return JSONResponse({"error": "请提供文本内容"}, status_code=400)

    import sys
    sys.path.insert(0, str(ROOT_DIR))
    from utils.keyword_checker import KeywordChecker, get_replacements

    config = load_config()
    custom_words = config.get("keywords", {}).get("custom", {})
    checker = KeywordChecker(custom_words)
    result = checker.check(text, platforms)

    # 添加推荐替代词
    for issue in result["issues"]:
        issue["replacements"] = get_replacements(issue["word"])

    return result


@app.get("/api/keywords")
async def api_get_keywords(platform: str = None):
    """获取违禁词列表"""
    import sys
    sys.path.insert(0, str(ROOT_DIR))
    from utils.keyword_checker import KeywordChecker, PLATFORM_KEYWORDS

    config = load_config()
    custom_words = config.get("keywords", {}).get("custom", {})
    checker = KeywordChecker(custom_words)

    if platform:
        return checker.get_platform_keywords(platform)
    return PLATFORM_KEYWORDS


@app.post("/api/keywords/custom")
async def api_save_custom_keywords(request: Request):
    """保存自定义违禁词"""
    body = await request.json()
    config = load_config()
    config.setdefault("keywords", {})["custom"] = body.get("words", {})

    config_path = ROOT_DIR / "config" / "settings.yaml"
    os.makedirs(config_path.parent, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    return {"status": "success"}


# ==================== WebSocket ====================

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connections.append(ws)
    try:
        while True:
            data = await ws.receive_text()
    except WebSocketDisconnect:
        connections.remove(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)
