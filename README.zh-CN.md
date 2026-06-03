# Mr.K Cover Studio

**给 AI、商业判断、认知和一线观察类抖音账号使用的固定视觉封面系统。**

[English](./README.en.md) | [默认 README](./README.md) | [线上站点](https://dna.superk.ai)

Mr.K Cover Studio 不是通用海报工具。它服务的是一种更具体的需求：把一个内容账号的视觉 DNA 固定下来，让每条作品、每个合集、每张主页背景都像从同一套系统里生产出来。

你可以丢一段抖音分享文案、一条作品链接、一张截图，或者一句自然语言主题。系统会提炼标题、栏目、摘要和背景方向，再用固定的 Mr.K 视觉模板生成封面。

## 两种交付形态

| 形态 | 适合场景 | 命令 |
| --- | --- | --- |
| Agent Skill | 直接把抖音链接发给 Agent，由 Agent 追问几个关键问题并生成封面方案 | `scripts/install_agent_skill.sh` |
| Local Web Studio | 本地打开可视化页面，调图、保存素材、导出 PNG | `scripts/run_local_studio.sh` |

## 为什么要做

很多内容账号的问题不是单条内容差，而是主页没有被经营过。

封面各做各的，标题层级不稳定，背景图风格乱，合集和单条作品没有统一识别。用户刷到主页时，很难马上知道这个账号到底擅长什么、值得关注什么。

Mr.K Cover Studio 要解决的是这件事：把内容判断变成视觉资产。

## 适用场景

### 爆款复盘

给播放量过万的历史作品重新生成统一封面，让主页从散乱素材变成内容资产库。

### 热点追踪

模型、公司、人物、商业事件出现后，快速把热点变成判断型标题和对应背景。

### 个人 IP 视觉固定

账号名、微信 ID、头像印章、K 字标、栏目色和标题层级都固定下来，长期沉淀辨识度。

### Onboarding 初始化

第一次进入页面时先选择 Agent / Web 使用方式，再选择常用模板，最后确认栏目。默认栏目保留，同时支持自定义栏目名、英文名、副文案和栏目色。

### 快速模板

内置 AI 热点拆解、强者金句、一线观察、系列合集、主页背景和自定义栏目入口，适合快速开始一张封面，而不是从空白字段填起。

### 本地素材管理

生成过的封面可以保存到素材库。没有 KV 时走本地存储，配置 KV 后可以走云端。

## 品牌 DNA

- 账号名：`MR.K 在路上`
- 抖音 ID：`KevPH2026`
- 微信 ID：`Kevph2026`
- 域名：`dna.superk.ai`
- 口号：`少和人对话，多和AI对话`

固定栏目：

- `AI下半场`：模型、Agent、商业重构
- `强者恒强`：判断力、筹码、个体系统
- `在路上`：出差、客户、一线观察

## 工作流

1. 粘贴抖音分享文案、短链接、截图或主题。
2. DeepSeek 提炼内容角度，生成标题、栏目、摘要和背景方向。
3. Image 生成贴合文案的真实/编辑感背景。
4. 固定模板叠加头像、K 字标、栏目标签、标题和编号。
5. 保存到素材库，或导出 PNG。

## 输出规格

- 单条作品封面：`1080x1920`
- 合集封面：`1080x1080`
- 主页背景：`1920x640`
- 素材库：默认本地保存，生产环境可接 KV

## 本地启动

```bash
scripts/run_local_studio.sh
```

或直接运行：

```bash
python3 cover_studio_server.py
```

打开：

```text
http://127.0.0.1:8765/mrk-cover-studio.html
```

启用真实 AI 生图：

```bash
OPENAI_API_KEY=sk-... python3 cover_studio_server.py
```

## 安装到 Agent

```bash
scripts/install_agent_skill.sh
```

安装后可用：

```text
$mrk-douyin-cover 这个抖音链接帮我生成封面：https://v.douyin.com/...
```

Skill 会默认使用 Mr.K 的固定视觉规则，只追问缺失的关键变量，例如标题、分类、背景方向和编号。

## 部署

Vercel 提供静态页面和 Python Serverless API：

```text
/api/cover-agent
/api/generate-image
/api/auth
/api/assets
```

生产环境必需变量：

```text
DEEPSEEK_API_KEY
OPENAI_API_KEY
KV_REST_API_URL
KV_REST_API_TOKEN
```

可选变量：

```text
DEEPSEEK_MODEL=deepseek-chat
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_QUALITY=medium
OPENAI_IMAGE_INPUT_FIDELITY=high
ACCOUNT_KV_PREFIX=mrkcover
```

没有配置 KV 时，浏览器会自动回退到本地登录和本地素材库。
