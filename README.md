<p align="center"><strong>AI Agent Hub</strong><br><span style="font-size:0.85em;">Multi-agent platform · REST API · Telegram bot · Self-hosted</span><br><br><a href="https://ai-demo-latest.onrender.com"><img src="https://img.shields.io/badge/Live-Demo-brightgreen?style=flat-square"/></a> &nbsp; <img src="https://img.shields.io/badge/Python-3.13-informational?style=flat-square"/> &nbsp; <img src="https://img.shields.io/badge/Docker-Private-blue?style=flat-square"/> &nbsp; <img src="https://img.shields.io/badge/License-MIT-success?style=flat-square"/></p>

---

### → [Live Demo](https://ai-demo-latest.onrender.com)

---

A containerized FastAPI service that runs specialized AI agents behind a unified REST API and Telegram bot. Each agent handles a specific task — CV tailoring, weather lookups, recipe generation, prayer time scheduling — with its own tools, prompts, and output pipeline. Connects to any OpenAI-compatible LLM via LiteLLM.

No managed services. No vendor lock-in. Your API key, your data, your server.

---

## What's included

| Agent | Input | Output |
|---|---|---|
| **CV Tailor** | Your CV PDF + cover letter + job description | Tailored PDFs in English and German, sent via Telegram |
| **Weather** | City name | Current temp, humidity, wind, conditions |
| **Recipe** | Ingredients or prompt | Structured recipe with ingredients and steps |
| **Prayer Times** | City name or Telegram location | 5 daily prayers + Tahajjud, with automatic reminder scheduling |
| **General** | Free text | LLM chat response |

All accessible via REST API, Telegram bot, or the built-in web dashboard.

---

## How it works

```
  Telegram webhook          Web dashboard          REST API
        │                        │                     │
        └────────────────────────┼─────────────────────┘
                                 │
                            FastAPI router
                                 │
                         Agent dispatch layer
                          ╱      │      ╲      ╲
                     CV Tailor  Weather  Recipe  Prayer  General
                         │                        │
                    Tool calls              Aladhan API
                  (read_pdf,                      │
                   write_file)             Background scheduler
                         │                (checks every 30s, sends
                   Strands Agent           reminders at each
                         │                prayer time)
                   LiteLLM → your LLM
```

---

## Quick start

```bash
git clone https://github.com/somia295/ai-demo.git && cd ai-demo
uv sync
cp .env.example .env   # fill in your API key
uv run uvicorn hub.main:app --port 8080
```

Open `http://localhost:8080`. Login with the credentials you generated (see below).

### Generate auth credentials

```bash
python -m hub.core.security
```

This prints a `JWT_SECRET` and `ADMIN_PASSWORD_HASH` — put both in your `.env`.

---

## Deploy to production

The Dockerfile is multi-stage and produces a ~235MB image. Tested on [Render](https://render.com).

### Docker

```bash
docker build -t ai-demo .
docker run -p 8080:8080 --env-file .env ai-demo
```

### Render (with private Docker image)

1. Push image to Docker Hub:
   ```bash
   docker build -t yourname/ai-demo:latest .
   docker push yourname/ai-demo:latest
   ```

2. Make the repo private on Docker Hub → Settings → Visibility → Private

3. On Render, create a **Web Service** → **Deploy an existing image**:
   - Image: `docker.io/yourname/ai-demo:latest`
   - Port: `8080`
   - Add Docker Hub credentials under Settings → Registry Credentials (use a Personal Access Token, not your password)

4. Set environment variables (see below)

5. Register the Telegram webhook:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-app.onrender.com/webhook/telegram"
   ```

---

## Configuration

All config is through environment variables (or `.env` for local dev).

**Required:**

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Any OpenAI-compatible API key |
| `JWT_SECRET` | Token signing key (generate with `python -m hub.core.security`) |
| `ADMIN_PASSWORD_HASH` | Bcrypt hash (generate with `python -m hub.core.security`) |

**Optional:**

| Variable | Default | Description |
|---|---|---|
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | LLM API endpoint |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model identifier |
| `OPENAI_TEMPERATURE` | `0.7` | Sampling temperature |
| `OPENAI_MAX_TOKENS` | `4096` | Max response tokens |
| `ADMIN_USERNAME` | `admin` | Dashboard username |
| `TELEGRAM_BOT_TOKEN` | — | From @BotFather. Enables Telegram bot |

### LLM compatibility

Works with anything that speaks the OpenAI chat completions format:

- **OpenAI** — `gpt-4o-mini`, `gpt-4o`, etc.
- **Local** — Ollama, vLLM, LM Studio
- **Other providers** — Groq, Together, DeepSeek, any OpenAI-compatible endpoint

Reasoning models (o1, o3, DeepSeek-R1, QwQ, GLM) are auto-detected — `temperature` is dropped and `max_completion_tokens` is used.

---

## API reference

All endpoints require JWT authentication. Get a token first:

```bash
TOKEN=$(curl -s -X POST https://ai-demo-latest.onrender.com/auth/login \
  -d "username=admin&password=yourpassword" | jq -r .access_token)
```

Then call any agent:

```bash
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"query": "Berlin"}' \
     https://ai-demo-latest.onrender.com/api/agents/weather
```

### Endpoints

| Method | Path | Body |
|---|---|---|
| `POST` | `/auth/login` | `username`, `password` (form-encoded) |
| `POST` | `/api/agents/cv-tailor` | `{"cv_text": "...", "job_description": "..."}` |
| `POST` | `/api/agents/cv-tailor-files` | `{"job_description": "...", "use_sample_job_file": true}` |
| `POST` | `/api/agents/weather` | `{"query": "Berlin"}` |
| `POST` | `/api/agents/recipe` | `{"prompt": "vegetarian pasta"}` |
| `POST` | `/api/agents/prayer` | `{"query": "Berlin"}` or `{"lat": 52.52, "lng": 13.41}` |
| `POST` | `/api/agents/general` | `{"message": "hello"}` |
| `POST` | `/webhook/telegram` | Telegram Bot API payload |

---

## Telegram bot

### Commands

| Command | Description |
|---|---|
| `/cv <job text>` | Tailor CV for a job description |
| `/cvfile` | Tailor CV using `samples/job_description.txt` |
| `/weather <city>` | Current weather |
| `/recipe <prompt>` | Generate a recipe |
| `/prayer <city>` | Show today's prayer times |
| `/help` | List all commands |

### Conversation flow

The bot uses inline keyboards for agent selection. When you send a message, it presents buttons to pick an agent, then asks for input. For Prayer Times, it offers two options: share your location (enables daily reminders) or type a city name.

### Prayer reminders

Once you share your location:
- Timings are fetched from [Aladhan API](https://aladhan.com/prayer-times-api) (free, no key)
- A background scheduler (asyncio, checks every 30s) sends a Telegram message at each prayer time
- Tahajjud time is calculated as the last third of the night (Isha → Fajr)

---

## Project layout

```
hub/
├── main.py                          # App factory, startup events
├── config.py                        # Pydantic BaseSettings
├── agents/
│   ├── base.py                      # Strands Agent + LiteLLM + reasoning detection
│   ├── cv_tailor.py                 # PDF/DOCX output, parallel conversions
│   ├── cv_tailor_text.py            # Text-only variant for REST
│   ├── weather.py                   # Open-Meteo geocoding + forecast
│   ├── recipe.py                    # LLM recipe generation
│   ├── prayer.py                    # Aladhan timings + Tahajjud math
│   └── general.py                   # Fallback LLM chat
├── core/
│   ├── llm.py                       # chat_completion() async helper
│   ├── prompts.py                   # load_prompt() from .txt files
│   ├── security.py                  # JWT issue/verify, bcrypt
│   └── tools.py                     # read_pdf, read_file, write_file
├── routers/
│   ├── rest_agents.py               # Agent HTTP endpoints
│   └── telegram_webhook.py          # Webhook + conversation state
├── services/
│   ├── cv_pipeline.py               # End-to-end CV pipeline
│   ├── prayer_scheduler.py          # Background prayer reminder loop
│   └── telegram_outbound.py         # Bot API: sendMessage, sendDocument
├── telegram/
│   └── dispatch.py                  # Regex agent detection + routing
├── prompts/                         # All prompts as .txt files
└── static/
    └── index.html                   # Dashboard SPA
```

---

## Adding an agent

1. **Agent class** — `hub/agents/my_agent.py`
   ```python
   class MyAgent:
       async def run(self, query: str) -> str:
           return result
   ```

2. **Prompt file** — `hub/prompts/telegram_agent_my_agent.txt`

3. **Wire it up** in these files:

   | File | Change |
   |---|---|
   | `telegram/dispatch.py` | Add to `KNOWN_AGENTS`, `TELEGRAM_AGENT_RULES`, `run_telegram_agent()` |
   | `routers/rest_agents.py` | Add request model + `@router.post()` |
   | `services/telegram_outbound.py` | Add command to `register_bot_commands()` |
   | `routers/telegram_webhook.py` | Add button to keyboard |
   | `static/index.html` | Add section + JS handler |

No framework changes needed. Follow the existing pattern.

---

## Stack

**Backend:** Python 3.13 · FastAPI · Strands Agents · LiteLLM · httpx
**Output:** PyMuPDF · python-docx
**Infra:** Docker (multi-stage) · Render
**APIs:** Open-Meteo · Aladhan · Telegram Bot API

---

MIT License
