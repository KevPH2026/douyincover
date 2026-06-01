# Mr.K Cover Studio

Git-built cover generator for `dna.superk.ai`.

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

## Deploy

Vercel serves the static app and the Python serverless functions at:

```text
/api/cover-agent
/api/generate-image
```

Required production environment variable:

```text
DEEPSEEK_API_KEY
OPENAI_API_KEY
```

Optional:

```text
DEEPSEEK_MODEL=deepseek-chat
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_QUALITY=medium
OPENAI_IMAGE_INPUT_FIDELITY=high
```
