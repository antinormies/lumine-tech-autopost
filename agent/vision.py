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
    "- reply(tweet_index, text) — reply to a post (do this when you have something relevant to say)\n"
    "- bookmark(tweet_index) — save for later\n"
    "- open_profile(tweet_index) — click user name to see their profile\n"
    "- follow — click Follow button on a profile page\n"
    "- click_trend(idx) — click a trend name from sidebar or Explore (0=first visible). Use like: click_trend with tweet_index=0\n"
    "- back — go back\n"
    "- click(target) — explore_link, home_link, sidebar_tweet, show_more, or any visible text\n"
    "- search_topic(text) — search for a topic, interact with results, open profiles, follow\n"
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
    "KEY ACTIONS DURING SCROLLING:\n"
    "- LIKE every interesting post you see. Do this OFTEN.\n"
    "- REPLY when you see something interesting — share your take, opinion, or question.\n"
    "- Find an interesting post? open_profile(tweet_index) to check the author.\n"
    "- Like 2-3 of their tweets. Follow if relevant.\n"
    "- See a smart take or hot take? BOOKMARK it.\n"
    "- When something sparks curiosity: search_topic('keyword') to dive deeper.\n\n"
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
    "- On Explore page there are two tabs: 'For you' (personalized trends) and 'Trending' (real trends).\n"
    "- click(target='For you') or click(target='Trending') to switch tabs on Explore.\n"
    "- On each tab: scroll_down_long, pick a trend matching interests, click_trend, engage.\n\n"
    "BEHAVIOR (do these in repeatable clusters):\n"
    "⚠️ Scrolling 3+ times without interaction = WASTING your session.\n\n"
    "CLUSTER A — HOME FEED (10-20 steps):\n"
    "1. Scroll home feed. LIKE every interesting post. RETWEET + BOOKMARK too.\n"
    "2. open_tweet interesting posts. Read comments. LIKE comments.\n"
    "3. open_profile(tweet_index) on every interesting post — check their bio + tweets.\n"
    "4. LIKE 2-3 of their posts. Follow if relevant.\n"
    "5. QUOTE highly relevant posts with your take.\n"
    "6. Repeat steps 1-5 for ~10-20 actions. Then switch to Explore or Search.\n\n"
    "CLUSTER B — EXPLORE (15-20 steps):\n"
    "7. click(target='explore_link'). You see TREND TOPICS (links, not tweets). DO NOT scroll them.\n"
    "8. click(target='For you') tab. Pick interest-matching trend: click_trend(N).\n"
    "9. Scroll trend posts. LIKE + RETWEET + BOOKMARK + QUOTE heavily.\n"
    "10. open_tweet -> reply -> LIKE comments. open_profile on EVERY interesting post.\n"
    "11. open_profile(tweet_index) -> like 2-3 of their posts -> follow if relevant.\n"
    "12. back to Explore. click_trend(1). Repeat until For You trends exhausted.\n"
    "13. Then click(target='Trending') tab. Same cycle: click_trend(N) -> engage -> open_profile -> follow -> back -> next.\n"
    "14. After ~15-20 Explore steps, switch to Home (A) or Search (C).\n\n"
    "CLUSTER C — SEARCH (8-15 steps):\n"
    "15. Use search_topic('keyword') to search for specific interests (cats, AI, crypto, stocks, music, etc).\n"
    "16. The search box is at the top of X. It shows results — LIKE interesting posts.\n"
    "17. open_tweet interesting results. LIKE comments. Reply if relevant.\n"
    "18. open_profile on EVERY interesting person. LIKE 2-3 of their posts. Follow if relevant.\n"
    "19. search_topic('different keyword') to try another topic.\n"
    "20. Repeat 3-4 searches. Then switch back to Home (A) or Explore (B).\n\n"
    "21. Use 'rest' after ~150 total actions. Restart from Cluster A.\n"
    "22. NEVER engage same tweet_index twice.\n\n"
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
        self._post_blocks = 0
        self._detail_streak = 0
        self._phase: str = "home"
        self._phase_steps: int = 0

    def _is_compose_open(self) -> bool:
        try:
            dialog = self.page.locator('[data-testid="sheetDialog"]')
            return dialog.is_visible(timeout=1000)
        except Exception:
            return False

    def _page_context(self) -> str:
        cluster_label = f"[{self._phase.upper()} cluster: step {self._phase_steps}] "
        if self._is_compose_open():
            return cluster_label + "📍 ACTIVE: Post compose dialog"

        try:
            home_sel = self.page.locator('[data-testid="AppTabBar_Home_Link"][aria-selected="true"]').count() > 0
            explore_sel = self.page.locator('[data-testid="AppTabBar_Explore_Link"][aria-selected="true"]').count() > 0
        except Exception:
            home_sel = False
            explore_sel = False

        if explore_sel:
            try:
                t = self.page.locator('[role="tab"][aria-selected="true"]').inner_text(timeout=1000).lower()
                if "trending" in t:
                    return cluster_label + "📍 ACTIVE: Explore > Trending tab"
                if "for you" in t:
                    return cluster_label + "📍 ACTIVE: Explore > For You tab"
            except Exception:
                pass
            return cluster_label + "📍 ACTIVE: Explore page"

        if home_sel:
            try:
                t = self.page.locator('[role="tab"][aria-selected="true"]').inner_text(timeout=1000).lower()
                if "for you" in t:
                    return cluster_label + "📍 ACTIVE: Home > For You tab"
                if "following" in t:
                    return cluster_label + "📍 ACTIVE: Home > Following tab"
            except Exception:
                pass
            return cluster_label + "📍 ACTIVE: Home feed"

        url = self._safe_url()
        if "/status/" in url:
            return cluster_label + "📍 ACTIVE: Tweet detail"
        if "/search?" in url:
            return cluster_label + "📍 ACTIVE: Search / Trend results"
        if url.startswith("https://x.com/") and url.count("/") == 2:
            return cluster_label + "📍 ACTIVE: Profile page"
        if "/home" in url or url in ("https://x.com", "https://twitter.com", ""):
            return cluster_label + "📍 ACTIVE: Home feed"
        if "explore" in url:
            return cluster_label + "📍 ACTIVE: Explore page"
        return cluster_label + f"📍 ACTIVE: Other ({url.split('/')[-1][:30]})"

    def _scroll_streak(self) -> int:
        streak = 0
        for a in reversed(self.memory.actions[-5:]):
            if a["action"] in ("scroll", "scroll_down", "scroll_down_long"):
                streak += 1
            elif a.get("success") is False:
                continue  # blocked/failed actions don't break the streak
            else:
                break
        return streak

    def _priority_nudge(self, trends_text: str = "") -> str:
        max_eng = config.MAX_ENGAGEMENTS
        eng = self.memory.total_engagements()
        total = len(self.memory.actions)
        likes = self.memory.engagement_counts.get("like", 0)
        replies = self.memory.engagement_counts.get("reply", 0)
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
        tab_clicks = sum(
            1 for a in self.memory.actions
            if a["action"] == "click" and (a.get("params") or {}).get("target", "").lower() in ("for you", "trending")
        )
        searches = sum(1 for a in self.memory.actions if a["action"] == "search_topic")
        on_explore = "explore" in self._safe_url()
        on_search = "/search?" in self._safe_url()

        if self._is_compose_open():
            can_post = self.memory.can_tweet(1.0)
            if not can_post:
                return "COMPOSE OPEN — cancel_compose NOW (post blocked by cooldown)."
            return "COMPOSE OPEN — tweet(text) to post or cancel_compose."

        streak = self._scroll_streak()
        if streak >= 2:
            if on_explore:
                return f"STOP SCROLLING ({streak}x). click_trend(0) NOW."
            return f"STOP SCROLLING ({streak}x). like(0) or open_tweet(0) NOW."

        has_trends = bool(trends_text.strip())

        # ── On search results page ──
        if on_search:
            if likes < 4:
                return "Search results — LIKE posts as you scroll."
            if replies < 1:
                return "Reply to something interesting in search results."
            if profiles < 2:
                return "open_profile on interesting people — check + follow."
            if follows < 1 and profiles > 0:
                return "You opened a profile — follow if relevant."
            if opened < 2:
                return "open_tweet to see comments."
            if retweets < 1:
                return "RETWEET something in results."
            if quotes < 1:
                return "QUOTE a result with your take."
            if searches < 2:
                return "search_topic('different keyword') for more."
            return "search_topic another keyword or switch back to Home."

        # ── Cluster-aware nudge ──
        HOME_MIN, HOME_MAX = 10, 20
        EXPLORE_MIN, EXPLORE_MAX = 15, 20
        phase, steps = self._phase, self._phase_steps

        if phase == "home":
            if steps < HOME_MIN:
                if likes < 4:
                    return "scroll_down_long + LIKE posts as you scroll."
                if replies < 1:
                    return "Reply to a post that interests you."
                if profiles < 1:
                    return "open_profile(tweet_index) on an interesting post — check them out."
                if follows < 1 and profiles > 0:
                    return "You opened a profile — follow if they're relevant."
                if opened < 2:
                    return "open_tweet to see comments + like comments."
                if retweets < 1:
                    return "RETWEET something interesting."
                if quotes < 1:
                    return "QUOTE a post with your take."
                if bookmarks < 1:
                    return "BOOKMARK a post."
                if searches < 1:
                    return "Try search_topic('keyword') to find fresh content."
                return "scroll_down_long + like more posts."
            return "SWITCH TO EXPLORE. click(target='explore_link')."

        # Phase == "explore"
        if on_explore:
            if steps < EXPLORE_MIN:
                if tab_clicks < 1 and trend_clicks < 1:
                    return "On Explore — click a tab first (click(target='For you') or click(target='Trending'))."
                if trend_clicks < 1:
                    return "click_trend(0) — stop scrolling, click a trend."
                if likes < 6:
                    return "scroll trend posts -> LIKE + RETWEET + QUOTE."
                if replies < 2:
                    return "Reply to trend posts — share your take."
                if profiles < 2:
                    return "open_profile on interesting trend posts — check + follow."
                if follows < 1 and profiles > 0:
                    return "You opened a profile — follow if relevant."
                if opened < 3:
                    return "open_tweet -> reply -> like comments."
                if quotes < 3:
                    return "QUOTE a trend post with your take."
                if retweets < 3:
                    return "RETWEET a trend post."
                if bookmarks < 2:
                    return "BOOKMARK a trend post."
                if tab_clicks < 2:
                    return "After this trend, click(target='Trending') for real trends."
                if searches < 2:
                    return "Try search_topic('keyword') — search for specific topics instead."
                return "click_trend another from Explore."
            return "SWITCH BACK TO HOME. click(target='home_link')."
        else:
            # Explore phase but somehow not on Explore page
            if steps < EXPLORE_MIN:
                return "click(target='explore_link') — you should be on Explore."

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
        page_ctx = self._page_context()

        recent_fails = [a for a in self.memory.actions[-5:] if not a.get("success")]
        fail_summary = ""
        if recent_fails:
            fail_summary = " Recent FAILURES: " + ", ".join(
                f"{a['action']} idx={a.get('params', {}).get('tweet_index', '?')}" for a in recent_fails
            ) + "\n"

        if compose_open:
            can_post = self.memory.can_tweet(1.0)
            if not can_post:
                user_text = (
                    f"{page_ctx}\n"
                    f"Compose dialog is OPEN but post is on cooldown. URL: {url}\n"
                    f"{last_result}"
                    f"You cannot tweet right now. ONLY action: cancel_compose.\n"
                    f"Close the compose dialog immediately."
                )
            else:
                user_text = (
                    f"{page_ctx}\n"
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
                urgent = " STOP trying to tweet — it keeps getting blocked." if self._post_blocks > 0 else ""
                cooldown_text = f" Post cooldown: {remaining_m}min left. Do NOT tweet/compose.{urgent}"

        used_reply = self.memory.used_indices("reply")
        used_like = self.memory.used_indices("like")
        used_retweet = self.memory.used_indices("retweet")
        used_bookmark = self.memory.used_indices("bookmark")
        used_quote = self.memory.used_indices("quote")

        dup_guard = ""
        all_used: set[int] = set()
        for action_name, used_set in ("like", used_like), ("retweet", used_retweet), ("reply", used_reply), ("bookmark", used_bookmark), ("quote", used_quote):
            if used_set:
                sorted_used = sorted(used_set)
                dup_guard += f" Used({action_name}): {sorted_used}."
                all_used.update(used_set)

        if dup_guard:
            try:
                tweet_count = len(self.page.locator(SELECTORS["tweet_article"]).all())
            except Exception:
                tweet_count = 10
            free = [i for i in range(min(tweet_count, 10)) if i not in all_used]
            if free:
                dup_guard += f" Free indices: {free[:5]}. Try one of those."
            else:
                dup_guard += " All indices used. Scroll down for fresh tweets."

        nudge = self._priority_nudge(trends_text)
        if nudge:
            nudge = f" >>> {nudge}"

        user_text = (
            f"{page_ctx}\n"
            f"I'm on Twitter. URL: {url}\n"
            f"{last_result}"
            f"{fail_summary}"
            f"Engagements: {eng}/{max_eng} | Last: {', '.join(last_3)}\n"
            f"{trends_text}"
            f"{cooldown_text}"
            f"{dup_guard}"
            f"{nudge}"
        )

        for attempt in range(2):
            response = self.llm.vision_chat(
                system_prompt=self.full_prompt,
                user_text=user_text,
                image=screenshot,
                temperature=0.8,
                max_tokens=512,
            )
            if not response:
                return None
            parsed = self._parse_action(response.content)
            if parsed:
                return parsed
            logger.warning(f"Parse failed (attempt {attempt+1}/2): raw response={response.content[:200]}")
            if attempt == 0:
                user_text += (
                    f"\nYour JSON was malformed. Response received: {response.content[:150]}...\n"
                    f"Fix the JSON formatting. Respond ONLY with valid JSON like:\n"
                    f'{{"action": "like", "reason": "...", "tweet_index": 0}}'
                )

        return None

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

    def _safe_url(self) -> str:
        try:
            return self.page.evaluate("window.location.href").lower()
        except Exception:
            return ""

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

        target = str(decision.get("target", "")).strip().lower()
        url_lower = self._safe_url()
        on_explore = "explore" in url_lower

        if action == "click" and "click_trend" in target:
            idx = decision.get("tweet_index", 0)
            if on_explore:
                logger.info(f"On Explore — click(target={target}) -> click_trend with tweet_index={idx}")
                decision["action"] = "click_trend"
                decision["tweet_index"] = idx
                decision.pop("target", None)
            else:
                logger.info(f"Normalized click(target={target}) -> explore_link (not on Explore)")
                decision["target"] = "explore_link"
        elif "click_trend" in action:
            idx = decision.get("tweet_index", 0)
            logger.info(f"Normalized {action} -> click_trend with tweet_index={idx}")
            decision["action"] = "click_trend"
            decision["tweet_index"] = idx

        if action == "click":
            target = str(decision.get("target", "")).strip()
            target_lower = target.lower()
            if target_lower in ("trending", "for you") and not on_explore:
                if target_lower == "trending":
                    logger.info(f"Normalized click({target}) -> explore_link (Trending tab only exists on Explore)")
                    decision["target"] = "explore_link"
                else:
                    logger.info("For you tab exists on Home — keeping as-is")
            elif target_lower == "scroll":
                logger.info(f"Normalized click({target}) -> scroll_down")
                decision["action"] = "scroll_down"
                decision.pop("target", None)
            elif target_lower.isdigit():
                idx = int(target_lower)
                logger.info(f"Normalized click(target={target_lower}) -> click_trend with tweet_index={idx}")
                decision["action"] = "click_trend"
                decision["tweet_index"] = idx
                decision.pop("target", None)

        action = decision["action"]  # re-sync after normalizations

        # ── Cluster switch detection ──
        target = str(decision.get("target", "")).strip().lower()
        if action == "click" and target in ("explore_link", "explore"):
            if self._phase == "home" and self._phase_steps >= 10:
                logger.info(f"Cluster switch: home ({self._phase_steps} steps) -> explore")
                self._phase = "explore"
                self._phase_steps = 0
        elif (action == "click" and target in ("home_link", "home")) or action == "rest":
            if self._phase == "explore" and self._phase_steps >= 15:
                logger.info(f"Cluster switch: explore ({self._phase_steps} steps) -> home")
                self._phase = "home"
                self._phase_steps = 0

        self._phase_steps += 1

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

        SCROLL_ACTIONS = {"scroll", "scroll_down", "scroll_down_long", "scroll_up"}
        trend_clicks = sum(1 for a in self.memory.actions if a["action"] == "click_trend")
        current_url = self._safe_url()
        on_explore_page = "explore" in current_url
        trending_visits = sum(
            1 for a in self.memory.actions
            if a["action"] == "click" and (a.get("params") or {}).get("target", "").lower() == "trending"
        )
        if on_explore_page and trend_clicks >= 2 and trending_visits < 1:
            logger.info("Blocked — trend engagement done but never clicked Trending tab. Force-switching.")
            self.memory.record_action(action, params, decision.get("reason", ""), False)
            execute_action(self.page, "click", {"target": "Trending"})
            self.memory.record_action("click", {"target": "Trending"}, "auto-switch to Trending tab", True)
            return True

        if action in SCROLL_ACTIONS and self._scroll_streak() >= 3:
            logger.info(f"Blocked scroll — streak={self._scroll_streak()}, forcing engagement")
            self.memory.record_action(action, params, decision.get("reason", ""), False)
            return True

        if action in SCROLL_ACTIONS and on_explore_page and trend_clicks < 1:
            logger.info(f"Blocked scroll on Explore — no trend clicked yet (url={current_url[:50]}). Must click_trend first.")
            self.memory.record_action(action, params, decision.get("reason", ""), False)
            return True

        POST_ACTIONS = {"tweet", "compose", "post"}
        if action in POST_ACTIONS and not self.memory.can_tweet(1.0):
            self._post_blocks += 1
            logger.info(f"Blocked {action} — post cooldown active (last tweet < 1h ago) [block #{self._post_blocks}]")
            self.memory.record_action(action, params, decision.get("reason", ""), False)
            if self._post_blocks >= 2:
                logger.info("Auto-breaking post loop — forcing back + scroll to change context")
                execute_action(self.page, "back", {})
                execute_action(self.page, "scroll_down_long", {})
                self.memory.record_action("back", {}, "auto-escape post loop", True)
                self._post_blocks = 0
            return True

        DUPE_TIMEOUT = random.randint(180, 900)  # 3-15 min
        DUPE_CHECKED = {"reply", "like", "retweet", "quote", "bookmark"}
        if action in DUPE_CHECKED and tweet_idx is not None:
            if self.memory.is_duplicate(action, int(tweet_idx), DUPE_TIMEOUT):
                logger.info(f"Blocked duplicate {action} on tweet_index={tweet_idx} (still in {DUPE_TIMEOUT}s timeout)")
                self.memory.record_action(action, params, decision.get("reason", ""), False)
                recent = [a for a in self.memory.actions[-5:] if a["action"] in DUPE_CHECKED and not a.get("success")]
                if len(recent) >= 2:
                    logger.info("Duplicate streak — forcing redirect to break loop")
                    execute_action(self.page, "click", {"target": "explore_link"})
                    self.memory.record_action("click", {"target": "explore_link"}, "auto-escape dupe loop", True)
                return True

        success = execute_action(self.page, action, params)

        if success:
            self._post_blocks = 0

        # After clicking a trend, wait for page load + auto-scroll to load content
        if success and action == "click_trend":
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
                logger.info("Trend page loaded — auto-scrolling to reveal tweets")
                self.page.mouse.wheel(0, 600)
                time.sleep(1.5)
                self.page.mouse.wheel(0, 600)
            except Exception as e:
                logger.warning(f"Auto-scroll after click_trend failed: {e}")

        # Auto-escape tweet detail after 2+ actions without going back
        if "/status/" in self._safe_url() and action not in ("back", "done"):
            self._detail_streak += 1
            if self._detail_streak >= 2:
                logger.info(f"Auto-escaping tweet detail after {self._detail_streak} actions — forcing back")
                execute_action(self.page, "back", {})
                self.memory.record_action("back", {}, "auto-escape tweet detail loop", True)
                self._detail_streak = 0
                return True
        else:
            self._detail_streak = 0

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
