# Lumine Tech Autopost - Project Plan

## Overview

An AI-powered Twitter/X bot that uses a **local Gemma 4 E3B QAT vision model** (via llama-server) as a **browser agent**. Instead of the Twitter API, it uses **Playwright** to automate a real browser, and the vision model "sees" screenshots and decides what actions to take — like a human sitting at a computer.

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Vision LLM** | Gemma 4 E3B QAT (local, mmproj) | See screenshots, decide actions, generate content |
| **LLM Server** | llama-server (localhost:8080) | OpenAI-compatible vision API endpoint |
| **Language** | Python 3.10+ | Bare tech, no framework |
| **Browser** | Playwright | Browser automation (Chromium) |
| **HTTP Client** | requests | Communicate with llama-server |
| **Config** | python-dotenv | Environment variable management |

---

## How the Browser Agent Works

```
┌──────────────────────────────────────────────────────────────┐
│                     Main Controller                           │
│  (orchestrates the perceive-think-act loop)                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌──────────────┐
│   Playwright     │ │  Vision LLM │ │  Persona     │
│   Browser Agent  │ │  (Gemma 4)  │ │  Manager     │
│                  │ │             │ │              │
│  - Screenshot    │ │  - See page │ │  - Traits    │
│  - Click/tap     │ │  - Decide   │ │  - Tone      │
│  - Type text     │ │  - Generate │ │  - Rules     │
│  - Scroll        │ │  - Plan     │ │              │
│  - Read DOM      │ │             │ │              │
└─────────────────┘ └─────────────┘ └──────────────┘
```

### The Agent Loop

```
1. PERCEIVE: Take screenshot of current Twitter page
2. THINK:   Send screenshot + persona prompt to Gemma 4
            Model outputs a structured action decision
3. ACT:     Execute the action via Playwright (click, type, scroll, etc.)
4. REPEAT:  Go to step 1
```

---

## Project Structure

```
lumine-tech-autopost/
├── .env.example              # Configuration template
├── .env                      # Config (gitignored)
├── requirements.txt          # Python dependencies
├── config.py                 # Configuration loading
├── agent/
│   ├── __init__.py
│   ├── driver.py             # Playwright browser setup & management
│   ├── vision.py             # Send screenshots to Gemma 4, parse decisions
│   └── actions.py            # Action executors (click, type, scroll, navigate)
├── llm/
│   ├── __init__.py
│   └── client.py             # llama-server API client (vision support)
├── persona/
│   ├── __init__.py
│   ├── manager.py            # Persona loading & switching
│   └── personas/
│       ├── default.json
│       └── tech_enthusiast.json
├── brain/
│   ├── __init__.py
│   ├── decide.py             # Decision prompt construction & parsing
│   ├── context.py            # Timing, session state, memory
│   └── memory.py             # Short-term memory (engaged tweets, chat)
├── twitter/
│   ├── __init__.py
│   ├── timeline.py           # Timeline navigation & tweet extraction
│   ├── actions.py            # Twitter-specific: tweet, like, retweet, reply, bookmark
│   └── selectors.py          # CSS/XPath selectors for Twitter UI elements
├── main.py                   # Entry point
├── utils/
│   ├── __init__.py
│   ├── logger.py             # Logging setup
│   └── helpers.py            # Misc helpers
└── PLAN.md                   # This file
```

---

## Communication with llama-server

### Vision API Call Format

The model receives a screenshot of the Twitter page:

```python
POST /v1/chat/completions
{
    "model": "gemma-4-e3b-qat",
    "messages": [
        {
            "role": "system",
            "content": "You are TechEnthusiast. Your task is to browse Twitter. ..."
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What should I do next on this page?"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
            ]
        }
    ],
    "temperature": 0.7,
    "max_tokens": 500
}
```

### Structured Output Format

The model responds with a JSON action:

```json
{
    "action": "click",
    "target": "tweet_compose",
    "reason": "I want to post about AI trends",
    "text": "Just read a fascinating paper about multimodal AI architectures..."
}
```

### Available Actions

| Action | Parameters | Description |
|--------|-----------|-------------|
| `scroll_down` | amount (int, px) | Scroll down the page |
| `scroll_up` | amount (int, px) | Scroll up the page |
| `click` | target (str) | Click a UI element by data-testid |
| `type` | target, text | Type text into a field |
| `tweet` | text | Compose and post a tweet |
| `like` | tweet_index (int) | Like a tweet on the timeline |
| `retweet` | tweet_index | Retweet a tweet |
| `reply` | tweet_index, text | Reply to a tweet |
| `bookmark` | tweet_index | Bookmark a tweet |
| `navigate` | url | Go to a specific URL |
| `wait` | seconds (int) | Wait for N seconds |
| `done` | reason | Signal completion for this session |

---

## Twitter UI Selectors (`twitter/selectors.py`)

Twitter uses `data-testid` attributes extensively:

```python
SELECTORS = {
    "tweet_compose": '[data-testid="tweetTextarea_0"]',
    "tweet_button": '[data-testid="tweetButtonInline"]',
    "like_button": '[data-testid="like"]',
    "unlike_button": '[data-testid="unlike"]',
    "retweet_button": '[data-testid="retweet"]',
    "retweet_confirm": '[data-testid="retweetConfirm"]',
    "bookmark_button": '[data-testid="bookmark"]',
    "reply_button": '[data-testid="reply"]',
    "tweet_text": '[data-testid="tweetText"]',
    "tweet_article": 'article[data-testid="tweet"]',
    "sidebar_tweet": '[data-testid="sideBarTweetButton"]',
    "trends_panel": '[data-testid="sidebarColumn"]',
    "login_username": 'input[autocomplete="username"]',
    "login_password": 'input[autocomplete="current-password"]',
    "next_button": 'text="Next"',
    "login_button": 'text="Log in"',
}
```

---

## Phased Implementation

### Phase 1: Core Infrastructure
- [ ] Project setup, dependencies, config
- [ ] Playwright browser driver (launch, context, persistent cookies)
- [ ] llama-server vision client
- [ ] Logging

### Phase 2: Agent Loop
- [ ] Perceive: screenshot + DOM extraction
- [ ] Think: vision prompt construction, response parsing
- [ ] Act: action executor + element finder
- [ ] Main agent loop with state management

### Phase 3: Twitter Actions
- [ ] Twitter login flow (browser-based auth)
- [ ] Tweet composition & posting
- [ ] Like/unlike, retweet, reply, bookmark
- [ ] Timeline reading & browsing

### Phase 4: Persona System
- [ ] Persona JSON definitions
- [ ] Dynamic system prompt construction
- [ ] Tone/language rules

### Phase 5: Human-Like Behavior
- [ ] Random delays, activity windows
- [ ] Content variety
- [ ] Selective engagement
- [ ] Session memory

### Phase 6: Scheduling & Autonomy
- [ ] Scheduled operation
- [ ] Trend detection
- [ ] Daily caps & safety limits
- [ ] Error recovery

---

## Environment Variables (`.env`)

```bash
# LLM Server (vision model)
LLM_BASE_URL=http://localhost:8080/v1
LLM_MODEL=gemma-4-e3b-qat

# Twitter Browser Session
TWITTER_USERNAME=
TWITTER_PASSWORD=
TWITTER_EMAIL=  # In case Twitter asks for verification
BROWSER_HEADLESS=false  # Debug with visible browser

# Behavior Settings
MIN_DELAY_SECONDS=5
MAX_DELAY_SECONDS=30
ACTIVE_HOURS_START=8
ACTIVE_HOURS_END=22
MAX_TWEETS_PER_SESSION=5
MAX_LIKES_PER_SESSION=20

# Persona
DEFAULT_PERSONA=tech_enthusiast
```

---

## Dependencies

```
playwright>=1.52.0
requests>=2.31.0
python-dotenv>=1.0.0
Pillow>=10.0.0
```

---

## Usage

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Configure
cp .env.example .env
# Edit .env with your Twitter credentials and preferences

# Run the bot
python main.py

# Run with specific persona
python main.py --persona tech_enthusiast --headless
```

---

## Safety & Compliance

1. **Respect robots.txt**: Twitter's ToS prohibits automation - this is for educational/research use
2. **Rate Limits**: Random delays 5-30s between actions, daily caps
3. **Content Policy**: LLM generates content within Twitter's rules
4. **Session Safety**: Browser session persistence via cookies (avoid re-login)
5. **Error Recovery**: Handle CAPTCHAs, login prompts, rate limit blocks
6. **Account Safety**: Use a burner account initially
7. **No Spam**: Implement cooldowns, per-session caps
