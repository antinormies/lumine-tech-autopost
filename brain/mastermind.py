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

    def advise(self, context: str, recent_actions: list[dict]) -> str:
        actions_str = "; ".join(
            f"{a.get('action','?')}({'ok' if a.get('success') else 'x'})"
            for a in recent_actions[-6:]
        )
        research = self._auto_research()
        prompt = (
            f"You are the MASTERMIND. The Analyst is mid-session.\n\n"
            f"SESSION BRIEF (pre-set):\n{self._brief}\n\n"
            f"CURRENT STATE:\n{context}\n\n"
            f"RECENT ACTIONS (last 6):\n{actions_str}\n\n"
        )
        if research:
            prompt += f"WEB RESEARCH (fresh data):\n{research[:800]}\n\n"
        prompt += (
            f"Give 1-2 sentence tactical advice. What should the Analyst do RIGHT NOW?\n"
            f"Be specific — 'keep scrolling home', 'switch to Explore Trending tab', "
            f"'click_trend(0) on AI', 'reply to the cat post', etc.\n"
            f"Under 60 words."
        )
        resp = self.llm.text_chat(
            system_prompt="You are a strategic mastermind. Give concise real-time guidance.",
            user_text=prompt,
            temperature=0.6,
            max_tokens=150,
        )
        if resp and resp.content:
            logger.info(f"[MASTERMIND] Advice: {resp.content.strip()[:120]}")
            return resp.content.strip()
        return ""

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
