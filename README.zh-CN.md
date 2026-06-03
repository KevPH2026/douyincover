# Mr.K Cover Studio

**给 AI、商业判断、认知和一线观察类抖音账号使用的固定视觉封面系统。**

[English](./README.en.md) | [默认 README](./README.md) | [线上站点](https://dna.superk.ai) | [GitHub](https://github.com/KevPH2026/douyincover)

Mr.K Cover Studio 不是通用海报工具。它服务的是一种更具体的需求：把一个内容账号的视觉 DNA 固定下来，让每条作品、每个合集、每张主页背景都像从同一套系统里生产出来。

你可以丢一段抖音分享文案、一条作品链接、一张截图、一段片头/片尾素材，或者一句自然语言主题。系统会提炼标题、栏目、摘要和背景方向，再用固定的 Mr.K 视觉模板生成封面或 1-2 秒动效。

## 两种交付形态

| 形态 | 适合场景 | 命令 |
| --- | --- | --- |
| Agent Skill | 直接把抖音链接发给 Agent，由 Agent 追问几个关键问题并生成封面方案 | `scripts/install_agent_skill.sh` |
| Local Web Studio | 本地打开可视化页面，调图、保存素材、导出 PNG/M4V | `scripts/run_local_studio.sh` |

## Agent 对话式接入

Agent 不是一上来就生成图，而是先把账号上下文问清楚，再进入封面生产：

完整接入指南：[下载 Skill 或直接复制提示词](./AGENT_GUIDE.md)。

1. 先问抖音 ID、主页链接或主页截图。默认 Mr.K 使用 `KevPH2026`。
2. 再问任务类型：单条封面、片头/片尾动效、解码 DNA、批量换封面、合集封面或主页背景。
3. 再判断分类：优先落在 `AI下半场`、`强者恒强`、`在路上`，不合适再开自定义栏目。
4. 再收素材：单条给链接/文案/截图；片头/片尾动效可补图片或视频素材；解码 DNA / 生成 Style 可以先只给 1 个公开抖音作品链接，系统会自动追作者主页、头像、ID 和其它公开作品。
5. 如果是新账号或客户账号，先爬取账号身份和不少于 10 条公开样本，再生成可应用的账号 Style，最后进入单条封面生产。
6. 最后确认 brief：标题、英文副题、背景方向、比例/时长和编号，确认后生成并保存到素材库。

推荐开场：

```text
我的抖音 ID 是 KevPH2026，这次要做单条封面，内容链接是 ...
```

## 为什么要做

很多内容账号的问题不是单条内容差，而是主页没有被经营过。

封面各做各的，标题层级不稳定，背景图风格乱，合集和单条作品没有统一识别。用户刷到主页时，很难马上知道这个账号到底擅长什么、值得关注什么。

Mr.K Cover Studio 要解决的是这件事：把内容判断变成视觉资产。

## 适用场景

### 爆款复盘

给播放量过万的历史作品重新生成统一封面，让主页从散乱素材变成内容资产库。

### 热点追踪

模型、公司、人物、商业事件出现后，快速把热点变成判断型标题和对应背景。

### 片头 / 片尾动效

用图片或视频素材做底，覆盖作品前 1-2 秒，让主干观点、标题和英文副题以动效出现，先把判断打到屏幕上。

### 个人 IP 视觉固定

账号名、微信 ID、头像印章、K 字标、栏目色和标题层级都固定下来，长期沉淀辨识度。

### Onboarding 初始化

第一次进入页面时先选择 Agent / Web 使用方式，再选择常用模板，最后确认栏目。默认栏目保留，同时支持自定义栏目名、英文名、副文案和栏目色。

### 快速模板

内置 AI 热点拆解、强者金句、一线观察、片头/片尾动效、系列合集、主页背景和自定义栏目入口，适合快速开始一张封面，而不是从空白字段填起。

### 本地素材管理

生成过的封面可以保存到素材库。没有 KV 时走本地存储，配置 KV 后可以走云端。

### 访客试用和验证码登录

未登录用户可以免费使用 3 次 AI 生产能力，包括对话生成封面/动效、解码 DNA 和手动 AI 生图。超过 3 次后会提示输入邮箱验证码登录；邮箱验证通过后自动登录，首次邮箱会自动创建账号。

### 本地模型配置

页面内置本地模型配置面板，可配置 OpenAI 兼容的 LLM 和生图接口，用来做内容分析、标题摘要文案撰写，以及背景图生成。配置只保存在浏览器本机，不写入 Git、素材库或云端。

### 解码 DNA

给 Agent 一个抖音主页/作品链接即可开始。系统会先尝试自动找到作者主页、头像、抖音号/主页 ID 和其它公开作品；如果抖音页面受登录或反爬限制，再补充标题、封面文字、文案或截图转文字。系统会先提炼账号 DNA，再输出栏目、视觉风格、设计方向和可应用的账号 Style。

生成的 Style 会落到页面控件里：栏目名、英文名、副标题、栏目色、配图风格、信息密度和背景方向都可以一键应用，也可以只应用背景方向继续微调。

如果可用样本不足 10 条，系统会明确提示还差几条，不会基于一条链接强行编设计策略。

## 品牌 DNA

- 账号名：`MR.K 在路上`
- 抖音 ID：`KevPH2026`
- 微信 ID：`kevph2026`
- 域名：`dna.superk.ai`
- 口号：`少和人对话，多和AI对话`

固定栏目：

- `AI下半场`：模型、Agent、商业重构
- `强者恒强`：判断力、筹码、个体系统
- `在路上`：出差、客户、一线观察

## 工作流

1. 粘贴抖音分享文案、短链接、截图或主题。
2. 已配置的 LLM 提炼内容角度，生成标题、栏目、摘要和背景方向。
3. 已配置的生图模型生成贴合文案的真实/编辑感背景。
4. 固定模板叠加头像、K 字标、栏目标签、标题和编号。
5. 保存到素材库，或导出 PNG/M4V。

解码 DNA 的工作流：

1. 粘贴抖音链接，并补充至少 10 条作品标题/封面文字/文案样本。
2. Agent 整理内容主题、表达方式、标题气质和视觉线索。
3. 输出账号定位、受众、内容栏目、风格禁忌和 2-3 个设计方向。
4. 再进入单条封面、合集封面或主页背景生产。

## 输出规格

- 单条作品封面：`1080x1920`
- 片头/片尾动效：`1080x1920`，`1.2-2 秒`，浏览器 M4V 优先导出
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

## 本地模型配置

右侧「本地模型配置」面板支持：

- LLM：OpenAI 兼容 Chat Completions 地址、模型名、可选 API Key
- 生图：OpenAI 兼容 Images API 地址、模型名、可选 API Key
- 保存位置：浏览器 `localStorage`，键名 `mrk.localModelConfig`
- 服务行为：每次请求临时读取，不写入服务端文件、KV 或 Git

这些字段不填时，会继续使用 `DEEPSEEK_API_KEY`、`OPENAI_API_KEY` 等环境变量。接口不可用时，页面会回退到本地规则和本地占位配图。

## 邮箱验证码登录

云端验证码依赖 KV 保存验证码和账号会话，并支持两种邮件通道：

- Resend：`RESEND_API_KEY`，可选 `AUTH_EMAIL_FROM`、`AUTH_EMAIL_REPLY_TO`
- SMTP：`SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASSWORD`、`SMTP_FROM`

没有配置 KV 或邮件服务时，页面会进入本地调试验证码流程，方便本地开发；生产环境建议配置 Resend 或 SMTP。

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
/api/dna-agent
/api/generate-image
/api/transcode-m4v
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
RESEND_API_KEY=re_...
AUTH_EMAIL_FROM="Mr.K Cover Studio <login@your-domain.com>"
AUTH_EMAIL_REPLY_TO=kevph2026@example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=login@your-domain.com
```

没有配置 KV 时，浏览器会自动回退到本地登录和本地素材库。
