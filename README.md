# Lumine Tech Autopost

> An intelligent Twitter bot powered by local AI vision models. It sees your screen, thinks like a human, and interacts naturally — no APIs required.

## Overview

Lumine Tech Autopost is a browser-based AI agent that navigates Twitter/X just like a person would. Instead of using the Twitter API (which is restrictive and expensive), it uses a **local vision model** (like Qwen2.5-3B or Gemma 4) to look at screenshots of the page and decide what to do next.

It clicks buttons, scrolls through feeds, reads tweets, likes interesting posts, replies to discussions, retweets content, and even posts original tweets — all while behaving like a real human to avoid detection.

The entire system runs on your own machine using [llama-server](https://github.com/ggml-org/llama.cpp) for inference. No data ever leaves your computer.

## Features

- **Vision-based AI** — The model sees exactly what you see on screen and makes decisions based on the visual layout
- **Multiple personas** — Choose from Default, Tech Enthusiast, or Finance Investor personalities that shape what the bot says and engages with
- **Human-like behavior** — Random delays, jittery mouse movements, stepped scrolling, reading time simulation, and varied action patterns
- **Fully local** — Everything runs on your machine. No cloud APIs, no data leaks, no monthly fees
- **Persistent browser sessions** — Uses your existing Brave (or Chrome) profile so you stay logged in
- **Customizable** — Tweak delays, limits, prompts, and personas to match your style
- **Anti-detection built-in** — Engineered from the ground up to mimic real browsing patterns

## How It Works

The bot runs a continuous loop:

1. **Perceive** — Takes a screenshot of the current Twitter page
2. **Think** — Sends the screenshot to a local vision model (llama-server), which decides the next action
3. **Act** — Executes the action using Playwright (click, scroll, type, etc.)
4. **Wait** — Pauses for a random human-like delay
5. **Repeat**

The model receives a detailed prompt that includes:
- The current URL and page context
- What happened in the last action (success or failure)
- How many engagements have been done this session
- Instructions to behave like a real person

## Personas

Personas define the bot's personality and interests. Each has its own voice, topics, and behavior style.

| Persona | Voice | Interests |
|---------|-------|-----------|
| **Default** | Neutral, professional | Technology, innovation, general topics |
| **Tech Enthusiast** | Casual, passionate | AI, programming, startups, gadgets |
| **Finance Investor** | Analytical, data-driven | Stocks, crypto, market trends, forex |

Personas are stored as JSON files in the `persona/` directory and are easy to customize or extend.

## Anti-Detection & Human-Like Behavior

Getting suspended is easy if you act like a bot. This project is built to avoid that.

### What makes it look human

- **Random delays** — Every action is followed by a pause of 10-45 seconds (configurable). No two waits are the same.
- **Stepped scrolling** — Instead of jumping 600px instantly, it scrolls in small chunks (3-8 steps) with tiny gaps, just like a real mouse wheel.
- **Mouse jitter** — Before clicking anything, the cursor moves to a random position first, then to the target.
- **Reading time** — When reading tweets, it waits based on how long the text would take to read (200-400 words per minute).
- **Action variety** — The model is explicitly told to mix up its behavior: scroll, like, reply, retweet, post. Never the same thing twice in a row.
- **Engagement limits** — Only 2 tweets, 5 likes, 3 replies, and 2 retweets per session. Once limits are hit, it just browses.
- **Single tab** — The browser starts with only one tab, directly on x.com/home. No suspicious blank tabs.
- **Randomized values** — Scroll amounts, click positions, delay lengths are all randomized within realistic ranges.

### What it avoids

- Fixed delays (always waiting exactly 5 seconds)
- Rapid-fire actions (scrolling 10 times without stopping)
- Repetitive patterns (scroll → scroll → scroll)
- Bot-like navigation (jumping between pages too quickly)
- Suspicious timing (clicking faster than a human could read)

## Tech Stack

- **Python 3.11+** — Core language
- **Playwright** — Browser automation (Brave/Chromium)
- **llama.cpp / llama-server** — Local LLM inference
- **Qwen2.5-3B / Gemma 4** — Vision-language models
- **Pillow** — Image processing for screenshots

## Requirements

- Python 3.11 or later
- A local llama-server instance running on `localhost:8080`
- A vision-capable model (Qwen2.5-3B or similar)
- Brave or Chrome browser with a logged-in Twitter/X account

## Quick Start

### 1. Start the AI model server

Make sure llama-server is running with a vision model loaded:

```bash
./llama-server \
  -m path/to/qwen2.5-3b.gguf \
  --mmproj path/to/mmproj-qwen2.5-3b.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  -ngl 99
```

### 2. Set up the bot

```bash
git clone https://github.com/yourusername/lumine-tech-autopost
cd lumine-tech-autopost

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# Edit .env with your settings
```

### 3. Run it

```bash
python3 main.py --steps 10 --persona "Tech Enthusiast"
```

## Configuration

All settings are in `.env` file or `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `MIN_DELAY_SECONDS` | 10 | Minimum wait between actions |
| `MAX_DELAY_SECONDS` | 45 | Maximum wait between actions |
| `MAX_TWEETS_PER_SESSION` | 2 | Max original tweets per run |
| `MAX_LIKES_PER_SESSION` | 5 | Max likes per run |
| `MAX_REPLIES_PER_SESSION` | 3 | Max replies per run |
| `MAX_RETWEETS_PER_SESSION` | 2 | Max retweets per run |
| `MAX_ENGAGEMENTS` | 6 | Total engagement cap per run |

## Command Line Options

```bash
python3 main.py --help
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--persona` | Default | Persona to use (Default, Tech Enthusiast, Finance Investor) |
| `--headless` | off | Run browser without visible window |
| `--steps` | 12 | Maximum number of actions per session |

## Safety Notes

- **Use responsibly.** Automating Twitter interactions violates their Terms of Service. This project is for educational purposes.
- **Start small.** Begin with `--steps 3` to verify everything works before running longer sessions.
- **Use a throwaway account** if you want to experiment without risk.
- The bot is designed to be conservative — it will do less, not more. You can increase limits, but doing so increases risk.

## Project Structure

```
lumine-tech-autopost/
├── agent/              # Browser driver, action execution, vision loop
│   ├── driver.py       # Playwright browser management
│   ├── vision.py       # Main agent loop (perceive → think → act)
│   └── actions.py      # Click, scroll, type, tweet implementations
├── brain/              # Memory, context, decision tracking
│   └── memory.py       # Session memory and engagement counting
├── llm/                # LLM client
│   └── client.py       # llama-server API communication
├── persona/            # Persona definitions
│   ├── manager.py      # Persona loading and management
│   ├── default.json
│   ├── tech_enthusiast.json
│   └── finance_investor.json
├── twitter/            # Twitter-specific selectors and helpers
│   └── selectors.py    # Element selectors and descriptions
├── utils/              # Utilities
│   ├── logger.py       # Logging configuration
│   └── helpers.py      # Random delays, helpers
├── config.py           # Configuration management
├── main.py             # Entry point
├── models.ini          # AI model definitions
├── .env.example        # Environment template
├── requirements.txt    # Python dependencies
└── README.md           # This file
```
