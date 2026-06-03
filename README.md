# Mr.K Cover Studio

**A fixed visual cover system for Douyin creators who publish AI, business, judgment, and field-note content.**

[中文](./README.zh-CN.md) | [English](./README.en.md) | [Live Site](https://dna.superk.ai) | [GitHub](https://github.com/KevPH2026/dna-superk-ai)

Mr.K Cover Studio turns a Douyin link, copied share text, screenshot, or content idea into an on-brand cover. It is not a general poster editor. It is a repeatable content asset system for one account style: fixed identity, fixed categories, flexible titles and backgrounds.

## Two Ways To Use It

| Delivery | Best For | Command |
| --- | --- | --- |
| Agent Skill | Send a Douyin link to an Agent, answer a few questions, generate a cover brief and asset | `scripts/install_agent_skill.sh` |
| Local Web Studio | Preview, tune, save to material library, export PNG locally | `scripts/run_local_studio.sh` |

## Why It Exists

Most creator homepages fail quietly. The content may be sharp, but the grid looks accidental: different crops, different fonts, different visual logic, no memory hook.

This project fixes that problem for `MR.K 在路上`.

- One visual language across single posts, collections, and profile background
- AI-assisted title, summary, category, and background direction
- First-run onboarding for choosing Agent/Web workflow, starter template, and content category
- Quick templates for AI news, strong quotes, field notes, collections, profile banners, and custom columns
- Custom categories with editable Chinese name, English name, subtitle, and accent color
- Local-only configuration for OpenAI-compatible LLM and image models
- Realistic editorial backgrounds instead of generic AI wallpaper
- Local material management for generated covers
- A deployable Skill for Agent workflows

## Brand DNA

- Account: `MR.K 在路上`
- Douyin ID: `KevPH2026`
- WeChat ID: `Kevph2026`
- Domain: `dna.superk.ai`
- Categories: `AI下半场`, `强者恒强`, `在路上`

## Core Workflow

1. Paste a Douyin share snippet, short link, screenshot, or topic.
2. The configured LLM extracts the content angle and proposes title/category/summary.
3. The configured image model creates a background that matches the copy.
4. The fixed Mr.K overlay system renders the final cover.
5. Save to material library or export PNG.

## Outputs

- Single work cover: `1080x1920`
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

## Production

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

When KV is not configured, the browser falls back to local-only login and local asset storage.
