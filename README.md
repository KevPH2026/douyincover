# Mr.K Cover Studio

`dna.superk.ai` 的固定视觉封面生产器。

Mr.K Cover Studio 面向知识型短视频账号，把抖音链接、作品文案、自然语言主题和参考图，转成统一风格的主页背景、合集封面和单条作品封面。

核心不是再做一个通用海报工具，而是把一个账号的视觉 DNA 固定下来：该固定的固定，该输入的输入，让内容团队把精力放在判断、标题和背景场景上。

## Product Positioning

一句话：把抖音内容资产变成有识别度的账号视觉系统。

适合这类内容账号：

- AI、商业、认知、个人 IP 类知识账号
- 需要批量统一历史作品封面的创作者
- 需要把热点快速加工成判断型封面的运营者
- 希望主页、合集、单条作品保持同一套视觉语言的账号

## Use Cases

### 爆款复盘

把播放量过万的历史作品重新生成统一封面，让主页从散乱素材变成可识别的内容资产库。

### 热点追踪

粘贴抖音链接或分享文案，自动提炼标题、栏目、摘要和背景方向，快速产出适合发布的封面。

### 个人 IP 视觉固定

账号名、微信 ID、头像印章、K 字标、栏目色、标题层级都被锁定，避免每次做图都跑偏。

### AI 背景生成

根据作品主题生成更贴合内容的真实/编辑感背景，不使用泛泛的 AI 风抽象图。

## Brand System

固定资产：

- 账号名：`MR.K 在路上`
- 抖音 ID：`KevPH2026`
- 微信 ID：`Kevph2026`
- 域名：`dna.superk.ai`
- 口号：`少和人对话，多和AI对话`

固定栏目：

- `AI下半场`：模型、Agent、商业重构
- `强者恒强`：判断力、筹码、个体系统
- `在路上`：出差、客户、一线观察

## Workflow

1. 粘贴抖音分享文案、作品链接、图片或自然语言主题。
2. DeepSeek 提炼标题、栏目、摘要和封面方向。
3. Image 生成贴合文案的背景图。
4. 固定 Mr.K 视觉系统自动叠加标题、头像、K 字标和栏目标签。
5. 保存到素材库或导出 PNG。

## Outputs

- 单条作品封面：`1080x1920`
- 合集封面：`1080x1080`
- 主页背景：`1920x640`
- 生成素材库：本地可用，配置 KV 后支持云端保存

## Local

```bash
python3 cover_studio_server.py
```

Open:

```text
http://127.0.0.1:8765/mrk-cover-studio.html
```

Enable real AI image generation locally:

```bash
OPENAI_API_KEY=sk-... python3 cover_studio_server.py
```

The studio can generate a cover from a full Douyin share snippet or short link. Paste the copied Douyin text into the right inspector and use `抖音链接生成封面`; the backend extracts the link, cleans copy-code noise, reads available metadata, and returns a fixed-style Mr.K cover plan.

## Skill

This repo includes a Codex Skill source:

```text
skills/mrk-douyin-cover/
```

Use it when a Douyin link, share text, screenshot, or content topic should become a Mr.K-style cover. The Skill asks only the missing questions, builds the cover brief, and can launch the local studio page quickly.

## Deploy

Vercel serves the static app and the Python serverless functions at:

```text
/api/cover-agent
/api/generate-image
/api/auth
/api/assets
```

Required production environment variables:

```text
DEEPSEEK_API_KEY
OPENAI_API_KEY
KV_REST_API_URL
KV_REST_API_TOKEN
```

Optional:

```text
DEEPSEEK_MODEL=deepseek-chat
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_QUALITY=medium
OPENAI_IMAGE_INPUT_FIDELITY=high
ACCOUNT_KV_PREFIX=mrkcover
```

When KV is not configured, the browser falls back to local-only login and local asset storage.
