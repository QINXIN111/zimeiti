"""文章爬取模块 - 从各平台抓取文章内容用于复刻"""

import re
import time
import requests
from urllib.parse import urlparse


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class ArticleCloner:
    """文章复刻器 - 抓取 + 分析 + 复刻"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.pw = None
        self.browser = None

    def fetch_article(self, url: str) -> dict:
        """根据 URL 自动识别平台并抓取文章

        Returns:
            {
                "title": str,
                "content": str,
                "images": list[str],
                "author": str,
                "platform": str,
                "url": str,
            }
        """
        domain = urlparse(url).netloc

        if "xiaohongshu" in domain or "xhslink" in domain:
            return self._fetch_xiaohongshu(url)
        elif "mp.weixin.qq" in domain:
            return self._fetch_wechat(url)
        elif "douyin" in domain:
            return self._fetch_douyin(url)
        elif "b23.tv" in domain or "bilibili" in domain:
            return self._fetch_bilibili(url)
        else:
            return self._fetch_generic(url)

    def _fetch_xiaohongshu(self, url: str) -> dict:
        """抓取小红书笔记"""
        # 使用 Playwright 抓取（需要登录态）
        return self._fetch_with_playwright(url, "小红书")

    def _fetch_wechat(self, url: str) -> dict:
        """抓取微信公众号文章"""
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        html = resp.text

        # 提取标题
        title_match = re.search(r'var msg_title = "(.*?)"', html) or re.search(r'<h1[^>]*>(.*?)</h1>', html)
        title = title_match.group(1) if title_match else "未知标题"

        # 提取正文
        content_match = re.search(r'id="js_content"[^>]*>(.*?)</div>', html, re.DOTALL)
        content = content_match.group(1) if content_match else ""

        # 清理 HTML 标签
        content = re.sub(r'<[^>]+>', '\n', content)
        content = re.sub(r'\n{3,}', '\n\n', content).strip()

        # 提取图片
        images = re.findall(r'data-src="(https://[^"]+)"', html)

        return {
            "title": title,
            "content": content,
            "images": images[:9],
            "author": "",
            "platform": "微信公众号",
            "url": url,
        }

    def _fetch_douyin(self, url: str) -> dict:
        """抓取抖音内容"""
        return self._fetch_with_playwright(url, "抖音")

    def _fetch_bilibili(self, url: str) -> dict:
        """抓取 B 站内容"""
        return self._fetch_with_playwright(url, "B站")

    def _fetch_generic(self, url: str) -> dict:
        """通用网页抓取"""
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        html = resp.text

        title_match = re.search(r'<title[^>]*>(.*?)</title>', html)
        title = title_match.group(1) if title_match else "未知标题"

        # 尝试提取正文段落
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        content = "\n".join(re.sub(r'<[^>]+>', '', p) for p in paragraphs if len(p) > 20)

        return {
            "title": title,
            "content": content,
            "images": [],
            "author": "",
            "platform": "网页",
            "url": url,
        }

    def _fetch_with_playwright(self, url: str, platform: str) -> dict:
        """使用 Playwright 抓取需要 JS 渲染的页面"""
        try:
            from playwright.sync_api import sync_playwright
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch(headless=True)
            context = self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=HEADERS["User-Agent"],
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # 提取标题
            title = page.title() or "未知标题"

            # 提取正文（通用选择器）
            content = ""
            for selector in [".note-content", ".content", "article", ".rich-text", "main"]:
                el = page.locator(selector).first
                if el.count() > 0:
                    content = el.inner_text()
                    break

            if not content:
                content = page.inner_text("body")[:3000]

            # 提取图片
            images = page.locator("img").evaluate_all(
                "els => els.map(e => e.src).filter(s => s && s.startsWith('http'))"
            )

            self.browser.close()
            self.pw.stop()

            return {
                "title": title,
                "content": content,
                "images": (images or [])[:9],
                "author": "",
                "platform": platform,
                "url": url,
            }
        except Exception as e:
            return {
                "title": f"[{platform}] 抓取失败",
                "content": f"抓取失败: {e}",
                "images": [],
                "author": "",
                "platform": platform,
                "url": url,
            }
        finally:
            if self.browser:
                try:
                    self.browser.close()
                except:
                    pass
            if self.pw:
                try:
                    self.pw.stop()
                except:
                    pass

    def analyze_style(self, article: dict) -> dict:
        """分析文章风格，用于复刻

        Returns:
            {
                "title_style": str,   # 标题风格（提问式/数字式/感叹式/陈述式）
                "structure": str,     # 结构（总分总/列表式/时间线/故事型）
                "tone": str,          # 语气（严肃/活泼/吐槽/专业）
                "avg_paragraph": int, # 平均段落长度
                "has_emoji": bool,    # 是否使用 emoji
                "has_hashtags": bool, # 是否使用标签
            }
        """
        content = article.get("content", "")
        title = article.get("title", "")

        # 标题风格判断
        title_style = "陈述式"
        if "?" in title or "？" in title:
            title_style = "提问式"
        elif any(c.isdigit() for c in title):
            title_style = "数字式"
        elif "!" in title or "！" in title or "！" in title:
            title_style = "感叹式"

        # 语气判断
        tone = "中性"
        lively_words = ["哈哈", "太", "绝了", "安利", "姐妹", "宝子", "yyds"]
        roast_words = ["但", "然而", "可惜", "翻车", "踩雷", "后悔"]
        pro_words = ["根据", "数据", "分析", "研究", "对比", "测评"]

        for w in lively_words:
            if w in content:
                tone = "活泼"
                break
        for w in roast_words:
            if w in content:
                tone = "吐槽"
                break
        for w in pro_words:
            if w in content:
                tone = "专业"
                break

        # 结构判断
        structure = "自由格式"
        if content.count("\n") > 5 and any(content.count(f"{i}.") > 0 for i in range(1, 10)):
            structure = "列表式"
        elif content[:50] in content[50:100]:
            structure = "总分总"
        elif "首先" in content or "其次" in content or "最后" in content:
            structure = "递进式"

        return {
            "title_style": title_style,
            "structure": structure,
            "tone": tone,
            "avg_paragraph": len(content) // max(content.count("\n"), 1),
            "has_emoji": bool(re.search(r'[\U0001F600-\U0001F64F]', content)),
            "has_hashtags": "#" in content,
        }
