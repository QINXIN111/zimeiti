"""违禁词检测模块 - 发布前扫描内容风险"""

import re
import json
import os
from pathlib import Path

# 平台违禁词库（可扩展）
PLATFORM_KEYWORDS = {
    "xiaohongshu": {
        "high_risk": [
            "加微信", "加V", "私聊", "私信我", "联系方式", "vx", "vx号",
            "免费领取", "限时免费", "零元", "0元", "白嫖",
            "最便宜", "最低价", "全网最低", "绝对", "第一",
            "月入过万", "日赚", "躺赚", "躺平", "暴富",
            "代购", "刷单", "返利", "佣金", "代理",
            "原单", "高仿", "A货", "复刻", "莆田",
        ],
        "medium_risk": [
            "淘宝", "拼多多", "京东", "闲鱼", "闲鱼",
            "红包", "抽奖", "福利", "薅羊毛",
            "引流", "涨粉", "爆款", "赚钱", "变现",
            "推荐码", "邀请码", "口令", "暗号",
        ],
        "spam_patterns": [
            r"(\d)\1{3,}",  # 连续相同数字
            r"[!！]{3,}",   # 连续感叹号
            r"[?？]{3,}",   # 连续问号
        ],
    },
    "douyin": {
        "high_risk": [
            "关注我", "点个关注", "双击", "点赞关注",
            "加微信", "私信", "私聊", "联系方式",
            "免费", "限时", "限量", "抢购",
            "最", "第一", "绝对", "保证", "包治",
            "刷量", "刷粉", "刷赞", "互粉", "互关",
        ],
        "medium_risk": [
            "链接", "评论区", "点击下方", "主页", "后台",
            "同款", "爆款", "推荐", "分享",
        ],
        "spam_patterns": [
            r"[！!]{3,}",
            r"关注.{0,5}[！!]{2,}",
        ],
    },
    "wechat": {
        "high_risk": [
            "关注公众号", "扫码关注", "转发朋友圈",
            "加我微信", "私聊", "微信红包",
            "诱导分享", "诱导关注", "转发集赞",
            "敏感词", "政治", "涉政",
        ],
        "medium_risk": [
            "外部链接", "外链", "跳转",
            "二维码", "小程序码",
        ],
        "spam_patterns": [
            r"[ \t]{10,}",  # 大量空白字符
        ],
    },
    "common": {
        "high_risk": [
            "色情", "赌博", "毒品", "枪支", "爆炸",
            "诈骗", "洗钱", "非法", "违法", "犯罪",
            "色情", "裸照", "不雅",
        ],
        "medium_risk": [
            "破解", "盗版", "破解版",
            "挂", "外挂", "作弊",
        ],
        "spam_patterns": [],
    },
}


class KeywordChecker:
    """违禁词检测器"""

    def __init__(self, custom_words: dict = None):
        """初始化，支持自定义扩展词库"""
        self.keywords = {}
        # 合并平台词库
        for platform, words in PLATFORM_KEYWORDS.items():
            self.keywords[platform] = words
        # 合并自定义词库
        if custom_words:
            for platform, words in custom_words.items():
                if platform in self.keywords:
                    for level in ["high_risk", "medium_risk", "spam_patterns"]:
                        if level in words:
                            self.keywords[platform][level] = list(
                                set(self.keywords[platform].get(level, []) + words[level])
                            )
                else:
                    self.keywords[platform] = words

    def check(self, text: str, platforms: list[str] = None) -> dict:
        """检测文本违禁词

        Returns:
            {
                "risk_level": "high" | "medium" | "low" | "safe",
                "score": int,  # 风险分 0-100
                "issues": [
                    {"word": str, "risk": str, "platforms": [str], "position": int},
                ],
                "suggestions": [str],  # 修改建议
                "summary": str,  # 摘要
            }
        """
        if platforms is None:
            platforms = list(self.keywords.keys())

        issues = []
        suggestions = set()
        score = 0

        for platform in platforms:
            p_keywords = self.keywords.get(platform, {})
            if not p_keywords:
                continue

            # 高风险词
            for word in p_keywords.get("high_risk", []):
                for match in re.finditer(re.escape(word), text):
                    issues.append({
                        "word": word,
                        "risk": "high",
                        "platforms": [platform],
                        "position": match.start(),
                    })
                    score += 20
                    suggestions.add(f"替换或删除高风险词「{word}」")

            # 中风险词
            for word in p_keywords.get("medium_risk", []):
                for match in re.finditer(re.escape(word), text):
                    issues.append({
                        "word": word,
                        "risk": "medium",
                        "platforms": [platform],
                        "position": match.start(),
                    })
                    score += 8
                    suggestions.add(f"考虑替换中风险词「{word}」")

            # 垃圾内容模式
            for pattern in p_keywords.get("spam_patterns", []):
                for match in re.finditer(pattern, text):
                    issues.append({
                        "word": match.group()[:20],
                        "risk": "spam",
                        "platforms": [platform],
                        "position": match.start(),
                    })
                    score += 12
                    suggestions.add(f"检测到垃圾内容模式「{match.group()[:10]}...」")

        score = min(score, 100)

        # 去重
        seen = set()
        unique_issues = []
        for issue in issues:
            key = f"{issue['word']}_{issue['risk']}"
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        # 风险等级
        if score >= 40:
            risk_level = "high"
        elif score >= 15:
            risk_level = "medium"
        elif score > 0:
            risk_level = "low"
        else:
            risk_level = "safe"

        # 摘要
        high_count = sum(1 for i in unique_issues if i["risk"] == "high")
        medium_count = sum(1 for i in unique_issues if i["risk"] == "medium")
        spam_count = sum(1 for i in unique_issues if i["risk"] == "spam")

        if risk_level == "safe":
            summary = "✅ 未检测到违禁词，内容安全"
        else:
            parts = []
            if high_count:
                parts.append(f"⚠️ {high_count}个高风险词")
            if medium_count:
                parts.append(f"🟡 {medium_count}个中风险词")
            if spam_count:
                parts.append(f"🚫 {spam_count}个垃圾模式")
            summary = "，".join(parts)

        return {
            "risk_level": risk_level,
            "score": score,
            "issues": unique_issues,
            "suggestions": list(suggestions),
            "summary": summary,
        }

    def highlight(self, text: str, issues: list[dict]) -> str:
        """返回带高亮标记的 HTML 文本"""
        # 按位置排序（从后往前替换，避免位置偏移）
        sorted_issues = sorted(issues, key=lambda x: x["position"], reverse=True)
        highlighted = text
        for issue in sorted_issues:
            pos = issue["position"]
            word = issue["word"]
            color = {"high": "#ef4444", "medium": "#f59e0b", "spam": "#a855f7"}.get(issue["risk"], "#666")
            highlighted = (
                highlighted[:pos]
                + f'<mark style="background:{color}20;color:{color};border-bottom:2px solid {color};padding:0 2px">{word}</mark>'
                + highlighted[pos + len(word):]
            )
        return highlighted

    def get_platform_keywords(self, platform: str) -> dict:
        """获取某个平台的违禁词列表（用于前端展示）"""
        return self.keywords.get(platform, {})


def get_replacements(word: str) -> list[str]:
    """获取违禁词的推荐替代词"""
    replacements = {
        "加微信": ["主页有联系方式", "详见个人简介", "欢迎私信"],
        "免费": ["限时体验", "试用", "0门槛"],
        "最便宜": ["性价比高", "价格实惠", "超值"],
        "绝对": ["基本", "通常", "大概率"],
        "第一": ["领先", "主流", "热门"],
        "月入过万": ["收入可观", "副业增收", "额外收入"],
        "关注我": ["欢迎关注", "如果觉得有用可以关注一下"],
        "点赞关注": ["觉得有用可以点个赞"],
    }
    return replacements.get(word, ["换成更温和的表达"])
