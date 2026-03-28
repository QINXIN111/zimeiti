"""热点采集模块 - 抓取各平台热搜榜"""

import re
import json
import time
import requests
from datetime import datetime


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class HotspotCollector:
    """多平台热点采集器"""

    def collect_all(self, sources: list[str] = None) -> list[dict]:
        """采集所有来源的热点

        Returns:
            [{"title": str, "url": str, "source": str, "heat": str, "category": str, "time": str}]
        """
        if sources is None:
            sources = ["weibo", "zhihu", "baidu"]

        all_hotspots = []
        collectors = {
            "weibo": self.collect_weibo,
            "zhihu": self.collect_zhihu,
            "baidu": self.collect_baidu,
        }

        for source in sources:
            fn = collectors.get(source)
            if fn:
                try:
                    hotspots = fn()
                    all_hotspots.extend(hotspots)
                    print(f"[热点] ✅ {source}: {len(hotspots)} 条")
                except Exception as e:
                    print(f"[热点] ❌ {source}: {e}")

        # 去重 + 排序
        seen = set()
        unique = []
        for h in all_hotspots:
            key = h["title"][:10]
            if key not in seen:
                seen.add(key)
                unique.append(h)

        return unique

    def collect_weibo(self) -> list[dict]:
        """采集微博热搜"""
        url = "https://weibo.com/ajax/side/hotSearch"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()

        hotspots = []
        if "data" in data and "realtime" in data["data"]:
            for item in data["data"]["realtime"][:30]:
                title = item.get("word", "")
                hot_num = item.get("num", 0)
                category = item.get("category", "")
                hotspots.append({
                    "title": title,
                    "url": f"https://s.weibo.com/weibo?q={title}",
                    "source": "微博",
                    "heat": f"{hot_num // 10000}万" if hot_num > 10000 else str(hot_num),
                    "category": self._categorize_weibo(category),
                    "time": datetime.now().strftime("%H:%M"),
                })
        return hotspots

    def _categorize_weibo(self, cat_code: str) -> str:
        mapping = {
            "ent": "娱乐", "society": "社会", "tech": "科技",
            "finance": "财经", "sport": "体育", "game": "游戏",
            "car": "汽车", "food": "美食", "travel": "旅游",
        }
        return mapping.get(cat_code, "综合")

    def collect_zhihu(self) -> list[dict]:
        """采集知乎热榜"""
        url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=30"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()

        hotspots = []
        for item in data.get("data", [])[:30]:
            target = item.get("target", {})
            title = target.get("title", "")
            excerpt = target.get("excerpt", "")
            heat = item.get("detail_text", "")
            hotspots.append({
                "title": title,
                "url": f"https://www.zhihu.com/question/{target.get('id', '')}",
                "source": "知乎",
                "heat": heat,
                "category": "综合",
                "time": datetime.now().strftime("%H:%M"),
            })
        return hotspots

    def collect_baidu(self) -> list[dict]:
        """采集百度热搜"""
        url = "https://top.baidu.com/api/board?platform=wise&tab=realtime"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()

        hotspots = []
        for item in data.get("data", {}).get("cards", [{}])[0].get("content", [])[:30]:
            word = item.get("word", "")
            desc = item.get("desc", "")
            hot_value = item.get("hotScore", 0)
            hotspots.append({
                "title": word,
                "url": f"https://www.baidu.com/s?wd={word}",
                "source": "百度",
                "heat": f"{hot_value // 10000}万" if hot_value > 10000 else str(hot_value),
                "category": "综合",
                "time": datetime.now().strftime("%H:%M"),
            })
        return hotspots


def format_hotspots_for_display(hotspots: list[dict], limit: int = 20) -> str:
    """格式化热点列表用于展示"""
    lines = []
    for i, h in enumerate(hotspots[:limit], 1):
        emoji = _category_emoji(h.get("category", ""))
        lines.append(f"{i}. {emoji} {h['title']} [{h['source']}] 🔥{h['heat']}")
    return "\n".join(lines)


def _category_emoji(category: str) -> str:
    mapping = {
        "娱乐": "🎬", "社会": "📰", "科技": "💻",
        "财经": "💰", "体育": "⚽", "游戏": "🎮",
        "汽车": "🚗", "美食": "🍜", "旅游": "✈️",
    }
    return mapping.get(category, "📌")
