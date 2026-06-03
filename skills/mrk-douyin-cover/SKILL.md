---
name: mrk-douyin-cover
description: Use when the user sends a Douyin/TikTok China share link, copied Douyin share text, screenshot, caption, image, or topic and wants to generate or revise an on-brand cover for the Mr.K在路上 account. Guides Codex to ask a few focused questions, extract the core idea, choose one of the fixed Mr.K content categories, generate a realistic background, compose the cover, save it into the SNS cover/material library, and help the user replace or manage the asset.
metadata:
  short-description: Mr.K 抖音链接封面生成
---

# Mr.K Douyin Cover

## Canon

- Account: `MR.K 在路上`; Douyin ID: `KevPH2026`.
- Fixed categories:
  - `AI下半场` (`ai`, accent `#b2ff52`)
  - `强者恒强` (`strong`, accent `#50d6ff`)
  - `在路上` (`road`, accent `#ff6052`)
- New single-work covers default to `1:1`, `1080x1080`.
- A cover must include the work's main title. Make the Chinese title large enough for Douyin grid browsing; include an uppercase English subtitle when useful.
- Do not add play count, likes, or historical performance numbers unless the user explicitly asks.
- Style: dark editorial, high contrast, mature technology/business mood, restrained neon accent, K mark/avatar/category chip, consistent typography.
- Avoid generic AI-looking backgrounds: no abstract orbs, bokeh blobs, random neural-network wallpaper, or vague sci-fi gradients. Prefer realistic/editorial scenes that match the content.

## Workflow

1. **Collect source**
   - If the user provides a Douyin URL or copied share text, extract the URL, caption, hashtags, visible title, and topic.
   - If the link cannot be opened because of auth, anti-bot, or app restrictions, do not get stuck; ask for the caption, screenshot, or key text.
   - Private works are excluded by default unless the user explicitly asks to process them.

2. **Conversational Agent intake**
   Use a short dialogue funnel before generating. The Agent should collect context in this order, while skipping anything already known:
   - `账号入口`: ask for Douyin ID, profile link, or profile screenshot. For Mr.K, default to `KevPH2026` unless the user names a different account.
   - `任务目标`: ask whether this is single-work cover, DNA decode, batch cover refresh, collection cover, or profile background.
   - `内容分类`: infer one of `AI下半场`, `强者恒强`, `在路上`; ask only when ambiguous. Use custom category only when the content clearly does not fit.
   - `素材输入`: for a single work, ask for the link/caption/screenshot/key text; for DNA decode, require at least 10 public work samples; for batch work, ask for the list and priority rule.
   - `生成确认`: before producing the asset, confirm title, English subtitle, background direction, ratio, and code in one compact brief.

   Opening pattern:
   ```text
   先建上下文：这是 Mr.K 的 KevPH2026，还是一个新账号？这次要做单条封面、解码 DNA、批量换封面、合集封面，还是主页背景？
   ```

3. **DNA decode mode**
   Use this mode when the user asks to analyze a creator/account, read multiple Douyin works, extract `账号DNA`, or produce a design direction before generating individual covers.
   - Require at least 10 public work samples before making a full DNA conclusion. Samples can be titles, cover text, captions, copied share text, or OCR from screenshots.
   - If a Douyin profile/work link is blocked by login, anti-bot, or the in-app browser, say that clearly and ask for the missing samples instead of guessing.
   - Exclude private works by default.
   - Output:
     - account positioning, audience, voice, and content pillars;
     - title patterns and recurring content angles;
     - style signals and visual taboos;
     - 2-3 cover/profile/collection design directions;
     - operating rules for future cover generation.
   - If using the local Web Studio, call `/api/dna-agent` with:
     ```json
     {
       "douyin_url": "",
       "source_text": "10+ work samples",
       "content_samples": [],
       "goal": "提炼账号DNA并输出设计方向"
     }
     ```

4. **Ask only missing questions**
   Ask 2-4 concise questions when the answer is not inferable. Use defaults aggressively.
   - `账号`: default to Mr.K / `KevPH2026` unless the user says this is another account.
   - `任务`: ask only if the user did not specify single cover, DNA decode, batch refresh, collection, or profile background.
   - `用途/比例`: single-work cover `1:1` by default; ask only if it may be a collection cover, homepage background, or image-post carousel.
   - `主标题`: offer a recommended title and ask whether to use it. Preserve exact user-specified titles.
   - `内容分类`: infer from the content; ask only if ambiguous among `AI下半场`, `强者恒强`, `在路上`.
   - `背景方向`: offer 2-3 realistic options tied to the copy, such as office desk, city night, product screen, conference room, road scene, lab, market chart, or portrait-like editorial scene.
   - `编号`: use the user's value if given, otherwise choose the next sensible `K-xx` or omit if the asset batch already has a naming rule.

   Good question pattern:
   ```text
   我先按 Mr.K / KevPH2026 的 1:1 单条封面处理。还差 3 个判断：
   1. 主标题用「...」可以吗？
   2. 分类我建议放「AI下半场 / 强者恒强 / 在路上」，你选哪个？
   3. 背景走 A「...」、B「...」还是 C「...」？
   ```

5. **Build a cover brief**
   Keep a compact brief before generation:
   ```json
   {
     "account": "MR.K 在路上 / KevPH2026",
     "source_url": "",
     "task": "single_cover|dna_decode|batch_refresh|collection|profile",
     "category": "ai|strong|road",
     "ratio": "1:1",
     "title_cn": "",
     "title_en": "",
     "summary": "",
     "background_direction": "",
     "background_prompt": "",
     "code": "K-xx"
   }
   ```

6. **Title rules**
   - Ideal Chinese title length: 8-18 characters, split into 2-3 strong lines.
   - Use judgment-title forms:
     - `X不是Y，是Z`
     - `X死了，谁还活着？`
     - `如果你还在X，会错过Y`
     - `这不是热点，这是重新定价`
     - `多和聪明的人交往`
   - Avoid plain topic labels like `AI发展趋势` unless the user insists.
   - For quote/cognition content, sharpen into a repeatable judgment rather than a soft slogan.

7. **Background mapping**
   - AI model/product/business news: real product screen, terminal/API console, founder desk, conference table, market chart, server room, newsroom wall.
   - Strong people/cognition/Jobs/business judgment: late-night office, whiteboard discussion, desk lamp, book/notes, portrait-like black-and-white editorial, negotiation room.
   - Road/field notes: city night, airport/train/car interior, client site, hotel desk, rainy street, border/cross-border scene.
   - Use the accent color only as subtle environmental light or a small design element.

8. **Generate and compose**
   - In `/Users/k/Documents/SNS`, prefer the existing MRK cover system and drawing rules:
     - `mrk-cover-studio.html` for interactive generation/material management.
     - `make_high_play_covers.py` and `make_low_play_covers.py` as reference implementations for typography, layout, avatar, K mark, category chips, and output manifests.
   - For a new single cover, create a narrowly scoped script or reuse existing drawing functions; save to `/Users/k/Documents/SNS/generated-covers/ad-hoc/` unless the user asks for a batch folder.
   - If AI background generation is needed, generate the background first from the `background_prompt`, then composite the fixed Mr.K overlay. The background must serve the title, not compete with it.
   - If the user asks to update the web product/material library, update the relevant manifest/local storage/cloud asset path when available, then open the page or folder for inspection.

9. **Local page deployment**
   - If the user asks to deploy, preview, open, or use a local page, run this skill's local launcher:
     ```bash
     scripts/launch_local_studio.sh
     ```
   - The script serves `/Users/k/Documents/SNS/mrk-cover-studio.html` through `cover_studio_server.py`, chooses the next free port starting at `8765`, prints the local URL, then keeps the server running in the foreground.
   - In Codex, keep the returned dev-server session alive while the user is using the page. If the user is running it manually in Terminal and wants background mode, use `launch_local_studio.sh --background`.
   - Open the printed URL in the in-app browser when the user wants to operate the page directly.
   - For full AI workflow, preserve any available `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, `KV_REST_API_URL`, and `KV_REST_API_TOKEN` environment variables. Without them, the page still works for local editing and local asset storage.

10. **Local model configuration**
   - The Web Studio exposes a local-only model panel for analysis, copywriting, and image generation.
   - Store model settings only in the browser's `localStorage` under `mrk.localModelConfig`; never commit API keys, model keys, or private endpoints to the repo.
   - Supported LLM shape: OpenAI-compatible Chat Completions endpoint, model name, optional API key. Examples: DeepSeek, LM Studio, Ollama OpenAI-compatible `/v1/chat/completions`.
   - Supported image shape: OpenAI-compatible Images endpoint, model name, optional API key. Examples: OpenAI Images-compatible local gateways or cloud image endpoints.
   - Each request may include `model_config`; the local server uses it only for that request and does not persist it.
   - If the configured endpoint fails, fall back to the existing local planning/image placeholder flow so the user can still continue editing.

11. **Verify**
   Before finishing, inspect or open the generated image/contact sheet and check:
   - ratio and pixel size match the request;
   - title is readable in Douyin grid size;
   - no text overlap;
   - no accidental play count or private-work marker;
   - category, ID, and code are correct;
   - background feels specific to the copy, not generic AI wallpaper.

12. **Hand off**
   - Show the generated image with a Markdown image tag when possible.
   - Give the absolute file path.
   - If a local page was deployed, give the URL and the log path.
   - If the user wants to upload to Douyin backend, note that the in-app browser may not support local file upload automation; open/reveal the folder so the user can select the file manually.
