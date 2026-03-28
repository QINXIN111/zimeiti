# 🚀 自媒体多平台同步发布助手

AI 驱动的自媒体内容生成 + 多平台一键分发工具，支持**小红书、抖音、公众号**。

## ✨ 功能

- 🤖 **AI 写文章** — 根据主题自动生成各平台风格的文案
- 🎨 **AI 生成配图** — 自动为每篇文章生成配图
- 📱 **多平台同步发布** — 一键分发到小红书、抖音、公众号
- 👀 **人工审核** — 发布前预览确认，避免翻车
- 🍪 **登录态持久化** — 一次扫码，后续免登录

## 📦 安装

```bash
git clone git@github.com:QINXIN111/zimeiti.git
cd zimeiti
pip install -r requirements.txt
playwright install chromium
```

## ⚙️ 配置

```bash
cp config/settings.yaml.example config/settings.yaml
# 编辑 config/settings.yaml，填入 API Key 等配置
```

## 🎯 使用

```bash
# 全平台发布
python main.py "今天分享一个Python小技巧"

# 指定平台
python main.py "AI绘画教程" -p xiaohongshu douyin

# 跳过审核直接发布
python main.py "热点新闻点评" --auto
```

## 🖥️ Web 可视化界面

```bash
python -m web.app
# 浏览器打开 http://localhost:8888
```

功能：
- 📝 输入主题，一键生成多平台内容
- 👀 审核编辑，发布前可修改标题/正文
- 📊 任务历史，查看每次发布记录
- 🔌 实时日志，WebSocket 实时反馈执行状态
- 🍪 平台登录状态一目了然

## 📁 项目结构

```
├── main.py              # 入口文件
├── scheduler.py         # 调度器（串联生成+发布）
├── generators/          # AI 生成模块
│   ├── article.py       # 文章生成
│   └── image.py         # 配图生成
├── publishers/          # 平台发布模块
│   ├── base.py          # 发布器基类
│   ├── xiaohongshu.py   # 小红书
│   ├── douyin.py        # 抖音
│   └── wechat.py        # 公众号
├── config/              # 配置文件
│   └── settings.yaml.example
├── templates/           # Prompt 模板
│   ├── article_prompt.txt
│   └── image_prompt.txt
└── output/              # 生成内容输出
    ├── images/
    └── drafts/
```

## ⚠️ 注意事项

- 本工具基于 Playwright 浏览器自动化，页面结构变化可能导致发布失败
- 建议先用 `--auto` 以外的模式测试，确认无误后再自动发布
- 遵守各平台使用规范，避免频繁发布触发风控
- Cookies 文件包含登录态，请妥善保管
