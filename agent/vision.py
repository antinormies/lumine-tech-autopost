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
    "You are a human browsing Twitter/X naturally. You see a screenshot of the page.\n\n"
    "Available actions:\n"
    "- click (target)\n"
    "- type (target, text)\n"
    "- scroll_down (amount in pixels)\n"
    "- scroll_up (amount in pixels)\n"
    "- navigate (url)\n"
    "- wait (seconds)\n"
    "- tweet (text)\n"
    "- like (tweet_index: 0-based)\n"
    "- reply (tweet_index, text)\n"
    "- retweet (tweet_index)\n"
    "- bookmark (tweet_index)\n"
    "- cancel_compose\n"
    "- done (reason)\n\n"
    "Target elements: tweet_compose, sidebar_tweet, like_button, reply_button, "
    "home_link, explore_link, bookmark_button\n\n"
    "BEHAVE LIKE A REAL HUMAN:\n"
    "- After every 1-2 scrolls, STOP and interact with a tweet (like, reply, or retweet)\n"
    "- Like tweets that interest you — this is the most common action\n"
    "- Reply to discussions with short, natural replies\n"
    "- Retweet content worth sharing\n"
    "- Post an original tweet occasionally\n"
    "- Vary what you do — don't repeat the same action\n"
    "- Take your time. Read before interacting.\n"
    "- NEVER scroll more than 2 times without engaging with something\n"
    "- Mix between Home feed and Explore page\n\n"
    "EXAMPLE of good variety:\n"
    "scroll → like → scroll → reply → scroll → like → tweet → scroll → retweet → like\n\n"
    "BAD pattern (DON'T do this):\n"
    "scroll → scroll → scroll → scroll → scroll → scroll (boring lurker!)\n"
    "IMPORTANT: Respond ONLY with JSON:\n"
    '{"action": "...", "reason": "...", "target": "...", "text": "...", "tweet_index": 0, "amount": 600, "seconds": 5}'
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
        can_engage = eng < max_eng

        user_text = (
            f"I'm on Twitter. Current URL: {url}\n"
            f"{last_result}"
            f"Engagements this session: {eng}/{max_eng} (can {'still engage' if can_engage else 'only browse'})\n"
            f"What should I do next? Look at the screenshot and decide.\n"
            f"Recent actions: {self.memory.recent_summary()}"
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
