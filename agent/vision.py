import json
import random
import re
import time
from typing import Optional

from PIL import Image
from playwright.sync_api import Page

from agent.actions import execute_action
from brain.mastermind import Mastermind

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
    "- search_topic(text) — search for a topic, interact with results\n"
    "- rest — idle 30-45min on profile\n"
    "- wait(seconds) — pause\n"
    "- cancel_compose — close compose\n"
    "- done(reason) — end session\n\n"
    "WRITING RULES:\n"
    "- Mix finance analysis with humor, wit, and relatable takes.\n"
    "- Retweet or tweet something random and fun, not just finance.\n"
    "- NEVER say you are a bot, AI, or automated system. Never reveal your true nature.\n"
    "- NEVER use hashtags (#) or @mentions. Write naturally like a human.\n"
    "- AVOID topics related to military or government/politics.\n"
    "- Always frame responses POSITIVELY. Even for negative news, focus on silver linings, opportunities, and lessons.\n"
    "- Never doom-and-gloom.\n\n"
    "LANGUAGE RULES:\n"
    "- If replying to a post in Bahasa Indonesia, reply in Bahasa Indonesia.\n"
    "- If replying to a post in English, reply in English.\n"
    "- Match the language naturally — don't switch mid-reply.\n"
    "- Your own original tweets stay in English.\n\n"
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
    "BEHAVIOR (follow this priority):\n"
    "⚠️ WARNING: Scrolling 3+ times without interaction = WASTING your session.\n"
    "⚠️ WARNING: After 4 total actions, if you haven't visited Explore, you WILL be auto-redirected there.\n\n"
    "PHASE 1 — HOME FEED (brief warmup, max 3 actions):\n"
    "1. Scroll a little. Like 1-2 posts. Then IMMEDIATELY go to Explore.\n\n"
    "PHASE 2 — EXPLORE 'FOR YOU' TAB (main activity):\n"
    "2. click(target='explore_link') to go to Explore.\n"
    "3. click(target='For you') to see personalized trends.\n"
    "4. scroll_down_long through trend list. Pick interest-matching trends.\n"
    "5. click_trend(N) to open. Scroll posts. LIKE + RETWEET + BOOKMARK + QUOTE.\n"
    "6. open_tweet -> reply -> like comments. open_profile -> follow.\n"
    "7. back to Explore. Pick next trend. Repeat.\n"
    "8. After matching trends exhausted, switch to Trending tab.\n\n"
    "PHASE 3 — EXPLORE 'TRENDING' TAB:\n"
    "9. click(target='Trending') for real trending topics.\n"
    "10. Repeat same cycle: scroll -> pick -> click_trend -> engage -> back -> next.\n"
    "11. First pick interest-matching trends. Then any specific non-military/govt trend.\n\n"
    "PHASE 4 — SEARCH (when trends don't match):\n"
    "12. If no trends match your interests, search_topic('interest keyword').\n"
    "13. Pick keywords like 'AI', 'stocks', 'tech', 'music', etc.\n"
    "14. scroll_down_long through results. LIKE + RETWEET + BOOKMARK + QUOTE.\n"
    "15. open_tweet -> reply -> like comments. open_profile -> follow.\n"
    "16. Try different search terms to find fresh content.\n\n"
    "GENERAL RULES:\n"
    "17. Post about matching trends if cooldown allows.\n"
    "18. Quote is NOT locked — use it freely.\n"
    "19. Use 'rest' after ~150 actions. Then restart from Phase 2.\n"
    "20. NEVER engage same tweet_index twice.\n\n"
    "Respond ONLY JSON:\n"
    '{"action": "...", "reason": "...", "target": "...", "text": "...", "tweet_index": 0, "amount": 600, "seconds": 5}'
)


class VisionAgent:
    def __init__(self, page: Page, llm: LLMClient, system_prompt: str, mastermind_brief: str = "", mastermind: Optional[Mastermind] = None):
        self.page = page
        self.llm = llm
        self.memory = Memory()
        self.mastermind = mastermind
        self._mastermind_advice = ""
        self._last_checkin_step = 0
        self.system_prompt = system_prompt
        brief_block = f"\n\n═══ MASTERMIND STRATEGY ═══\n{mastermind_brief}\n════════════════════════\n\n" if mastermind_brief else ""
        self.full_prompt = f"{system_prompt}{brief_block}{VISION_SYSTEM_INSTRUCTION}"
        if mastermind_brief:
            logger.info(f"[ANALYST] Injected mastermind brief into system prompt ({len(mastermind_brief)} chars)")
        self._compose_streak = 0
        self._phase = "home"
        self._phase_steps = 0

    def _is_compose_open(self) -> bool:
        try:
            dialog = self.page.locator('[data-testid="sheetDialog"]')
            return dialog.is_visible(timeout=1000)
        except Exception:
            return False

    def _page_context(self) -> str:
        ctx = self._page_label()
        return f"[{self._phase.upper()} cluster: step {self._phase_steps}] {ctx}"

    def _page_label(self) -> str:
        if self._is_compose_open():
            return "📍 ACTIVE: Post compose dialog"

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
                    return "📍 ACTIVE: Explore > Trending tab"
                if "for you" in t:
                    return "📍 ACTIVE: Explore > For You tab"
            except Exception:
                pass
            return "📍 ACTIVE: Explore page"

        if home_sel:
            try:
                t = self.page.locator('[role="tab"][aria-selected="true"]').inner_text(timeout=1000).lower()
                if "for you" in t:
                    return "📍 ACTIVE: Home > For You tab"
                if "following" in t:
                    return "📍 ACTIVE: Home > Following tab"
            except Exception:
                pass
            return "📍 ACTIVE: Home feed"

        url = self._safe_url()
        if "/status/" in url:
            return "📍 ACTIVE: Tweet detail"
        if "/search?" in url:
            return "📍 ACTIVE: Search / Trend results"
        if url.startswith("https://x.com/") and url.count("/") == 2:
            return "📍 ACTIVE: Profile page"
        if "/home" in url or url in ("https://x.com", "https://twitter.com", ""):
            return "📍 ACTIVE: Home feed"
        if "explore" in url:
            return "📍 ACTIVE: Explore page"
        return f"📍 ACTIVE: Other ({url.split('/')[-1][:30]})"

    def _scroll_streak(self) -> int:
        streak = 0
        for a in reversed(self.memory.actions[-5:]):
            if a["action"] in ("scroll", "scroll_down", "scroll_down_long"):
                streak += 1
            else:
                break
        return streak

    def _mastermind_checkin(self, step: int) -> str:
        if not self.mastermind:
            return ""
        if step - self._last_checkin_step < config.MASTERMIND_CHECKIN_INTERVAL:
            return self._mastermind_advice
        self._last_checkin_step = step
        try:
            url = self.page.url
        except Exception:
            url = "unknown"
        recent = self.memory.actions[-6:]
        context = (
            f"Step {step} | URL: {url}\n"
            f"Phase: {getattr(self, '_phase', 'home')}/{getattr(self, '_phase_steps', 0)} | "
            f"Engagements: {self.memory.total_engagements()}/{config.MAX_ENGAGEMENTS}\n"
        )
        advice = self.mastermind.advise(context, recent)
        if advice:
            self._mastermind_advice = advice
            logger.info(f"[MASTERMIND] Check-in at step {step}: {advice[:100]}")
        return self._mastermind_advice

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
        tab_clicks = sum(
            1 for a in self.memory.actions
            if a["action"] == "click" and (a.get("params") or {}).get("target", "").lower() in ("for you", "trending")
        )
        searches = sum(1 for a in self.memory.actions if a["action"] == "search_topic")
        on_explore = "explore" in self._safe_url()

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

        # Phase 1: Home feed — cluster minimum 10 steps
        if not on_explore:
            if self._phase_steps < 10:
                if likes < 4:
                    return "scroll_down_long + LIKE interesting posts."
                if opened < 2:
                    return "open_tweet interesting posts, LIKE comments."
                if profiles < 1:
                    return "open_profile on interesting people."
            return f"Home cluster done ({self._phase_steps}/10). SWITCH TO EXPLORE — click(target='explore_link') NOW."

        # On Explore — Phases 2/3 — cluster minimum 15 steps
        if on_explore and self._phase_steps < 15:
            if tab_clicks < 1 and trend_clicks < 1:
                return "On Explore — click a tab first (click(target='For you') or click(target='Trending'))."
            if trend_clicks < 1:
                return "click_trend(0) — stop scrolling, click a trend."
            if tab_clicks < 2:
                return "After this trend, click(target='Trending') for real trends."

            # General trend engagement (within explore cluster)
            if has_trends:
                if likes < 5:
                    return "scroll trend posts -> LIKE + RETWEET + QUOTE."
                if quotes < 3:
                    return "QUOTE a trend post with your take."
                if retweets < 3:
                    return "RETWEET a trend post."
                if bookmarks < 2:
                    return "BOOKMARK a trend post."
                if opened < 3:
                    return "open_tweet -> read -> reply if relevant -> like comments."
                if profiles < 1:
                    return "open_profile -> follow if interesting."
                replies = self.memory.engagement_counts.get("reply", 0)
                if replies < 1:
                    return "reply to a trend post if high relevance."
                if searches < 2:
                    return "No matching trends left — search_topic('interest keyword')."
                return "click_trend another from Explore or search again."
            return "On Explore but no trends visible — click_trend(0) or search_topic('keyword')."

        # Explore cluster complete — switch back to Home
        if on_explore:
            return f"Explore cluster done ({self._phase_steps}/15). SWITCH BACK TO HOME — click(target='home_link') NOW."

        # Fallback engagement nudges (no trends visible)
        if eng < max_eng and total < 5:
            return "scroll_down_long + like to warm up."
        if explore_visits < 1:
            return "click(target='explore_link') to see trends."
        if likes < 3 and eng < max_eng:
            return "Like tweets in feed."
        if quotes < 1 and eng < max_eng:
            return "QUOTE a post."
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
        if searches < 1 and total > 10:
            return "search_topic('something interesting') for fresh content."
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

    def decide_action(self, step: int = 0) -> Optional[dict]:
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
                cooldown_text = f" Post cooldown: {remaining_m}min left. Do NOT tweet/compose."

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

        mastermind_advice = self._mastermind_checkin(step)
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
            f"{mastermind_advice}"
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
            if attempt == 0:
                user_text += "\nYou gave invalid JSON. Fix the formatting — valid JSON only."

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
            logger.info(f"[ANALYST] Action: {decision.get('action', '?')} | Reason: {decision.get('reason', 'no reason')}")
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

    def run_step(self, step: int = 0) -> bool:
        if not self._page_alive():
            logger.warning("Page is no longer alive, stopping")
            return False

        # Phase tracking
        on_explore = "explore" in self._safe_url()
        new_phase = "explore" if on_explore else "home"
        if new_phase != self._phase:
            self._phase = new_phase
            self._phase_steps = 1
            logger.info(f"Phase switched to {self._phase}")
        else:
            self._phase_steps += 1

        if self._is_compose_open() and not self.memory.can_tweet(1.0):
            logger.info("Compose open but post blocked — cancelling then scrolling")
            execute_action(self.page, "cancel_compose", {})
            execute_action(self.page, "scroll_down_long", {})
            time.sleep(1)

        decision = self.decide_action(step)
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

        target = str(decision.get("target", "")).strip()
        m = re.match(r"^click\s*\(\s*target\s*=\s*['\"]([^'\"]+)['\"]\s*\)$", target, re.IGNORECASE)
        if m:
            inner = m.group(1)
            logger.info(f"Parsed nested target '{target}' -> '{inner}'")
            decision["target"] = target = inner

        target_lower = target.lower()
        if action == "click" and "click_trend" in target_lower:
            idx = decision.get("tweet_index", 0)
            logger.info(f"Normalized click(target={target}) -> explore_link (LLM meant 'go to Explore')")
            decision["target"] = "explore_link"
        elif "click_trend" in action:
            idx = decision.get("tweet_index", 0)
            logger.info(f"Normalized {action} -> click_trend with tweet_index={idx}")
            decision["action"] = "click_trend"
            decision["tweet_index"] = idx

        url_lower = self._safe_url()
        if action == "click":
            if target_lower in ("trending", "for you") and "explore" not in url_lower:
                logger.info(f"Normalized click({target}) -> explore_link (not on Explore)")
                decision["target"] = "explore_link"
            elif target_lower in ("trending", "for you") and "explore" in url_lower:
                logger.info(f"On Explore — keeping click({target}) for tab")

        action = decision["action"]  # re-sync after normalizations

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

        FORCE_AFTER = 2
        explore_visits = sum(
            1 for a in self.memory.actions
            if (a.get("params") or {}).get("target") == "explore_link"
            or a.get("action") == "navigate" and "explore" in str(a.get("params", {}))
        )
        if explore_visits < 1 and len(self.memory.actions) >= FORCE_AFTER:
            logger.info(f"Blocked {action} — haven't visited Explore after {len(self.memory.actions)} actions. Force-navigating.")
            self.memory.record_action(action, params, decision.get("reason", ""), False)
            execute_action(self.page, "click", {"target": "explore_link"})
            self.memory.record_action("click", {"target": "explore_link"}, "auto-navigate to Explore", True)
            return True

        SCROLL_ACTIONS = {"scroll", "scroll_down", "scroll_down_long", "scroll_up"}
        trend_clicks = sum(1 for a in self.memory.actions if a["action"] == "click_trend")
        trending_visits = sum(
            1 for a in self.memory.actions
            if a["action"] == "click" and (a.get("params") or {}).get("target", "").lower() == "trending"
        )
        if "explore" in self._safe_url() and trend_clicks >= 2 and trending_visits < 1:
            logger.info("Blocked — trend engagement done but never clicked Trending tab. Force-switching.")
            self.memory.record_action(action, params, decision.get("reason", ""), False)
            execute_action(self.page, "click", {"target": "Trending"})
            self.memory.record_action("click", {"target": "Trending"}, "auto-switch to Trending tab", True)
            return True

        if action in SCROLL_ACTIONS and self._scroll_streak() >= 3:
            logger.info(f"Blocked scroll — streak={self._scroll_streak()}, forcing engagement")
            self.memory.record_action(action, params, decision.get("reason", ""), False)
            return True

        if action in SCROLL_ACTIONS and "explore" in self._safe_url() and trend_clicks < 1:
            logger.info("Blocked scroll on Explore — no trend clicked yet. Must click_trend first.")
            self.memory.record_action(action, params, decision.get("reason", ""), False)
            return True

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
                recent = [a for a in self.memory.actions[-5:] if a["action"] in DUPE_CHECKED and not a.get("success")]
                if len(recent) >= 2:
                    logger.info("Duplicate streak — forcing redirect to break loop")
                    execute_action(self.page, "click", {"target": "explore_link"})
                    self.memory.record_action("click", {"target": "explore_link"}, "auto-escape dupe loop", True)
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

            should_continue = self.run_step(step)
            if not should_continue:
                break
            step += 1

        logger.info(f"Session ended after {step} steps")
        self.memory.save()
