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
from twitter.selectors import SELECTORS
from utils.logger import logger
from utils.helpers import random_delay


VISION_SYSTEM_INSTRUCTION = (
    "You are a real human on Twitter. You see a screenshot of the page.\n\n"
    "ACTIONS:\n"
    "- scroll_down/scroll — scroll feed (do this a lot)\n"
    "- scroll_down_long — scroll far down to load many posts\n"
    "- like(tweet_index) — like a post (0=first visible)\n"
    "- retweet(tweet_index) — repost\n"
    "- quote(tweet_index, text) — retweet with your comment\n"
    "- tweet(text) / compose(text) — post original thought. NO hashtags/tags EVER.\n"
    "- open_tweet(tweet_index) — click to see detail + comments\n"
    "- like_comment(tweet_index) — like a comment on detail page\n"
    "- reply(tweet_index, text) — reply to a post (keep it relevant)\n"
    "- bookmark(tweet_index) — save for later\n"
    "- back — go back to feed\n"
    "- click(target) — explore_link, home_link, or sidebar_tweet\n"
    "- rest — go to profile and idle 45-120min (do this periodically)\n"
    "- wait(seconds) — pause\n"
    "- cancel_compose — close compose\n"
    "- done(reason) — end session\n\n"
    "CRITICAL: NEVER use hashtags (#) or @mentions. Write naturally.\n\n"
    "POST COOLDOWN:\n"
    "1. You can only post (tweet/compose) once per hour minimum.\n"
    "2. If you already posted recently, do NOT try to post again.\n"
    "3. Instead scroll, like, reply, or use rest action.\n\n"
    "REST RULES:\n"
    "1. Periodically use the 'rest' action to idle on your profile.\n"
    "2. Rest mimics real human breaks (45 min - 2 hours).\n"
    "3. After rest, continue browsing normally.\n\n"
    "TREND RULES:\n"
    "1. Go to Explore (click explore_link) to see trending topics.\n"
    "2. Identify trends that match your interests (listed above).\n"
    "3. Post about those matching trends with your own analysis/opinion.\n"
    "4. If nothing matches, scroll_down_long to see more trends.\n"
    "5. Don't post about trends outside your interests.\n\n"
    "BEHAVIOR:\n"
    "1. Scroll feed naturally. Scroll is normal.\n"
    "2. LIKE posts you see — do this often.\n"
    "3. Click a post (open_tweet) to see details + comments.\n"
    "4. Scroll comments, like interesting ones (like_comment).\n"
    "5. RETWEET big or important info.\n"
    "6. POST about trends matching your interests (see TREND RULES) only if cooldown has passed.\n"
    "7. Browse Trends/Explore frequently — scroll through, like a few, post about what fits.\n"
    "8. Vary between feed and trends — don't do just one thing.\n"
    "9. Reply only when relevant. No unrelated replies.\n"
    "10. NEVER engage the same tweet_index twice. Check which indices are already used.\n"
    "11. Use 'rest' occasionally to seem human — especially after posting.\n\n"
    "Respond ONLY JSON:\n"
    '{"action": "...", "reason": "...", "target": "...", "text": "...", "tweet_index": 0, "amount": 600, "seconds": 5}'
)


class VisionAgent:
    def __init__(self, page: Page, llm: LLMClient, system_prompt: str):
        self.page = page
        self.llm = llm
        self.memory = Memory()
        self.system_prompt = system_prompt
        self.full_prompt = f"{system_prompt}\n\n{VISION_SYSTEM_INSTRUCTION}"

    def _extract_trends(self) -> str:
        try:
            url = self.page.url
            trend_cells = self.page.locator(SELECTORS["trend_item"]).all()
            if not trend_cells or "explore" not in url.lower():
                return ""
            texts = []
            for t in trend_cells[:10]:
                try:
                    txt = t.inner_text(timeout=2000)
                    if txt.strip():
                        texts.append(txt.strip())
                except Exception:
                    continue
            if texts:
                trends = "; ".join(texts[:8])
                logger.info(f"Extracted trends: {trends[:100]}...")
                return f"Trending now: {trends}\n"
        except Exception:
            pass
        return ""

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
        if total_engage == 0 and total_actions > 2 and eng < max_eng:
            engage_nudge = " PICK A TWEET AND LIKE IT NOW (like(tweet_index))."
        elif total_engage < 2 and total_actions > 4 and eng < max_eng:
            engage_nudge = " LIKE or RETWEET visible tweet NOW."
        elif total_engage < 3 and total_actions > 6 and eng < max_eng:
            engage_nudge = " RETWEET or QUOTE a tweet you see."
        elif total_engage < 5 and total_actions > 9 and eng < max_eng:
            engage_nudge = " Like or quote more tweets."

        opened_tweet = sum(1 for a in self.memory.actions if a["action"] == "open_tweet")
        commented_count = self.memory.engagement_counts.get("like_comment", 0)
        tweet_detail_nudge = ""
        if opened_tweet < 1 and total_actions > 3 and eng < max_eng:
            tweet_detail_nudge = " Open a tweet (open_tweet) to see comments!"

        recent_fails = sum(1 for a in self.memory.actions[-4:] if not a.get("success"))
        stop_clicking = ""
        if recent_fails >= 3:
            stop_clicking = " STOP clicking! Use like/retweet/quote/tweet instead."

        composer_check = ""
        if "type" in last_3_actions and "tweet" not in last_3_actions:
            composer_check = " You've been typing manually. Use 'tweet' action instead."
        navigate_check = ""
        last_targets = [str((a.get("params") or {}).get("target") or "") for a in self.memory.actions[-3:]]
        bad_nav = any(kw in t.lower() for t in last_targets for kw in ("explore", "search", "notification", "message"))
        if "navigate" in last_3_actions or bad_nav:
            navigate_check = " STAY on feed."

        trends_text = self._extract_trends()

        used_reply = self.memory.used_indices("reply")
        used_like = self.memory.used_indices("like")
        used_retweet = self.memory.used_indices("retweet")
        used_bookmark = self.memory.used_indices("bookmark")
        used_quote = self.memory.used_indices("quote")

        dup_guard = ""
        if used_reply:
            dup_guard += f" Already replied to indices: {sorted(used_reply)} — pick a different tweet."
        if used_like:
            dup_guard += f" Already liked indices: {sorted(used_like)} — pick a different tweet."

        cooldown_hours = 1
        can_post = self.memory.can_tweet(cooldown_hours)
        cooldown_text = ""
        if not can_post:
            last_t = self.memory.last_tweet_time
            elapsed_m = max(0, int((time.time() - last_t) / 60)) if last_t else 0
            remaining_m = max(1, 60 - elapsed_m)
            cooldown_text = f" Post cooldown: {remaining_m}min left. Do NOT tweet or compose."
            post_suggestion = ""

        user_text = (
            f"I'm on Twitter. Current URL: {url}\n"
            f"{last_result}"
            f"Engagements: {eng}/{max_eng} | Last: {', '.join(last_3_actions)}\n"
            f"{trends_text}"
            f"{cooldown_text}"
            f"{dup_guard}"
            f"{post_suggestion}{engage_nudge}{stop_clicking}{composer_check}{navigate_check}{tweet_detail_nudge}"
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
            time.sleep(2)
            return True

        action = decision["action"]
        if action == "done":
            logger.info(f"Agent done: {decision.get('reason', '')}")
            return False

        params = {k: v for k, v in decision.items() if k not in ("action", "reason")}

        POST_ACTIONS = {"tweet", "compose", "post"}
        if action in POST_ACTIONS and not self.memory.can_tweet(1.0):
            logger.info(f"Blocked {action} — post cooldown active (last tweet < 1h ago)")
            self.memory.record_action(action, params, decision.get("reason", ""), False)
            return True

        tweet_idx = params.get("tweet_index")
        DUPE_CHECKED = {"reply", "like", "retweet", "quote", "bookmark"}
        if action in DUPE_CHECKED and tweet_idx is not None:
            used = self.memory.used_indices(action)
            if int(tweet_idx) in used:
                logger.info(f"Blocked duplicate {action} on tweet_index={tweet_idx}")
                self.memory.record_action(action, params, decision.get("reason", ""), False)
                return True

        success = execute_action(self.page, action, params)

        self.memory.record_action(action, params, decision.get("reason", ""), success)
        if not success:
            logger.info(f"Action '{action}' failed, running fallback (click home or go home)")
            fallback_ok = execute_action(self.page, "click", {"target": "home_link"})
            if not fallback_ok:
                logger.info("Fallback click failed, navigating to home directly")
                execute_action(self.page, "navigate", {"url": "https://x.com/home"})
            self.memory.record_action("fallback_home", {}, "auto-fallback after failure", True)

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
