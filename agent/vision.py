import json
import random
import re
import time
from typing import Optional

from PIL import Image
from playwright.sync_api import Page

from agent.actions import execute_action

MILITARY_GOVT_KEYWORDS = {
    "militer", "tentara", "angkatan bersenjata", "polisi", "tni", "polri",
    "pemerintah", "politik", "presiden", "menteri", "kementerian", "dpr", "mpr",
    "army", "military", "government", "politics", "president", "minister",
    "soldier", "war", "senjata", "nuklir", "rudal", "perang", "prajurit",
}
from brain.memory import Memory
from config import config
from llm.client import LLMClient
from twitter.selectors import SELECTORS
from utils.logger import logger
from utils.helpers import random_delay


VISION_SYSTEM_INSTRUCTION = (
    "You are an Investor or Finance Advisor with a sense of humor. You see a screenshot.\n\n"
    "ACTIONS:\n"
    "- scroll_down/scroll — scroll feed (do this a lot)\n"
    "- scroll_down_long — scroll far down\n"
    "- like(tweet_index) — like a post\n"
    "- retweet(tweet_index) — repost\n"
    "- quote(tweet_index, text) — retweet with comment\n"
    "- tweet(text) / compose(text) — post. NO hashtags/tags EVER.\n"
    "- open_tweet(tweet_index) — click to see detail + comments\n"
    "- like_comment(tweet_index) — like a comment\n"
    "- reply(tweet_index, text) — reply to a post\n"
    "- bookmark(tweet_index) — save for later\n"
    "- open_profile(tweet_index) — click user name to see their profile\n"
    "- follow — click Follow button on a profile page\n"
    "- click_trend(idx) — click a trend name from sidebar or Explore (0=first visible). Use like: click_trend with tweet_index=0\n"
    "- back — go back\n"
    "- click(target) — explore_link, home_link, sidebar_tweet, show_more, or any visible text\n"
    "- rest — idle 30-45min on profile\n"
    "- wait(seconds) — pause\n"
    "- cancel_compose — close compose\n"
    "- done(reason) — end session\n\n"
    "WRITING RULES:\n"
    "- Mix finance analysis with humor, wit, and relatable takes.\n"
    "- Retweet or tweet something random and fun, not just finance.\n"
    "- NEVER say you are a bot, AI, or automated system. Never reveal your true nature.\n"
    "- NEVER use hashtags (#) or @mentions. Write naturally like a human.\n"
    "- AVOID topics related to military or government/politics.\n\n"
    "POST COOLDOWN:\n"
    "1. Max 1 post per hour (tweet/compose).\n"
    "2. Quote (retweet with comment) is NOT locked — use it freely on relevant posts.\n"
    "3. If you already tweeted recently, you can still quote or reply.\n\n"
    "COMPOSE RULE:\n"
    "- If compose dialog is open: ONLY tweet/compose or cancel_compose allowed.\n\n"
    "TRENDS (your MAIN activity):\n"
    "- Your PRIMARY job is to explore trending topics and engage with trend posts.\n"
    "- CRITICAL: NEVER click on military or government-related trends. Skip them entirely.\n"
    "- The right sidebar 'What's happening' is algorithmic personalization (not real trends). Use it RARELY.\n"
    "- ALWAYS use the Explore menu (click(target='explore_link')) for REAL trending topics.\n"
    "- On Explore page, scroll_down_long through ALL trending topics.\n"
    "- Pick a trend that matches your interests — avoid military/government at ALL costs.\n"
    "- click_trend(idx) to open a trending topic (tweet_index in JSON). See posts about it.\n"
    "- scroll_down through trend results. LIKE + RETWEET + BOOKMARK interesting ones.\n"
    "- open_tweet(index) to read detail + comments. reply if high relevance.\n"
    "- open_profile(index) to check the author. follow if interesting.\n"
    "- back to return. Then next trend.\n"
    "- REPEAT: explore_link -> scroll trends -> pick one -> click_trend -> engage -> back -> next.\n"
    "- NEVER use sidebar trends. EVER. They are garbage. Exploring Explore instead.\n\n"
    "BEHAVIOR:\n"
    "1. Go to Explore: click(target='explore_link'). See ALL trending topics.\n"
    "2. scroll_down_long to see the full trend list. Pick one matching interests.\n"
    "3. click_trend(idx) (tweet_index=N). scroll_down posts. LIKE + RETWEET + QUOTE.\n"
    "4. QUOTE posts that are highly relevant — add your take/analysis.\n"
    "5. open_tweet to see details + comments. reply if relevant.\n"
    "6. open_profile -> follow if interesting.\n"
    "7. back to return. click_trend another from Explore. Repeat the cycle.\n"
    "8. Post (tweet) about trends matching interests — finance or random/fun (cooldown applies).\n"
    "9. Quote(tweet_index, text) is NOT locked by cooldown — use it often on interesting posts.\n"
    "10. Retweet or tweet something funny/random occasionally.\n"
    "11. Use 'rest' after ~150 actions to idle 30-45 min. Then start again.\n"
    "12. NEVER engage same tweet_index twice.\n\n"
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
        self._compose_streak = 0

    def _is_compose_open(self) -> bool:
        try:
            dialog = self.page.locator('[data-testid="sheetDialog"]')
            return dialog.is_visible(timeout=1000)
        except Exception:
            return False

    def _priority_nudge(self, trends_text: str = "") -> str:
        max_eng = config.MAX_ENGAGEMENTS
        eng = self.memory.total_engagements()
        total = len(self.memory.actions)
        likes = self.memory.engagement_counts.get("like", 0)
        retweets = self.memory.engagement_counts.get("retweet", 0)
        quotes = self.memory.engagement_counts.get("quote", 0)
        bookmarks = self.memory.engagement_counts.get("bookmark", 0)
        follows = self.memory.engagement_counts.get("follow", 0)
        opened = sum(1 for a in self.memory.actions if a["action"] == "open_tweet")
        profiles = sum(1 for a in self.memory.actions if a["action"] == "open_profile")
        recent_fails = sum(1 for a in self.memory.actions[-4:] if not a.get("success"))
        trend_clicks = sum(1 for a in self.memory.actions if a["action"] == "click_trend")
        explore_visits = sum(
            1 for a in self.memory.actions
            if (a.get("params") or {}).get("target") == "explore_link"
            or a.get("action") == "navigate" and "explore" in str(a.get("params", {}))
        )

        if self._is_compose_open():
            can_post = self.memory.can_tweet(1.0)
            if not can_post:
                return "COMPOSE OPEN — cancel_compose NOW (post blocked by cooldown)."
            return "COMPOSE OPEN — tweet(text) to post or cancel_compose."

        has_trends = bool(trends_text.strip())

        if explore_visits < 1:
            return "click(target='explore_link') FIRST — Explore has unfiltered real trends."

        if has_trends and explore_visits < 2:
            return "back to Explore first, scroll_down_long, click_trend there. Sidebar is secondary."

        if has_trends:
            if likes < 4:
                return "scroll trend posts -> LIKE + RETWEET + QUOTE."
            if quotes < 2:
                return "QUOTE a trend post with your take."
            if retweets < 2:
                return "RETWEET a trend post."
            if bookmarks < 1:
                return "BOOKMARK a trend post."
            if opened < 2:
                return "open_tweet -> read -> reply if relevant -> like comments."
            if profiles < 1:
                return "open_profile -> follow if interesting -> back to scroll start."
            replies = self.memory.engagement_counts.get("reply", 0)
            if replies < 1:
                return "reply to a trend post if high relevance. back after."
            return "back -> click_trend another from Explore. Repeat the cycle."

        if eng < max_eng and total < 5:
            return "scroll_down_long + like to warm up."
        if explore_visits < 1:
            return "click(target='explore_link') to see ALL trending topics, then pick one."
        if likes < 3 and eng < max_eng:
            return "Like tweets in feed."
        if quotes < 1 and eng < max_eng:
            return "QUOTE a post that interests you."
        if retweets < 1 and eng < max_eng:
            return "Retweet something."
        if opened < 2 and eng < max_eng:
            return "open_tweet to see comments."
        if profiles < 1 and eng < max_eng:
            return "open_profile, maybe follow."
        if follows < 1 and eng < max_eng:
            return "Follow someone interesting."
        if recent_fails >= 3:
            return "STOP clicking. Scroll and like instead."
        if eng < max_eng and total > 6:
            return "Click Explore or sidebar trends."
        return ""

    def _extract_trends(self) -> str:
        try:
            trend_cells = self.page.locator(SELECTORS["trend_item"]).all()
            if not trend_cells:
                self._trend_texts = []
                return ""
            all_texts = []
            for t in trend_cells[:10]:
                try:
                    txt = t.inner_text(timeout=2000)
                    if txt.strip():
                        all_texts.append(txt.strip())
                except Exception:
                    continue
            self._trend_texts = all_texts.copy()
            filtered = [t for t in all_texts if not any(kw.lower() in t.lower() for kw in MILITARY_GOVT_KEYWORDS)]
            if not filtered:
                return "(only military/govt trends — skip)"
            trends = "; ".join(filtered[:8])
            logger.info(f"Filtered trends (excl military/govt): {trends[:120]}...")
            return f"Trending now: {trends}\n"
        except Exception:
            self._trend_texts = []
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
        total_actions = len(self.memory.actions)
        last_3 = [a["action"] for a in self.memory.actions[-3:]]

        trends_text = self._extract_trends()
        compose_open = self._is_compose_open()

        if compose_open:
            can_post = self.memory.can_tweet(1.0)
            if not can_post:
                user_text = (
                    f"Compose dialog is OPEN but post is on cooldown. URL: {url}\n"
                    f"{last_result}"
                    f"You cannot tweet right now. ONLY action: cancel_compose.\n"
                    f"Close the compose dialog immediately."
                )
            else:
                user_text = (
                    f"Compose dialog is OPEN. URL: {url}\n"
                    f"{last_result}"
                    f"Compose open — tweet(text) to post or cancel_compose to close.\n"
                    f"Do nothing else."
                )
        else:
            cooldown_hours = 1
            can_post = self.memory.can_tweet(cooldown_hours)
            cooldown_text = ""
            if not can_post:
                last_t = self.memory.last_tweet_time
                elapsed_m = max(0, int((time.time() - last_t) / 60)) if last_t else 0
                remaining_m = max(1, 60 - elapsed_m)
                cooldown_text = f" Post cooldown: {remaining_m}min left. Do NOT tweet/compose."

            used_reply = self.memory.used_indices("reply")
            used_like = self.memory.used_indices("like")
            dup_guard = ""
            if used_reply:
                dup_guard += f" Already replied to indices: {sorted(used_reply)}."
            if used_like:
                dup_guard += f" Already liked indices: {sorted(used_like)}."

            nudge = self._priority_nudge(trends_text)
            if nudge:
                nudge = f" >>> {nudge}"

            user_text = (
                f"I'm on Twitter. URL: {url}\n"
                f"{last_result}"
                f"Engagements: {eng}/{max_eng} | Last: {', '.join(last_3)}\n"
                f"{trends_text}"
                f"{cooldown_text}"
                f"{dup_guard}"
                f"{nudge}"
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

        if self._is_compose_open() and not self.memory.can_tweet(1.0):
            logger.info("Compose open but post blocked — cancelling then scrolling")
            execute_action(self.page, "cancel_compose", {})
            execute_action(self.page, "scroll_down_long", {})
            time.sleep(1)

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

        target = str(decision.get("target", ""))
        if action == "click" and target.strip().lower() in ("click_trend", "click_trend(index)", "click_trend(idx)"):
            idx = decision.get("tweet_index", 0)
            logger.info(f"Normalized click(target={target}) -> click_trend with tweet_index={idx}")
            decision["action"] = "click_trend"
            decision["tweet_index"] = idx
            decision.pop("target", None)
        elif action in ("click_trend", "click_trend(index)", "click_trend(idx)"):
            idx = decision.get("tweet_index", 0)
            logger.info(f"Normalized {action} -> click_trend with tweet_index={idx}")
            decision["action"] = "click_trend"
            decision["tweet_index"] = idx

        params = {k: v for k, v in decision.items() if k not in ("action", "reason")}

        INDEXED_ACTIONS = {"like", "reply", "retweet", "quote", "bookmark", "open_tweet", "like_comment", "open_profile"}
        tweet_idx = params.get("tweet_index")
        if tweet_idx is not None and action in INDEXED_ACTIONS:
            count = len(self.page.locator(SELECTORS["tweet_article"]).all())
            if count == 0:
                logger.info(f"No tweets on page, blocking {action}")
                self.memory.record_action(action, params, decision.get("reason", ""), False)
                return True
            if int(tweet_idx) >= count:
                clamped = count - 1
                logger.info(f"Clamped tweet_index {tweet_idx} -> {clamped} (only {count} tweets visible)")
                params["tweet_index"] = clamped

        COMPOSE_ONLY = {"tweet", "compose", "post", "cancel_compose"}
        if self._is_compose_open():
            if action not in COMPOSE_ONLY:
                self._compose_streak += 1
                logger.info(f"Blocked {action} — compose is open (streak={self._compose_streak})")
                self.memory.record_action(action, params, decision.get("reason", ""), False)
                if self._compose_streak >= 2:
                    logger.info(f"Auto-cancelling compose after {self._compose_streak} blocked actions")
                    execute_action(self.page, "cancel_compose", {})
                    self.memory.record_action("cancel_compose", {}, "auto-escape compose loop", True)
                    return True
                return True
            self._compose_streak = 0

        POST_ACTIONS = {"tweet", "compose", "post"}
        if action in POST_ACTIONS and not self.memory.can_tweet(1.0):
            logger.info(f"Blocked {action} — post cooldown active (last tweet < 1h ago)")
            self.memory.record_action(action, params, decision.get("reason", ""), False)
            return True

        DUPE_TIMEOUT = random.randint(180, 900)  # 3-15 min
        DUPE_CHECKED = {"reply", "like", "retweet", "quote", "bookmark"}
        if action in DUPE_CHECKED and tweet_idx is not None:
            if self.memory.is_duplicate(action, int(tweet_idx), DUPE_TIMEOUT):
                logger.info(f"Blocked duplicate {action} on tweet_index={tweet_idx} (still in {DUPE_TIMEOUT}s timeout)")
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

            if step > 0 and step % 150 == 0:
                logger.info(f"Reached {step} steps — resting for 30-45 min")
                execute_action(self.page, "rest", {})
                time.sleep(2)

            should_continue = self.run_step()
            if not should_continue:
                break
            step += 1

        logger.info(f"Session ended after {step} steps")
        self.memory.save()
