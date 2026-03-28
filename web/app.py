"""自媒体助手 - 可视化 Web 管理平台"""

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
    }


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
    import asyncio
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

    import asyncio
    asyncio.create_task(publish_task(task_id))

    return {"status": "publishing"}


@app.post("/api/task/{task_id}/cancel")
async def api_task_cancel(task_id: str):
    """取消任务"""
    if task_id in tasks:
        tasks[task_id]["status"] = "cancelled"
        await broadcast({"type": "task_update", "task": tasks[task_id]})
    return {"status": "cancelled"}


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


# ==================== 任务执行 ====================

async def run_task(task_id: str, topic: str, platforms: list, auto: bool):
    """执行 AI 生成任务"""
    task = tasks[task_id]
    config = load_config()

    # 如果未指定平台，使用所有启用的平台
    if not platforms:
        platforms = [name for name, cfg in config.get("platforms", {}).items() if cfg.get("enabled", True)]
        task["platforms"] = platforms

    try:
        # 导入生成模块
        import sys
        sys.path.insert(0, str(ROOT_DIR))
        from generators.article import ArticleGenerator
        from generators.image import ImageGenerator

        # 生成文章
        await broadcast({"type": "status", "task_id": task_id, "message": "✍️ 正在生成文章..."})
        article_gen = ArticleGenerator(config)
        articles = article_gen.generate_batch(topic, platforms)
        task["articles"] = articles

        await broadcast({"type": "task_update", "task": task})

        # 生成配图
        await broadcast({"type": "status", "task_id": task_id, "message": "🎨 正在生成配图..."})
        img_gen = ImageGenerator(config)
        for platform in platforms:
            article = articles.get(platform, {})
            img_prompt = article.get("image_prompt", topic)
            try:
                img_path = img_gen.generate(img_prompt, f"{platform}_{int(time.time())}.png")
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

        publisher_map = {
            "xiaohongshu": XiaohongshuPublisher,
            "douyin": DouyinPublisher,
            "wechat": WechatPublisher,
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
            try:
                success = publisher.publish(
                    title=article.get("title", ""),
                    content=article.get("content", ""),
                    image_path=task["images"].get(platform),
                    tags=article.get("tags"),
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
