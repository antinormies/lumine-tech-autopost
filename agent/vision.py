import json
import re
import time
from typing import Optional

from PIL import Image
from playwright.sync_api import Page

from agent.actions import execute_action
from brain.memory import Memory
from config import config
from llm.client import LLMClient
from utils.logger import logger
from utils.helpers import random_delay


VISION_SYSTEM_INSTRUCTION = (
    "You are a real human scrolling Twitter. You see a screenshot with visible tweets.\n\n"
    "ACTIONS you can use:\n"
    "- scroll_down / scroll — scroll feed (do this 5-15+ times)\n"
    "- like(tweet_index) — LIKE. DO THIS A LOT (0=first)\n"
    "- retweet(tweet_index) — RETWEET interesting content\n"
    "- quote(tweet_index, text) — QUOTE with your comment\n"
    "- tweet(text) — POST. ABSOLUTELY NO HASHTAGS OR TAGS.\n"
    "- bookmark(tweet_index) — save\n"
    "- click(target) — ONLY sidebar_tweet\n"
    "- cancel_compose — close compose\n"
    "- done(reason) — end\n\n"
    "CRITICAL: NEVER write hashtags (#) or @mentions in ANY text. "
    "Write naturally like a normal person talking. "
    "Example: say 'IHSG looking weak' NOT 'IHSG looking weak #stocks'.\n\n"
    "RULES:\n"
    "1. LIKE tweets OFTEN — multiple per session.\n"
    "2. RETWEET content worth sharing.\n"
    "3. QUOTE interesting tweets with your take.\n"
    "4. POST original thoughts (NO hashtags).\n"
    "5. SCROLL a LOT between actions.\n"
    "6. NEVER click on usernames or navigate away.\n\n"
    "Respond ONLY with JSON:\n"
    '{"action": "...", "reason": "why you chose this", "target": "...", "text": "...", "tweet_index": 0, "amount": 600, "seconds": 5}'
)


class VisionAgent:
    def __init__(self, page: Page, llm: LLMClient, system_prompt: str):
        self.page = page
        self.llm = llm
        self.memory = Memory()
        self.system_prompt = system_prompt
        self.full_prompt = f"{system_prompt}\n\n{VISION_SYSTEM_INSTRUCTION}"

    def capture_screenshot(self) -> Optional[Image.Image]:
        try:
            png_data = self.page.screenshot(type="png")
            from io import BytesIO
            return Image.open(BytesIO(png_data))
        except Exception as e:
            logger.warning(f"Screenshot failed: {e}")
            return None

    def decide_action(self) -> Optional[dict]:
        screenshot = self.capture_screenshot()
        if screenshot is None:
            return None
        try:
            url = self.page.url
        except Exception:
            url = "unknown (page closed)"
        last_action = self.memory.last_action()
        last_result = ""
        if last_action:
            status = "succeeded" if last_action.get("success") else "FAILED"
            last_result = f"Last action: {last_action['action']} ({status})\n"

        max_eng = config.MAX_ENGAGEMENTS
        eng = self.memory.total_engagements()
        recent = self.memory.recent_summary(3)
        total_actions = len(self.memory.actions)
        last_3_actions = [a["action"] for a in self.memory.actions[-3:]]
        has_posted = self.memory.engagement_counts.get("tweet", 0)
        has_retweeted = self.memory.engagement_counts.get("retweet", 0)
        has_quoted = self.memory.engagement_counts.get("quote", 0)

        post_suggestion = ""
        if total_actions > 2 and has_posted < 1 and eng < max_eng:
            post_suggestion = " POST something!"
        elif total_actions > 5 and has_posted < 3 and eng < max_eng:
            post_suggestion = " Post another!"

        like_count = self.memory.engagement_counts.get("like", 0)
        retweet_count = self.memory.engagement_counts.get("retweet", 0)
        quote_count = self.memory.engagement_counts.get("quote", 0)
        reply_count = self.memory.engagement_counts.get("reply", 0)
        total_engage = like_count + retweet_count + quote_count + reply_count

        engage_nudge = ""
        if total_engage == 0 and total_actions > 3 and eng < max_eng:
            engage_nudge = " LIKE or RETWEET a visible tweet NOW."
        elif total_engage < 2 and total_actions > 5 and eng < max_eng:
            engage_nudge = " LIKE or RETWEET something visible!"
        elif total_engage < 4 and total_actions > 8 and eng < max_eng:
            engage_nudge = " LIKE or QUOTE a tweet you see!"

        composer_check = ""
        if "type" in last_3_actions and "tweet" not in last_3_actions:
            composer_check = " You've been typing manually. Use 'tweet' action instead."
        navigate_check = ""
        last_targets = [str((a.get("params") or {}).get("target") or "") for a in self.memory.actions[-3:]]
        bad_nav = any(kw in t.lower() for t in last_targets for kw in ("explore", "search", "notification", "message"))
        if "navigate" in last_3_actions or bad_nav:
            navigate_check = " STAY on feed."

        user_text = (
            f"I'm on Twitter. Current URL: {url}\n"
            f"{last_result}"
            f"Engagements: {eng}/{max_eng} | Last: {', '.join(last_3_actions)}\n"
            f"{post_suggestion}{engage_nudge}{composer_check}{navigate_check}"
            f"Look at screenshot. What next?"
        )

        response = self.llm.vision_chat(
            system_prompt=self.full_prompt,
            user_text=user_text,
            image=screenshot,
            temperature=0.8,
            max_tokens=512,
        )

        if not response:
            return None

        return self._parse_action(response.content)

    def _parse_action(self, text: str) -> Optional[dict]:
        decoder = json.JSONDecoder()
        idx = text.find("{")
        if idx == -1:
            logger.warning(f"No JSON found in response: {text[:100]}...")
            return None
        try:
            decision, _ = decoder.raw_decode(text, idx)
            action = decision.get("action")
            if not action:
                logger.warning("No action in decision")
                return None
            logger.info(f"Decision: {decision.get('reason', 'no reason')}")
            return decision
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse action JSON: {e}")
            return None

    def _page_alive(self) -> bool:
        try:
            self.page.url
            return True
        except Exception:
            return False

    def run_step(self) -> bool:
        if not self._page_alive():
            logger.warning("Page is no longer alive, stopping")
            return False
        decision = self.decide_action()
        if decision is None:
            logger.warning("Vision model unavailable or page closed, stopping")
            return False
        if not decision:
            logger.warning("No decision from vision model, waiting...")
            time.sleep(5)
            return True

        action = decision["action"]
        if action == "done":
            logger.info(f"Agent done: {decision.get('reason', '')}")
            return False

        params = {k: v for k, v in decision.items() if k not in ("action", "reason")}
        success = execute_action(self.page, action, params)

        self.memory.record_action(action, params, decision.get("reason", ""), success)
        if not success:
            logger.info(f"Action '{action}' failed, will adapt next step")

        delay = random_delay(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
        logger.debug(f"Delayed {delay:.1f}s after action")

        return True

    def run_session(self, max_steps: int = 30):
        self.page.goto("https://x.com/home", wait_until="domcontentloaded")
        time.sleep(4)
        logger.info("Starting vision agent session")

        step = 0
        while step < max_steps:
            logger.info(f"--- Step {step + 1}/{max_steps} ---")
            should_continue = self.run_step()
            if not should_continue:
                break
            step += 1

        logger.info(f"Session ended after {step} steps")
        self.memory.save()
