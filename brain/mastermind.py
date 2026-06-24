import re
import time
from typing import Optional

import requests

from config import config
from llm.client import LLMClient
from utils.logger import logger
from brain.knowledge import Knowledge


class Mastermind:
    def __init__(self, persona):
        self.knowledge = Knowledge()
        self.persona = persona
        self.llm = LLMClient(
            base_url=config.MASTERMIND_BASE_URL,
            model=config.MASTERMIND_MODEL,
        )
        logger.info(f"Mastermind online — strategist: {config.MASTERMIND_MODEL}")

    def search_web(self, query: str, max_results: int = 3) -> str:
        cache = self.knowledge.data["research_cache"]
        key = query.lower().strip()
        if key in cache and time.time() - cache[key].get("timestamp", 0) < 3600:
            return cache[key].get("content", "")

        logger.info(f"[MASTERMIND] Searching web: {query}")
        try:
            resp = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                parts = []
                if data.get("AbstractText"):
                    parts.append(data["AbstractText"])
                if data.get("RelatedTopics"):
                    for t in data["RelatedTopics"][:max_results]:
                        if isinstance(t, dict) and t.get("Text"):
                            parts.append(t["Text"])
                if parts:
                    result = "\n".join(parts)
                    cache[key] = {"content": result, "timestamp": time.time()}
                    self.knowledge.save()
                    logger.info(f"[MASTERMIND] Web search result ({len(result)} chars)")
                    return result
                logger.info("[MASTERMIND] No web search results")
        except Exception as e:
            logger.warning(f"[MASTERMIND] Web search failed: {e}")
        return ""

    def fetch_page(self, url: str) -> str:
        cache_key = f"page:{url}"
        cache = self.knowledge.data["research_cache"]
        if cache_key in cache and time.time() - cache[cache_key].get("timestamp", 0) < 3600:
            return cache[cache_key].get("content", "")

        logger.info(f"[MASTERMIND] Fetching page: {url}")
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                text = re.sub(r"<[^>]+>", " ", resp.text)
                text = re.sub(r"\s+", " ", text).strip()[:2000]
                cache[cache_key] = {"content": text, "timestamp": time.time()}
                self.knowledge.save()
                logger.info(f"[MASTERMIND] Page fetched ({len(text)} chars)")
                return text
        except Exception as e:
            logger.warning(f"[MASTERMIND] Fetch failed: {e}")
        return ""

    def _auto_research(self) -> str:
        topics = self.persona.topics[:3]
        results = []
        for topic in topics:
            result = self.search_web(topic)
            if result:
                results.append(f"--- {topic} ---\n{result[:500]}")
        return "\n\n".join(results) if results else ""

    def generate_brief(self) -> str:
        knowledge_ctx = self.knowledge.summary()
        persona_prompt = self.persona.build_system_prompt()
        web_research = self._auto_research()

        prompt = (
            f"You are the MASTERMIND strategist guiding a Twitter bot.\n"
            f"An ANALYST (vision model) browses Twitter via screenshots.\n"
            f"You set the strategy — what to do, what to post, what to focus on.\n\n"
            f"PERSONA:\n{persona_prompt}\n\n"
            f"PERSISTENT KNOWLEDGE (past sessions):\n{knowledge_ctx}\n\n"
        )
        if web_research:
            prompt += f"WEB RESEARCH (current info):\n{web_research[:1000]}\n\n"
        prompt += (
            f"Generate a BRIEF SESSION STRATEGY for the Analyst. Include:\n"
            f"1. TOP GOALS (max 3) — what should this session achieve\n"
            f"2. INTERESTS TO FOCUS ON — from persona topics, what to prioritize\n"
            f"3. CONTENT STRATEGY — what kind of posts/replies to make, tone\n"
            f"4. WARNINGS — what to avoid\n\n"
            f"Under 200 words. Be specific. Plain text, no JSON.\n"
            f"Focus on the persona's core identity and goals."
        )

        resp = self.llm.text_chat(
            system_prompt="You are a strategic mastermind. Concise and specific.",
            user_text=prompt,
            temperature=0.7,
            max_tokens=400,
        )

        if resp and resp.content:
            logger.info(f"[MASTERMIND] Generated {len(resp.content.strip())} char brief")
            self._brief = resp.content.strip()
            return self._brief
        return self._fallback_brief()

    def research(self, query: str) -> str:
        """Legacy alias for search_web."""
        return self.search_web(query)

    def advise(self, context: str, recent_actions: list[dict], trends_text: str = "",
               avoid_keywords: Optional[set] = None) -> str:
        actions_str = "; ".join(
            f"{a.get('action','?')}[{'ok' if a.get('success') else 'x'}]"
            for a in recent_actions[-6:]
        )
        success_count = sum(1 for a in recent_actions[-6:] if a.get("success"))
        fail_count = sum(1 for a in recent_actions[-6:] if not a.get("success"))

        recent_names = [a.get("action", "") for a in recent_actions[-6:]]
        scroll_streak = 0
        for n in reversed(recent_names):
            if n in ("scroll_down", "scroll", "scroll_down_long", "scroll_up"):
                scroll_streak += 1
            else:
                break

        looping = len(recent_names) >= 3 and len(set(recent_names)) <= 2

        blocked_trend = ""
        if avoid_keywords and trends_text:
            for t in trends_text.replace("Trending now: ", "").split("; "):
                t_clean = t.strip().lower()
                if any(kw in t_clean for kw in avoid_keywords):
                    blocked_trend += f"WARNING: '{t}' is RESTRICTED (gov/military). AVOID.\n"
                    break

        analysis = ""
        if blocked_trend:
            analysis += blocked_trend
        if fail_count >= 3:
            analysis += f"WARNING: {fail_count}/{len(recent_actions[-6:])} recent actions FAILED. "
        if scroll_streak >= 2:
            analysis += f"STOP SCROLLING ({scroll_streak}x streak). "
        if looping:
            analysis += f"LOOP DETECTED: repeating [{', '.join(set(recent_names))}]. BREAK IT. "

        research = ""
        search_suggestion = ""
        if blocked_trend:
            import re as _re
            matches = _re.findall(r"'([^']+)' is RESTRICTED", blocked_trend)
            if matches:
                pass
            persona_topics = [t for t in self.persona.topics if not any(kw in t.lower() for kw in (avoid_keywords or set()))]
            if persona_topics:
                search_suggestion = f"search_topic('{persona_topics[0]}') for safe content."

        if trends_text and not blocked_trend:
            trend_lines = trends_text.replace("Trending now: ", "").split("; ")[:2]
            if trend_lines:
                query = trend_lines[0][:60]
                research = self.search_web(query)

        prompt = (
            f"You are the MASTERMIND. The Analyst is mid-session.\n\n"
            f"SESSION BRIEF:\n{self._brief}\n\n"
            f"CURRENT STATE:\n{context}\n\n"
            f"RECENT ACTIONS (last 6):\n{actions_str}\n"
            f"Success rate: {success_count}/{len(recent_actions[-6:])}\n\n"
            f"ANALYSIS:\n{analysis}\n"
        )
        if trends_text and not blocked_trend:
            prompt += f"VISIBLE TRENDS:\n{trends_text[:400]}\n\n"
        if research:
            prompt += f"WEB RESEARCH (current trend):\n{research[:500]}\n\n"
        if search_suggestion:
            prompt += f"SUGGESTION: {search_suggestion}\n\n"
        prompt += (
            f"INSTRUCTIONS:\n"
            f"1. CRITICALLY evaluate the Analyst's recent actions. "
            f"Are they following the brief? Stuck? Wasting steps?\n"
            f"2. Say which topic to ENGAGE with or SEARCH for. "
            f"If current trends are restricted, suggest a SAFE search topic.\n"
            f"3. Give ONE specific action. Be concrete: "
            f"'like(0)', 'reply(0, text)', 'search_topic(\"keyword\")', "
            f"'click(target=\"explore_link\")', 'click_trend(0)', 'back', etc.\n"
            f"4. Say WHY — connect it to the session goals.\n\n"
            f"Under 80 words."
        )

        resp = self.llm.text_chat(
            system_prompt="You are a critical strategist. Judge actions, give specific tactical orders.",
            user_text=prompt,
            temperature=0.6,
            max_tokens=150,
        )

        if resp and resp.content:
            logger.info(f"[MASTERMIND] Advice: {resp.content.strip()[:150]}")
            return resp.content.strip()
        return ""

    def load_brief(self) -> str:
        """Load the current brief (set by generate_brief) or fallback."""
        return getattr(self, "_brief", None) or self._fallback_brief()

    def _fallback_brief(self) -> str:
        topics = ", ".join(self.persona.topics[:5])
        self._brief = (
            f"GOALS:\n1. Scroll home feed and engage with posts about: {topics}\n"
            f"2. Explore trending topics, focus on interest-matching content\n"
            f"3. Like, retweet, reply naturally\n\n"
            f"INTERESTS: {self.persona.description}\n"
            f"WARNINGS: Avoid military/politics. Never reveal bot identity."
        )
        return self._brief

    def save(self):
        self.knowledge.save()
