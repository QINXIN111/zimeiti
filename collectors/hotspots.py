"""热点采集模块 - 使用 Playwright 抓取各平台热搜榜"""

import re
import time
from datetime import datetime


class HotspotCollector:
    """多平台热点采集器（Playwright 页面抓取）"""

    def collect_all(self, sources: list[str] = None) -> list[dict]:
        """采集所有来源的热点"""
        if sources is None:
            sources = ["weibo", "zhihu", "baidu"]

        all_hotspots = []
        collectors = {
            "weibo": self.collect_weibo,
            "toutiao": self.collect_toutiao,  # 替代知乎
            "baidu": self.collect_baidu,
        }

        for source in sources:
            fn = collectors.get(source)
            if fn:
                try:
                    hotspots = fn()
                    all_hotspots.extend(hotspots)
                    print(f"[热点] OK {source}: {len(hotspots)} 条")
                except Exception as e:
                    print(f"[热点] FAIL {source}: {e}")

        # 去重
        seen = set()
        unique = []
        for h in all_hotspots:
            key = h["title"][:10]
            if key not in seen and h["title"]:
                seen.add(key)
                unique.append(h)

        return unique

    def _start_browser(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=True)
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

    def _stop_browser(self):
        try:
            if hasattr(self, 'browser') and self.browser:
                self.browser.close()
            if hasattr(self, 'pw') and self.pw:
                self.pw.stop()
        except:
            pass

    def collect_weibo(self) -> list[dict]:
        """使用 Playwright 抓取微博热搜"""
        self._start_browser()
        try:
            page = self.context.new_page()
            page.goto("https://s.weibo.com/top/summary", wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)

            hotspots = []
            rows = page.locator("table tbody tr").all()
            for row in rows[:30]:
                try:
                    title_el = row.locator("td.td-02 a").first
                    if title_el.count() > 0:
                        title = title_el.inner_text().strip()
                        heat_el = row.locator("td.td-02 span").first
                        heat = heat_el.inner_text().strip() if heat_el.count() > 0 else "0"
                        if title:
                            hotspots.append({
                                "title": title,
                                "url": f"https://s.weibo.com/weibo?q={title}",
                                "source": "微博",
                                "heat": heat,
                                "category": "综合",
                                "time": datetime.now().strftime("%H:%M"),
                            })
                except:
                    continue
            return hotspots
        finally:
            self._stop_browser()

    def collect_toutiao(self) -> list[dict]:
        """使用 Playwright 抓取今日头条热榜"""
        self._start_browser()
        try:
            page = self.context.new_page()
            page.goto("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
                      wait_until="networkidle", timeout=15000)
            time.sleep(2)

            hotspots = []
            import json
            body_text = page.inner_text("body")
            data = json.loads(body_text)
            items = data.get("data", data) if isinstance(data, dict) else data
            for item in items[:30]:
                title = item.get("Title", "")
                url = item.get("Url", "")
                hot_value = item.get("HotValue", 0)
                label = item.get("Label", "综合")
                if title:
                    hotspots.append({
                        "title": title,
                        "url": url if url.startswith("http") else f"https://www.toutiao.com{url}",
                        "source": "头条",
                        "heat": str(hot_value),
                        "category": label or "综合",
                        "time": datetime.now().strftime("%H:%M"),
                    })
            return hotspots
        finally:
            self._stop_browser()

    def collect_baidu(self) -> list[dict]:
        """使用 Playwright 抓取百度热搜"""
        self._start_browser()
        try:
            page = self.context.new_page()
            page.goto("https://top.baidu.com/board?tab=realtime", wait_until="networkidle", timeout=15000)
            time.sleep(2)

            hotspots = []
            items = page.locator(".category-wrap_iQLoo .content_1YWBm").all()
            for item in items[:30]:
                try:
                    title_el = item.locator(".c-single-text-ellipsis").first
                    if title_el.count() > 0:
                        title = title_el.inner_text().strip()
                        heat_el = item.locator(".hot-index_1Bl1a").first
                        heat = heat_el.inner_text().strip() if heat_el.count() > 0 else "0"
                        if title:
                            hotspots.append({
                                "title": title,
                                "url": f"https://www.baidu.com/s?wd={title}",
                                "source": "百度",
                                "heat": heat,
                                "category": "综合",
                                "time": datetime.now().strftime("%H:%M"),
                            })
                except:
                    continue
            return hotspots
        finally:
            self._stop_browser()


def format_hotspots_for_display(hotspots: list[dict], limit: int = 20) -> str:
    lines = []
    for i, h in enumerate(hotspots[:limit], 1):
        lines.append(f"{i}. {h['title']} [{h['source']}] 🔥{h['heat']}")
    return "\n".join(lines)
