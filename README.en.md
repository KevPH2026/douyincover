# Mr.K Cover Studio

**A fixed visual cover system for Douyin creators working in AI, business judgment, personal leverage, and field notes.**

[中文](./README.zh-CN.md) | [Default README](./README.md) | [Live Site](https://dna.superk.ai)

Mr.K Cover Studio is not a generic poster maker. It is a production system for one repeatable creator identity: fixed brand assets, fixed content categories, flexible titles, flexible backgrounds.

Give it a Douyin share snippet, short link, screenshot, image reference, or plain topic. The system extracts the angle, proposes the cover copy, generates a matching background, and renders a cover inside the Mr.K visual system.

## Two Delivery Modes

| Mode | Use It When | Command |
| --- | --- | --- |
| Agent Skill | You want to send a Douyin link to an Agent and let it ask the missing questions | `scripts/install_agent_skill.sh` |
| Local Web Studio | You want a browser workspace for previewing, tuning, saving, and exporting covers | `scripts/run_local_studio.sh` |

## Why This Exists

Many creator accounts do not lose attention because one post is weak. They lose it because the grid has no memory.

Different crops. Different type sizes. Different backgrounds. No stable category logic. A viewer lands on the profile and cannot quickly understand what the account owns.

Mr.K Cover Studio turns content judgment into a visual asset system.

## Use Cases

### Repackage Winning Posts

Refresh high-performing historical works with consistent covers so the profile feels like an intentional library, not a folder of uploads.

### Move Fast On Hot Topics

Turn AI model updates, founder quotes, company moves, and market signals into judgment-driven titles and topic-specific backgrounds.

### Lock A Personal IP

Account name, WeChat ID, avatar stamp, K mark, category color, and title hierarchy stay fixed across outputs.

### Manage Generated Assets

Covers can be saved into a material library. It works locally by default and can use KV storage in production.

## Brand DNA

- Account: `MR.K 在路上`
- Douyin ID: `KevPH2026`
- WeChat ID: `Kevph2026`
- Domain: `dna.superk.ai`
- Slogan: `少和人对话，多和AI对话`

Fixed categories:

- `AI下半场`: models, agents, business reconstruction
- `强者恒强`: judgment, leverage, personal systems
- `在路上`: travel, clients, field observation

## Workflow

1. Paste a Douyin share snippet, short link, screenshot, image, or topic.
2. DeepSeek extracts the angle and proposes title, category, summary, and background direction.
3. Image generation creates a realistic editorial background matched to the copy.
4. The fixed template adds avatar, K mark, category chip, title, subtitle, and code.
5. Save to the material library or export PNG.

## Output Sizes

- Single work cover: `1080x1920`
- Collection cover: `1080x1080`
- Profile background: `1920x640`
- Material library: local by default, KV-backed in production

## Run Locally

```bash
scripts/run_local_studio.sh
```

Or run the server directly:

```bash
python3 cover_studio_server.py
```

Open:

```text
http://127.0.0.1:8765/mrk-cover-studio.html
```

Enable real image generation:

```bash
OPENAI_API_KEY=sk-... python3 cover_studio_server.py
```

## Install As An Agent Skill

```bash
scripts/install_agent_skill.sh
```

Then invoke:

```text
$mrk-douyin-cover Generate a Mr.K style cover from this Douyin link: https://v.douyin.com/...
```

The Skill uses the fixed Mr.K visual rules by default and only asks for missing decisions, such as title, category, background direction, and code.

## Deploy

Vercel serves the static studio and Python serverless APIs:

```text
/api/cover-agent
/api/generate-image
/api/auth
/api/assets
```

Required environment variables:

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

Without KV configuration, the browser falls back to local-only auth and asset storage.
