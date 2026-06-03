# Mr.K Cover Studio

**A fixed visual cover system for Douyin creators who publish AI, business, judgment, and field-note content.**

[中文](./README.zh-CN.md) | [English](./README.en.md) | [Live Site](https://dna.superk.ai) | [GitHub](https://github.com/KevPH2026/douyincover)

Mr.K Cover Studio turns a Douyin link, copied share text, screenshot, or content idea into an on-brand cover. It is not a general poster editor. It is a repeatable content asset system for one account style: fixed identity, fixed categories, flexible titles and backgrounds.

## Two Ways To Use It

| Delivery | Best For | Command |
| --- | --- | --- |
| Agent Skill | Send a Douyin link to an Agent, answer a few questions, generate a cover brief and asset | `scripts/install_agent_skill.sh` |
| Local Web Studio | Preview, tune, save to material library, export PNG/M4V locally | `scripts/run_local_studio.sh` |

## Conversational Agent Workflow

The Agent does not generate first. It asks for context, then turns the answer into a production brief:

Agent integration guide: [download the Skill or copy the prompt](./AGENT_GUIDE.md).

1. Ask for Douyin ID, profile link, or profile screenshot. For Mr.K, default to `KevPH2026`.
2. Ask for the task: single-work cover, motion intro/outro, DNA decode, batch cover refresh, collection cover, or profile background.
3. Choose the category: prefer `AI下半场`, `强者恒强`, or `在路上`; use a custom category only when needed.
4. Collect material: one link/caption/screenshot for a single work; image/video material for a motion intro/outro when available; for DNA decode, one public Douyin work link is enough to start because the crawler will try to discover the creator profile, avatar, ID, and more public works.
5. For a new creator or client account, crawl `account_identity` and at least 10 public samples before generating an applicable `style_profile`.
6. Confirm the brief: Chinese title, English subtitle, background direction, ratio/duration, and code. Then generate and save to the material library.

Starter prompt:

```text
My Douyin ID is KevPH2026. I want a single-work cover. The content link is ...
```

## Why It Exists

Most creator homepages fail quietly. The content may be sharp, but the grid looks accidental: different crops, different fonts, different visual logic, no memory hook.

This project fixes that problem for `MR.K 在路上`.

- One visual language across single posts, 1-2 second motion intros/outros, collections, and profile background
- AI-assisted title, summary, category, and background direction
- DNA decode from at least 10 content samples before proposing a design direction
- One-link account discovery: from a single public Douyin work link, try to pull creator profile, avatar, ID, and related public works
- Account Style generation that can be applied to category, accent color, image style, density, and background prompt controls
- First-run onboarding for choosing Agent/Web workflow, starter template, and content category
- Quick templates for AI news, strong quotes, field notes, motion intros/outros, collections, profile banners, and custom columns
- Custom categories with editable Chinese name, English name, subtitle, and accent color
- Local-only configuration for OpenAI-compatible LLM and image models
- Anonymous users can try 3 AI generation actions before email-code login is required
- Email verification login with auto-create account on first verified email
- Realistic editorial backgrounds instead of generic AI wallpaper
- Local material management for generated covers and motion frames
- A deployable Skill for Agent workflows

## Brand DNA

- Account: `MR.K 在路上`
- Douyin ID: `KevPH2026`
- WeChat ID: `kevph2026`
- Domain: `dna.superk.ai`
- Categories: `AI下半场`, `强者恒强`, `在路上`

## Core Workflow

1. Paste a Douyin share snippet, short link, screenshot, or topic.
2. The configured LLM extracts the content angle and proposes title/category/summary.
3. The configured image model creates a background that matches the copy.
4. The fixed Mr.K overlay system renders the final cover.
5. Save to material library or export PNG/M4V.

## DNA Decode

For a new creator or account, paste one public Douyin profile/work link. The crawler first tries to discover the author profile, avatar, ID, and related public works. If Douyin blocks the public page, paste titles, cover text, captions, or screenshot OCR as fallback. The Agent then extracts:

- crawled account identity: nickname, Douyin/profile ID, avatar URL, and profile URL when available
- account positioning, audience, voice, and content pillars
- style signals and visual taboos
- an applicable `style_profile`: category, column labels, accent color, image style, density, background direction, and cover rules
- 2-3 design directions for covers, collections, and profile background
- operating rules for future cover generation

If fewer than 10 usable samples are found, the Agent returns a sample-gap request instead of inventing a DNA.

## Outputs

- Single work cover: `1080x1920`
- Motion intro/outro overlay: `1080x1920`, `1.2-2s`, M4V-first export from the browser
- Collection cover: `1080x1080`
- Profile background: `1920x640`
- Material library: local by default, KV-backed in production

## Local Development

```bash
python3 cover_studio_server.py
```

Open:

```text
http://127.0.0.1:8765/mrk-cover-studio.html
```

With image generation:

```bash
OPENAI_API_KEY=sk-... python3 cover_studio_server.py
```

## Local Model Configuration

The Web Studio includes a local-only model panel for analysis, copywriting, and background generation.

- LLM: OpenAI-compatible Chat Completions endpoint, model name, optional API key
- Image: OpenAI-compatible Images endpoint, model name, optional API key
- Storage: browser `localStorage` only, under `mrk.localModelConfig`
- Server behavior: the config is used only for the current API request and is not persisted

Leave these fields empty to use environment variables such as `DEEPSEEK_API_KEY` and `OPENAI_API_KEY`.

## Auth And Trial Limit

Logged-out visitors can use 3 AI production actions: Agent cover/motion generation, DNA decode, or manual AI background generation. After the third action, the page opens the account menu and requires email-code login.

Email-code login supports:

- Resend: `RESEND_API_KEY`, optional `AUTH_EMAIL_FROM`, `AUTH_EMAIL_REPLY_TO`
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`
- Local/dev fallback: when KV or email delivery is not configured, the browser uses a local debug code flow

## Production

Vercel serves the static studio and Python serverless APIs:

```text
/api/cover-agent
/api/dna-agent
/api/generate-image
/api/transcode-m4v
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
RESEND_API_KEY=re_...
AUTH_EMAIL_FROM="Mr.K Cover Studio <login@your-domain.com>"
AUTH_EMAIL_REPLY_TO=kevph2026@example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=login@your-domain.com
```

When KV is not configured, the browser falls back to local-only login and local asset storage.
