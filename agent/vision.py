import json
import random
import re
import time
from typing import Optional

from PIL import Image
from playwright.sync_api import Page

from agent.actions import execute_action
from brain.mastermind import Mastermind
from utils.finance_words import is_finance_related

MILITARY_GOVT_KEYWORDS = {
    "militer", "tentara", "angkatan bersenjata", "polisi", "tni", "polri",
    "pemerintah", "politik", "presiden", "menteri", "kementerian", "dpr", "mpr",
    "army", "military", "government", "politics", "president", "minister",
    "soldier", "war", "senjata", "nuklir", "rudal", "perang", "prajurit", "mbg", "prabowo",
    # NSFW / adult content
    "nsfw", "naked", "nude", "lust", "sexy", "hot", "porn", "sex", "seks",
    "telanjang", "bugil", "berahi", "nafsu", "bikini", "onlyfans",
    "vulgar", "erotis", "erotic", "intim", "intimate", "porno",
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
    "- not_interested(tweet_index) — mark as 'not interested' to train algorithm away from non-finance\n"
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
    "- AVOID topics related to military, government/politics, NSFW, or adult content.\n"
    "- PREFER engaging with FINANCE, FOREX, TRADING, and INVESTMENT posts.\n"
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
    "TRENDS:\n"
    "- Periodically check Explore for trending topics, but don't spend all your time there.\n"
    "- CRITICAL: NEVER click on military, government, or NSFW/adult trends. Skip them entirely.\n"
    "- CRITICAL: PREFER finance, forex, trading, and investment posts above all else.\n"
    "- On Explore page there are two tabs: 'For you' (personalized trends) and 'Trending' (real trends).\n"
    "- click(target='For you') or click(target='Trending') to switch tabs on Explore.\n"
    "- If no finance/forex/trading trends: search_topic instead.\n\n"
    "BEHAVIOR (follow this priority):\n"
    "⚠️ WARNING: Scrolling 3+ times without interaction = WASTING your session.\n\n"
     "PHASE 1 — HOME FEED (main activity, spend most of your time here):\n"
    "1. scroll_down_long through the feed. Scroll OFTEN (every 1-2 actions).\n"
    "2. Like(N) finance/forex posts. not_interested(N) on non-finance to train the algorithm.\n"
    "3. REPLY to finance/forex posts with your analysis — do this OFTEN (every few posts).\n"
    "4. open_tweet -> like comments -> reply. open_profile -> follow.\n"
    "5. RETWEET interesting finance posts — share good content with your followers.\n"
    "6. QUOTE a post with your insight — add your own take to trending content.\n"
    "7. BOOKMARK posts worth saving.\n"
    "8. Keep scrolling and engaging. RETWEET, QUOTE, REPLY more — likes are just the start.\n"
    "9. Occasionally tweet(text) an original thought — share your market take if cooldown allows.\n\n"
     "PHASE 2 — SEARCH (when home feed gets stale or you want targeted content):\n"
    "10. search_topic('keyword') — e.g. search_topic('trading'), search_topic('stocks'), search_topic('saham'), search_topic('crypto'). Vary your keywords.\n"
    "11. Use SHORT keywords (1-3 words). NOT full sentences.\n"
    "12. scroll_down_long through search results. LIKE + REPLY + RETWEET + BOOKMARK + QUOTE.\n"
    "13. STAY on search results. Do NOT go to Explore/trends from search.\n"
    "14. open_tweet -> reply -> like comments. open_profile -> follow.\n"
    "15. Try different search terms to find fresh content. REPLY often.\n\n"
    "PHASE 3 — EXPLORE (quick trend check, keep it brief):\n"
    "16. click(target='explore_link') to check trends quickly.\n"
    "17. Pick finance-related trends, click_trend(0), click_trend(1)... Engage fast: RETWEET, QUOTE, REPLY.\n"
    "18. If scrolling too much on Trending with no clear finance trend → go HOME immediately. Don't linger on Explore.\n"
    "19. If no finance trends, search_topic instead. Don't force trends.\n\n"
    "PHASE 4 — ROTATE BACK:\n"
    "20. After checking Explore, go back to Home or Search. Rotate between Home <-> Search.\n"
    "21. Keep scrolling and engaging. Home feed + Search should be 80% of your time.\n"
    "22. Occasionally tweet or quote about web research from Mastermind if cooldown allows.\n\n"
    "GENERAL RULES:\n"
    "23. Post about matching trends if cooldown allows — use web research from Mastermind.\n"
    "24. Quote is NOT locked — use it freely.\n"
    "25. REPLY to posts with your opinion — do this often. Reply is the most engaging action. PREFER replying to finance/forex/trading posts over buzz trending.\n"
    "26. NEVER engage your own posts. If you see your own content, skip it. Do not like/retweet/reply/quote it.\n"
    "27. Reply freely — no cooldown between comments.\n"
    "28. Use 'rest' after ~100 total actions. Then restart from Phase 1.\n"
    "29. NEVER engage same tweet_index twice.\n"
    "30. Click different trend indices (0, 1, 2, 3...) — don't always pick the first.\n"
    "31. search_topic is a GREAT way to find content. Vary keywords: trading, stocks, saham, investasi, crypto, gold, etc.\n"
    "32. PREFER replying to finance/forex/trading posts over general buzz trending. If a trend isn't finance-related, scroll past it and find one that is.\n"
    "33. When on SEARCH RESULTS: STAY there. scroll_down_long through results. LIKE, REPLY, open_tweet, open_profile. Do NOT click trends or go to Explore.\n"
    "34. Use not_interested(N) on non-finance posts to train the algorithm. Like(N) on finance posts.\n"
    "35. NO EMOJIS/EMOTICONS in any content. Use character expressions instead (e.g. :), :(, :D, ;), :p).\n"
    "36. Finance keywords: forex, stocks, trading, crypto, investment, economy, market, bank, fintech.\n"
    "    Also Indonesian finance terms: saham, investasi, reksadana, ihsg, bursa, rupiah.\n\n"
    "Respond ONLY JSON:\n"
    '{"action": "...", "reason": "...", "target": "...", "text": "...", "tweet_index": 0, "amount": 600, "seconds": 5}'
)


class VisionAgent:
    def __init__(self, page: Page, llm: LLMClient, system_prompt: str, mastermind_brief: str = "", mastermind: Optional[Mastermind] = None):
        self.page = page
        self._context = page.context
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
        self._used_trend_indices: set[int] = set()
        self._mastermind_directive = ""
        self._own_username: str | None = None
        try:
            link = page.locator('[data-testid="AppTabBar_Profile_Link"]')
            href = link.get_attribute("href")
            if href:
                self._own_username = href.strip("/")
                logger.info(f"[ANALYST] Own username: {self._own_username}")
        except Exception:
            pass

    def _on_own_profile(self) -> bool:
        if not self._own_username:
            return False
        url = self._safe_url()
        path = url.split("?")[0].rstrip("/")
        return path == f"https://x.com/{self._own_username}"

    def _search_options(self, count: int = 2) -> str:
        keywords = random.sample([
            "forex", "trading", "stocks", "crypto", "bitcoin", "investment",
            "saham", "investasi", "reksadana", "ihsg", "idx",
            "gold", "oil", "interest rates", "inflation",
            "stock market", "economic outlook", "market analysis",
            "commodities", "emerging markets",
        ], min(count, 3))
        return " or ".join(f"search_topic('{k}')" for k in keywords)

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
            return "📍 ACTIVE: Search / Trend results — ONLY scroll, like, reply, retweet, quote, bookmark, open_tweet, open_profile, follow, back, search_topic. NO trends/clicks."
        if self._on_own_profile():
            return "📍 ACTIVE: Own profile — DO NOT engage your own posts"
        if url.startswith("https://x.com/") and url.count("/") == 2:
            return "📍 ACTIVE: Other profile page"
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

    def _mastermind_checkin(self, step: int, trends_text: str = "") -> str:
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
        advice = self.mastermind.advise(context, recent, trends_text, MILITARY_GOVT_KEYWORDS)
        if advice:
            self._mastermind_advice = advice
            logger.info(f"[MASTERMIND] Check-in at step {step}: {advice[:120]}")
        return self._mastermind_advice

    def _feed_exhausted(self) -> bool:
        try:
            markers = [
                'text=You\'re all caught up',
                'text=You\'re caught up',
                'text=No more posts',
                'text=Show newer posts',
                '[data-testid="empty_state"]',
            ]
            for m in markers:
                if self.page.locator(m).first.is_visible(timeout=1000):
                    return True
        except Exception:
            pass
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
        replies = self.memory.engagement_counts.get("reply", 0)
        not_interested_count = self.memory.engagement_counts.get("not_interested", 0)
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
                if self._phase_steps > 5:
                    return f"STOP SCROLLING trends ({streak}x, step {self._phase_steps}). Go back Home — click(target='home_link')."
                free = [i for i in range(8) if i not in self._used_trend_indices]
                if not free:
                    return f"STOP SCROLLING ({streak}x). scroll_down_long to load more trends."
                return f"STOP SCROLLING ({streak}x). click_trend({free[0]}) NOW."
            exhausted = self._feed_exhausted()
            if exhausted:
                return f"FEED EXHAUSTED ({streak}x scrolls). {self._search_options()} or click(target='explore_link') for fresh content."
            return f"STOP SCROLLING ({streak}x). like(0) or {self._search_options(1)}."

        has_trends = bool(trends_text.strip())

        # Search results: stay and engage, don't go back to trending
        on_search_results = "/search?" in self._safe_url()
        if on_search_results:
            if not_interested_count < 2:
                return "STAY on search results. not_interested(N) on non-finance posts, like(N) on finance/forex."
            if replies < 2:
                return "STAY on search results. REPLY to a finance/forex post — share your analysis."
            if retweets < 1:
                return "RETWEET an interesting post from search results."
            if quotes < 1:
                return "QUOTE a post with your insight."
            if likes < 3:
                return "Find a finance/forex post -> like(N). like(0) if it's finance, else not_interested(0)."
            if opened < 2:
                return "open_tweet -> like comments -> reply."
            if profiles < 2:
                return "open_profile on interesting people -> follow."
            if self.memory.can_tweet(1.0):
                return "Got an original take? tweet(text) to share. Else scroll more or search_topic('another keyword'). Stay on search."
            return "scroll more or search_topic('another keyword'). Stay on search."

        # Phase 1: Home feed — cluster minimum 25 steps, scroll + engage heavily
        if not on_explore:
            if self._phase_steps < 25:
                if not_interested_count < 3:
                    return "scroll_down_long -> not_interested(N) on non-finance, like(N) on finance. Scroll between posts."
                if likes < 3:
                    return "scroll_down_long -> like(N) finance/forex posts. Scroll past non-finance or not_interested(N)."
                if replies < 3:
                    return "REPLY to a finance post — share your analysis. Scroll and find one."
                if quotes < 2:
                    return "QUOTE a finance post with your take."
                if retweets < 2:
                    return "RETWEET a finance post."
                if opened < 3:
                    return "open_tweet -> like comments -> reply. Then scroll more."
                if bookmarks < 2:
                    return "BOOKMARK a post for later."
                if profiles < 2:
                    return "open_profile on interesting people -> follow."
                if searches < 2:
                    return f"search_topic('keyword') — {self._search_options(1)}. Vary your searches."
                if replies < 5:
                    return "REPLY again — the more replies the better. Find another post to comment on."
                if quotes < 4:
                    return "QUOTE another post — share your perspective."
                if retweets < 4:
                    return "RETWEET another interesting post."
                if likes < 6:
                    return "scroll more -> like(N) finance posts. Keep engaging home feed."
                if self.memory.can_tweet(1.0):
                    return "Got an insight? tweet(text) to share your take, or scroll more."
                return "scroll_down_long -> keep scrolling home feed. Reply, retweet, quote — keep engaging."
            if self.memory.can_tweet(1.0):
                return f"Home cluster done ({self._phase_steps}/25). Consider tweet(text) if you have a hot take, or search_topic/explore."
            return f"Home cluster done ({self._phase_steps}/25). Try search_topic('keyword') or click(target='explore_link') for a change."

        # Phase 3: Explore — quick trend check, keep it brief
        if on_explore and self._phase_steps < 10:
            if streak >= 2 and self._phase_steps > 5:
                return f"Too much scrolling on trends ({streak}x). Go back Home — click(target='home_link')."
            if tab_clicks < 1 and trend_clicks < 1:
                return "Quick check: click(target='For you') or click(target='Trending') for trends."
            if trend_clicks < 1:
                free = [i for i in range(8) if i not in self._used_trend_indices]
                if not free:
                    return "scroll_down_long to load more trends, then click one."
                return f"click_trend({free[0]}) — pick a trend quickly."
            if not_interested_count < 3 and likes > 1:
                return "not_interested(N) on non-finance trend posts."
            if likes < 2:
                return "like(N) on a FINANCE trend post. Quick check."
            if retweets < 1:
                return "RETWEET a trend post."
            if quotes < 1:
                return "QUOTE a trend post with your take."
            if replies < 1:
                return "REPLY to a finance/forex trend post."
            if searches < 1:
                return "search_topic('keyword') to find finance content after trends."
            return "Done with trends. click(target='home_link') to go back to Home or search_topic()."

        # Explore cluster complete — switch back to Home or Search
        if on_explore:
            return f"Explore done ({self._phase_steps}/10). Go back Home — click(target='home_link') or search_topic('keyword')."

        # Fallback engagement nudges (no trends visible)
        if eng < max_eng and total < 5:
            return "scroll_down_long + like to warm up."
        if total > 8 and searches < 1:
            return f"{self._search_options()} for targeted finance content."
        if replies < 2 and eng < max_eng:
            return "REPLY to a finance post — share your analysis."
        if quotes < 2 and eng < max_eng:
            return "QUOTE a post with your take."
        if retweets < 2 and eng < max_eng:
            return "Retweet something interesting."
        if likes < 4 and eng < max_eng:
            return "Scroll and like finance posts in feed."
        if opened < 2 and eng < max_eng:
            return "open_tweet to see comments."
        if profiles < 1 and eng < max_eng:
            return "open_profile, maybe follow."
        if follows < 1 and eng < max_eng:
            return "Follow someone interesting."
        if recent_fails >= 3:
            return "STOP clicking. Scroll and like instead."
        if self.memory.can_tweet(1.0) and total > 20:
            return "Share a thought? tweet(text) to post. Else scroll and engage."
        if eng < max_eng and total > 6:
            return "scroll_down_long or search_topic('keyword')."
        return "scroll_down_long through feed. Find finance posts to engage with."

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
        url_lower = url.lower()
        if "/search?" in url_lower:
            trends_text = ""  # no trends on search — LLM should focus on results
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

        mastermind_advice = self._mastermind_checkin(step, trends_text)

        directive_text = ""
        if self._mastermind_directive:
            directive_text = f" [MASTERMIND] {self._mastermind_directive}"
            self._mastermind_directive = ""  # clear after showing once

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
            f"{directive_text}"
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

    def _recover_page(self) -> bool:
        try:
            logger.info("Page may have crashed — creating new page")
            try:
                if not self.page.is_closed():
                    self.page.close()
            except Exception:
                pass
            self.page = self._context.new_page()
            self.page.set_default_timeout(30000)
            self.page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)
            logger.info("Page recovered successfully")
            return True
        except Exception as e:
            logger.warning(f"Page recovery failed: {e}")
        return False

    def _page_alive(self) -> bool:
        try:
            self.page.url
            return True
        except Exception:
            logger.warning("Page not alive — attempting recovery")
            return self._recover_page()

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

        # Normalize: action field contains full function call like click(target='...')
        func_match = re.match(r"^(\w+)\s*\((.+)\)$", action)
        if func_match:
            func_name = func_match.group(1)
            func_args = func_match.group(2)
            if func_name == "click" and "target=" in func_args:
                val = re.search(r"target\s*=\s*['\"]([^'\"]+)['\"]", func_args)
                if val:
                    logger.info(f"Parsed action '{action}' -> click target='{val.group(1)}'")
                    decision["action"] = "click"
                    decision["target"] = val.group(1)
            elif func_name in ("tweet", "compose", "post") and func_args:
                val = re.search(r"['\"]([^'\"]+)['\"]", func_args)
                if val:
                    logger.info(f"Parsed action '{action}' -> {func_name} with text")
                    decision["action"] = func_name
                    decision["text"] = val.group(1)
            elif func_name == "reply" and func_args:
                parts = [p.strip() for p in func_args.split(",")]
                idx_match = re.search(r"\d+", parts[0]) if parts else None
                text_match = re.search(r"['\"]([^'\"]+)['\"]", func_args) if len(parts) > 1 else None
                logger.info(f"Parsed action '{action}' -> reply with idx={idx_match.group(0) if idx_match else '?'}")
                decision["action"] = "reply"
                if idx_match:
                    decision["tweet_index"] = int(idx_match.group(0))
                if text_match:
                    decision["text"] = text_match.group(1)
            elif func_name == "search_topic" and func_args:
                val = re.search(r"['\"]([^'\"]+)['\"]", func_args)
                if val:
                    logger.info(f"Parsed action '{action}' -> search_topic('{val.group(1)}')")
                    decision["action"] = "search_topic"
                    decision["text"] = val.group(1)
            elif func_name == "click_trend":
                idx_match = re.search(r"\d+", func_args)
                decision["action"] = "click_trend"
                if idx_match:
                    decision["tweet_index"] = int(idx_match.group(0))
                logger.info(f"Normalized {action} -> click_trend with tweet_index={decision.get('tweet_index', 0)}")
            elif func_name == "not_interested":
                idx_match = re.search(r"\d+", func_args)
                decision["action"] = "not_interested"
                if idx_match:
                    decision["tweet_index"] = int(idx_match.group(0))
                logger.info(f"Normalized {action} -> not_interested with tweet_index={decision.get('tweet_index', 0)}")

        action = decision["action"]  # re-sync after function-call normalization

        target = str(decision.get("target", "")).strip()
        m = re.match(r"^click\s*\(\s*target\s*=\s*['\"]([^'\"]+)['\"]\s*\)$", target, re.IGNORECASE)
        if m:
            inner = m.group(1)
            logger.info(f"Parsed nested target '{target}' -> '{inner}'")
            decision["target"] = target = inner

        target_lower = target.lower()
        if target_lower == action:
            logger.info(f"Blocked {action}(target='{target}') — LLM used action name as target")
            rec_params = {k: v for k, v in decision.items() if k not in ("action", "reason")}
            self.memory.record_action(action, rec_params, decision.get("reason", ""), False)
            return True
        if action == "click" and "click_trend" in target_lower:
            idx = decision.get("tweet_index", 0)
            logger.info(f"Normalized click(target={target}) -> explore_link (LLM meant 'go to Explore')")
            decision["target"] = "explore_link"
        if action == "click" and re.match(r"idx[=_ ]\d+", target_lower):
            idx = int(re.search(r"\d+", target_lower).group(0))
            logger.info(f"Normalized click(target='{target}') -> click_trend with tweet_index={idx}")
            decision["action"] = "click_trend"
            decision["tweet_index"] = idx
            action = "click_trend"
        elif "click_trend" in action:
            idx = decision.get("tweet_index")
            if idx is None:
                free = [i for i in range(8) if i not in self._used_trend_indices]
                idx = free[0] if free else 0
                logger.info(f"click_trend without index — picking free index {idx} from {free}")
            else:
                idx = int(idx)
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

        if action in INDEXED_ACTIONS and self._on_own_profile():
            logger.info(f"Blocked {action} — on own profile, cannot engage own posts")
            self.memory.record_action(action, params, decision.get("reason", ""), False)
            return True

        if action == "reply":
            # Mastermind reply approval
            if self.mastermind:
                idx = int(tweet_idx) if tweet_idx is not None else 0
                post_text = ""
                author = "someone"
                try:
                    tweet_els = self.page.locator('[data-testid="tweetText"]').all()
                    if idx < len(tweet_els):
                        post_text = tweet_els[idx].inner_text(timeout=2000)[:300]
                except Exception:
                    pass
                try:
                    author_els = self.page.locator('[data-testid="User-Name"]').all()
                    if idx < len(author_els):
                        author = author_els[idx].inner_text(timeout=2000)[:50]
                except Exception:
                    pass

                last12 = self.memory.actions[-12:]
                ctx_parts = []
                for a in last12:
                    an = a["action"]
                    ap = a.get("params", {})
                    ar = a.get("reason", "")
                    if an in ("like", "retweet", "reply", "bookmark", "quote", "open_tweet"):
                        ctx_parts.append(f"{an}[idx={ap.get('tweet_index','?')}]: {ar[:60]}")
                    elif an == "search_topic":
                        ctx_parts.append(f"search_topic('{ap.get('text','')}'): {ar[:60]}")
                    elif an == "click_trend":
                        ctx_parts.append(f"click_trend({ap.get('tweet_index','?')})")
                    elif an in ("scroll_down", "scroll_down_long"):
                        ctx_parts.append(an)
                analyst_ctx = "; ".join(ctx_parts[-8:])

                approved, result = self.mastermind.approve_reply(
                    post_text=post_text, author=author,
                    analyst_context=analyst_ctx,
                    avoid_keywords=MILITARY_GOVT_KEYWORDS,
                )
                if not approved:
                    logger.info(f"Mastermind REJECTED reply: {result[:100]}")
                    self.memory.record_action(action, params, f"mastermind rejected: {result[:60]}", False)
                    if "BEST-TO-DO:" in result:
                        self._mastermind_directive = result.split("BEST-TO-DO:")[-1].strip()
                        logger.info(f"[MASTERMIND] Directive: {self._mastermind_directive}")
                    return True
                params["text"] = result
                decision["text"] = result
                logger.info(f"Mastermind APPROVED reply: {result[:100]}")

        if action == "click_trend" and tweet_idx is not None:
            idx = int(tweet_idx)
            if idx in self._used_trend_indices:
                free = [i for i in range(8) if i not in self._used_trend_indices]
                if free:
                    idx = free[0]
                    logger.info(f"Trend index {tweet_idx} already clicked — auto-correcting to {idx}")
                    params["tweet_index"] = idx
                    tweet_idx = idx
                else:
                    logger.info(f"Blocked trend index {idx} — already clicked. Free: {free}")
                    self.memory.record_action(action, params, decision.get("reason", ""), False)
                    return True
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

        # Hard block: on search results, only allow staying actions
        SEARCH_STAY = {"scroll", "scroll_down", "scroll_down_long", "scroll_up",
                       "like", "reply", "retweet", "quote", "bookmark",
                       "open_tweet", "like_comment", "open_profile", "follow",
                       "back", "search_topic", "wait", "rest", "done"}
        if "/search?" in self._safe_url() and action not in SEARCH_STAY:
            logger.info(f"Blocked {action} — on search results, must stay and engage")
            self.memory.record_action(action, params, "on search results, must stay and engage", False)
            return True

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
            exhausted = self._feed_exhausted()
            logger.info(f"Blocked scroll — streak={self._scroll_streak()}{', feed exhausted' if exhausted else ''}")
            if exhausted and "explore" not in self._safe_url():
                logger.info("Feed exhausted — redirecting to search")
                kw = random.choice(["forex", "trading", "stocks", "saham", "investasi", "gold", "bitcoin", "market"])
                self.memory.record_action(action, params, decision.get("reason", ""), False)
                execute_action(self.page, "search_topic", {"text": kw})
                self.memory.record_action("search_topic", {"text": kw}, "auto-search after feed exhausted", True)
                return True
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

        if action in POST_ACTIONS and self.mastermind:
            last12 = self.memory.actions[-12:]
            context_parts = []
            for a in last12:
                a_name = a["action"]
                a_params = a.get("params", {})
                a_reason = a.get("reason", "")
                if a_name in ("like", "retweet", "reply", "bookmark", "quote", "open_tweet"):
                    context_parts.append(f"{a_name}[idx={a_params.get('tweet_index','?')}]: {a_reason[:60]}")
                elif a_name == "search_topic":
                    context_parts.append(f"search_topic('{a_params.get('text','')}'): {a_reason[:60]}")
                elif a_name in ("scroll_down", "scroll_down_long", "scroll_up"):
                    context_parts.append(f"{a_name}")
                elif a_name == "click_trend":
                    context_parts.append(f"click_trend({a_params.get('tweet_index','?')})")
            analyst_ctx = "; ".join(context_parts[-10:])

            # Extract post texts the analyst engaged with
            post_texts = []
            try:
                tweet_els = self.page.locator('[data-testid="tweetText"]').all()
                for el in tweet_els[:5]:
                    try:
                        txt = el.inner_text(timeout=1000)
                        if txt.strip():
                            post_texts.append(txt.strip()[:200])
                    except Exception:
                        pass
            except Exception:
                pass

            trends = self._extract_trends()
            approved, result = self.mastermind.approve_post(
                trends_text=trends or "",
                post_texts=post_texts,
                analyst_context=analyst_ctx,
                avoid_keywords=MILITARY_GOVT_KEYWORDS,
            )
            if not approved:
                logger.info(f"Mastermind REJECTED post: {result[:100]}")
                self.memory.record_action(action, params, f"mastermind rejected: {result[:60]}", False)
                # Extract BEST-TO-DO directive from rejection
                self._mastermind_directive = ""
                if "BEST-TO-DO:" in result:
                    self._mastermind_directive = result.split("BEST-TO-DO:")[-1].strip()
                    logger.info(f"[MASTERMIND] Directive: {self._mastermind_directive}")
                return True
            params["text"] = result
            decision["text"] = result
            logger.info(f"Mastermind APPROVED post: {result[:100]}")

        # Finance gate: block engagement on non-finance posts
        FINANCE_CHECKED = {"like", "reply", "retweet", "quote", "bookmark"}
        if action in FINANCE_CHECKED and tweet_idx is not None:
            post_text = ""
            try:
                tweet_els = self.page.locator('[data-testid="tweetText"]').all()
                if int(tweet_idx) < len(tweet_els):
                    post_text = tweet_els[int(tweet_idx)].inner_text(timeout=3000)
            except Exception:
                pass
            if post_text and not is_finance_related(post_text):
                logger.info(f"Non-finance post at #{tweet_idx}, blocking {action} and marking not_interested")
                execute_action(self.page, "not_interested", {"tweet_index": int(tweet_idx)})
                self.memory.record_action(action, params, "blocked: non-finance post", False)
                return True

        success = execute_action(self.page, action, params)

        if success and action == "click_trend" and tweet_idx is not None:
            self._used_trend_indices.add(int(tweet_idx))
            logger.info(f"Tracked used trend index {tweet_idx} ({len(self._used_trend_indices)} used)")

        self.memory.record_action(action, params, decision.get("reason", ""), success)
        if not success:
            logger.info(f"Action '{action}' failed — retrying once")
            time.sleep(random.uniform(1, 2))
            success = execute_action(self.page, action, params)
            if success:
                logger.info(f"Retry of '{action}' succeeded")
                self.memory.record_action(action, params, "retry after failure", True)
            else:
                logger.info(f"Retry of '{action}' also failed, running fallback (click home)")
                fallback_ok = execute_action(self.page, "click", {"target": "home_link"})
                if not fallback_ok:
                    logger.info("Fallback click failed, navigating to home directly")
                    execute_action(self.page, "navigate", {"url": "https://x.com/home"})
                self.memory.record_action("fallback_home", {}, "auto-fallback after failure", True)

        delay = random_delay(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
        logger.debug(f"Delayed {delay:.1f}s after action")

        return True

    def run_session(self, max_steps: int = 30):
        try:
            self.page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.warning(f"Initial goto failed: {e}")
            if not self._recover_page():
                logger.error("Could not recover page at session start")
                return
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
