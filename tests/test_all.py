"""自媒体助手 - 自动化测试"""
import json, os, sys, unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
import yaml

# Mock playwright
mock_pw = MagicMock()
mock_page = MagicMock()
mock_page.url = ""
mock_page.locator.return_value.count.return_value = 0
mock_browser = MagicMock()
mock_browser.new_context.return_value.new_page.return_value = mock_page
mock_pw.return_value.start.return_value.chromium.launch.return_value = mock_browser
sys.modules["playwright"] = MagicMock()
sys.modules["playwright.sync_api"] = mock_pw

class TestConfig(unittest.TestCase):
    def test_load_config(self):
        from scheduler import load_config
        config = load_config()
        self.assertIsInstance(config, dict)
        self.assertIn("ai", config)

class TestArticleGenerator(unittest.TestCase):
    def test_generate(self):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = json.dumps({
            "title": "测试标题", "content": "测试内容",
            "tags": ["测试"], "image_prompt": "test"
        })
        with patch("generators.article.OpenAI") as m:
            m.return_value.chat.completions.create.return_value = mock_resp
            from generators.article import ArticleGenerator
            config = yaml.safe_load(open(ROOT_DIR / "config" / "settings.yaml"))
            gen = ArticleGenerator(config)
            result = gen.generate("测试", "xiaohongshu")
            self.assertEqual(result["title"], "测试标题")

class TestHotspots(unittest.TestCase):
    def test_collector_init(self):
        from collectors.hotspots import HotspotCollector
        c = HotspotCollector()
        self.assertTrue(hasattr(c, 'collect_all'))
        self.assertTrue(hasattr(c, 'collect_weibo'))
        self.assertTrue(hasattr(c, 'collect_zhihu'))
        self.assertTrue(hasattr(c, 'collect_baidu'))

class TestArticleClone(unittest.TestCase):
    def test_cloner_init(self):
        from collectors.article import ArticleCloner
        c = ArticleCloner()
        self.assertTrue(hasattr(c, 'fetch_article'))
        self.assertTrue(hasattr(c, 'analyze_style'))
    def test_analyze_style(self):
        from collectors.article import ArticleCloner
        c = ArticleCloner()
        article = {"title": "5个技巧！", "content": "哈哈太好用了\n姐妹们安利\n首先1 其次2 最后3\n#推荐", "platform": "小红书"}
        style = c.analyze_style(article)
        self.assertEqual(style["title_style"], "数字式")
        self.assertIn("tone", style)

class TestFormatter(unittest.TestCase):
    def test_markdown(self):
        from utils.formatter import markdown_to_html
        html = markdown_to_html("# 标题\n\n**加粗**", "wechat")
        self.assertIn("<h1>", html)
        self.assertIn("<strong>", html)

if __name__ == "__main__":
    unittest.main(verbosity=2)
