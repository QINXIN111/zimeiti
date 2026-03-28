# 自媒体多平台发布助手

基于 AI 的自媒体多平台发布工具,支持小红书、抖音、微信公众号一键发布。

## 功能特性

- ✨ **AI 文章生成**: 支持多种 AI 模型(DeepSeek、Qwen 等),一键生成高质量文章
- 🎨 **智能配图**: 可选 AI 生成配图,图文并茂
- 📝 **智能排版**: Markdown 自动转换为富文本,适配各平台格式
- 🚀 **多平台发布**: 一键同步发布到小红书/抖音/微信公众号
- 🖥️ **Web 管理面板**: 可视化配置管理,扫码登录
- ⚙️ **灵活配置**: 全局开关 + 任务级覆盖,精细控制每个发布任务

## 技术栈

- **后端**: Python + FastAPI
- **自动化**: Playwright (浏览器自动化)
- **前端**: 原生 HTML/JS/CSS
- **部署**: uvicorn

## 快速开始

### 环境要求

- Python 3.8+
- Node.js (用于前端依赖,可选)

### 安装依赖

```bash
pip install fastapi uvicorn jinja2 python-multipart playwright
playwright install chromium
```

### 配置文件

项目首次运行会自动生成 `settings.yaml`:

```yaml
# AI 配置
ai:
  provider: deepseek
  api_key: your-api-key
  base_url: https://api.deepseek.com/v1

# 平台账号(首次通过 Web 面板扫码登录)
platforms:
  xiaohongshu: {}
  douyin: {}
  wechat: {}

# 发布策略
publish:
  auto_publish: true  # 是否自动发布(不自动则先保存草稿)
  enable_image: true  # 默认是否生成配图
  enable_formatting: true  # 默认是否智能排版
```

### 启动服务

```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 打开管理面板。

## 使用说明

### 1. 配置 AI

在 Web 面板「设置」→「AI 配置」中填入你的 AI API 信息。

### 2. 登录平台

在「设置」→「平台账号」中点击各平台的「扫码登录」按钮,使用手机扫码完成登录。

### 3. 创建任务

- 输入文章主题
- 选择发布平台
- 配置高级选项(可选):
  - ☑ 生成配图
  - ☑ 自动排版
- 点击「开始生成」

### 4. 查看进度

任务列表实时显示生成和发布进度,支持查看详细日志。

## 开发说明

### 项目结构

```
zimeiti/
├── web/                    # Web 后端和前端
│   ├── app.py             # FastAPI 主应用
│   ├── templates/         # HTML 模板
│   └── static/            # 静态资源(CSS/JS)
├── generators/           # 内容生成器
│   └── article.py        # 文章生成器
├── publishers/           # 平台发布器
│   ├── base.py           # 基础发布器
│   ├── xiaohongshu.py    # 小红书
│   ├── douyin.py         # 抖音
│   └── wechat.py         # 微信公众号
├── utils/               # 工具函数
│   └── formatter.py     # Markdown→HTML 转换器
├── scheduler.py         # 任务调度器
└── settings.yaml       # 配置文件(自动生成)
```

### 添加新平台

1. 在 `publishers/` 下创建新文件,继承 `BasePublisher`
2. 实现 `publish(title, content, images, is_html)` 方法
3. 在 `web/app.py` 的 `login_platform()` 中添加登录逻辑
4. 在前端添加平台卡片和按钮

## 最近更新

### v1.1 (2026-03-28)

- ✅ 新增 Web 配置管理面板
- ✅ 支持平台扫码登录
- ✅ 新增智能配图功能开关
- ✅ 新增智能排版功能(Markdown→富文本)
- ✅ 高级选项:任务级功能覆盖
- ✅ 修复 5 个已知问题(scheduler 容错、async/sync 混用、进程泄漏等)

### v1.0

- 初始版本,支持 AI 文章生成和多平台发布

## 常见问题

**Q: 推送失败怎么办?**
A: 检查平台登录状态是否过期,重新扫码登录即可。

**Q: 如何关闭智能排版?**
A: 在「发布策略」中全局关闭,或在新建任务时高级选项中单独关闭。

**Q: 支持 AI 模型有哪些?**
A: 目前支持 DeepSeek、Qwen、通义千问等兼容 OpenAI 接口的模型。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request!
