import random
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
            context_size=config.MASTERMIND_CONTEXT_SIZE,
        )
        logger.info(f"Mastermind online — strategist: {config.MASTERMIND_MODEL}")

    def search_web(self, query: str, max_results: int = 3) -> str:
        cache = self.knowledge.data["research_cache"]
        key = query.lower().strip()
        if key in cache and time.time() - cache[key].get("timestamp", 0) < 3600:
            return cache[key].get("content", "")

        logger.info(f"[MASTERMIND] Searching web: {query}")
        try:
            resp = requests.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                urls = re.findall(r'class="result__url"[^>]*href="(https?://[^"]+)"', resp.text)
                snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|span)>', resp.text, re.DOTALL)
                parts = []
                for i in range(min(max_results, len(urls), len(snippets))):
                    snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()
                    parts.append(f"{urls[i]}: {snippet}")
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
            persona_topics = [t for t in self.persona.topics if not any(kw in t.lower() for kw in (avoid_keywords or set()))]
            if persona_topics:
                search_suggestion = f"search_topic('{persona_topics[0]}') for safe content."

        if trends_text and not blocked_trend:
            trend_lines = trends_text.replace("Trending now: ", "").split("; ")[:2]
            if trend_lines:
                parts = trend_lines[0].strip().split("\n")
                query = ""
                for p in parts:
                    p = p.strip()
                    if p and not p.lower().startswith("trending in"):
                        query = p[:60]
                        break
                if query:
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
            f"4. Say WHY — connect it to the session goals.\n"
            f"5. Never use emojis/emoticons in suggestions.\n\n"
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
            f"WARNINGS: Avoid military/politics. Never reveal bot identity. NO emojis/emoticons in any text."
        )
        return self._brief

    def approve_post(self, trends_text: str, post_texts: list[str], analyst_context: str,
                     avoid_keywords: Optional[set] = None) -> tuple[bool, str]:
        """Mastermind researches trends, evaluates relevance, generates or denies.

        Returns (approved: bool, text: str).
        - If approved: text is the EXACT tweet content to post verbatim.
        - If rejected: text starts with REJECTED and includes BEST-TO-DO directive.
        """
        # Use first trend as research topic
        trend_lines = trends_text.replace("Trending now: ", "").split("; ") if trends_text else []
        topic = ""
        if trend_lines:
            for part in trend_lines[0].split("\n"):
                p = part.strip()
                if p and not p.lower().startswith("trending in"):
                    topic = p[:100]
                    break
        if not topic:
            topic = self.persona.topics[0] if self.persona.topics else "forex"

        # Check restricted keywords
        restricted = ""
        if avoid_keywords:
            check_text = f"{topic} {' '.join(post_texts)}"
            for kw in avoid_keywords:
                if kw.lower() in check_text.lower():
                    restricted = f"TOPIC CONTAINS RESTRICTED KEYWORD '{kw}'"
                    break

        # Web research
        web_info = self.search_web(topic) if not restricted else ""

        persona_prompt = self.persona.build_system_prompt()

        prompt = (
            f"You are the MASTERMIND. The Analyst has gathered context and wants to post.\n\n"
            f"SESSION BRIEF:\n{self._brief}\n\n"
            f"ANALYST RECENT ACTIONS:\n{analyst_context}\n\n"
            f"TRENDING:\n{trends_text or '(none visible)'}\n\n"
            f"POSTS ANALYST ENGAGED WITH:\n"
        )
        if post_texts:
            for i, t in enumerate(post_texts[:5]):
                prompt += f"  Post {i+1}: {t[:200]}\n"
        else:
            prompt += "  (none captured)\n"

        if restricted:
            prompt += f"\nBLOCKED: {restricted}\n"
        elif web_info:
            prompt += f"\nWEB RESEARCH (current topic):\n{web_info[:800]}\n"

        prompt += (
            f"\nPERSONA WRITING RULES:\n{persona_prompt}\n\n"
            f"YOUR JOB:\n"
            f"1. Evaluate: is this topic relevant to the persona's interests (finance/forex/trading)?\n"
            f"2. Is it safe (not military/govt/NSFW)?\n"
            f"3. Is there enough context to write something valuable?\n\n"
            f"RULES:\n"
            f"- NO emojis/emoticons. Use character expressions like :), :(, :D, ;), :p instead.\n"
            f"- NO hashtags or @mentions.\n"
            f"- Positive framing. Match language of the posts.\n"
            f"- Write as a finance/investor persona, not a bot.\n\n"
            f"DECIDE:\n"
            f"- If YES to all: WRITE the EXACT tweet text the Analyst must post.\n"
            f"  Format: APPROVED: [exact tweet text — max 280 chars. Follow persona tone + rules.]\n\n"
            f"- If NO: REJECT then give a DIRECT BEST-TO-DO action for the Analyst.\n"
            f"  Format: REJECTED: [reason]. BEST-TO-DO: [specific action like search_topic('keyword') or click(target='...') or like(0)]\n\n"
            f"CRITICAL:\n"
            f"- NO hashtags or @mentions.\n"
            f"- Positive framing. Match language of the posts.\n"
            f"- Write as a finance/investor persona, not a bot."
        )

        resp = self.llm.text_chat(
            system_prompt="You are a strategic mastermind and content writer. Research, decide, then write or redirect.",
            user_text=prompt,
            temperature=0.7,
            max_tokens=250,
        )

        if not resp or not resp.content:
            logger.warning("[MASTERMIND] Post approval LLM returned nothing")
            return False, f"REJECTED: Mastermind unavailable. BEST-TO-DO: {self._best_do_fallback(topic)}"

        content = resp.content.strip()
        if content.startswith("REJECTED"):
            logger.info(f"[MASTERMIND] Post REJECTED: {content[:100]}")
            if "BEST-TO-DO:" not in content:
                content += f" BEST-TO-DO: {self._best_do_fallback(topic)}"
            return False, content

        if content.startswith("APPROVED:"):
            tweet_text = content[len("APPROVED:"):].strip()
            logger.info(f"[MASTERMIND] Post APPROVED: {tweet_text[:100]}")
            return True, tweet_text

        # LLM didn't follow format — assume approved raw text
        logger.info(f"[MASTERMIND] Post approved (raw): {content[:100]}")
        return True, content

    def _best_do_fallback(self, topic: str) -> str:
        keywords = ["forex", "trading", "stocks", "saham", "investasi", "crypto", "bitcoin", "gold", "rupiah", "IHSG"]
        kw = random.choice(keywords)
        return f"search_topic('{kw}') for relevant finance content."

    def approve_reply(self, post_text: str, author: str, analyst_context: str,
                      avoid_keywords: Optional[set] = None) -> tuple[bool, str]:
        """Analyst wants to reply to a specific post. Mastermind researches, writes the comment.

        Returns (approved: bool, text: str).
        - If approved: text is the EXACT comment to post verbatim.
        - If rejected: text starts with REJECTED and includes BEST-TO-DO directive.
        """
        # Check restricted keywords
        restricted = ""
        if avoid_keywords and post_text:
            for kw in avoid_keywords:
                if kw.lower() in post_text.lower():
                    restricted = f"POST CONTAINS RESTRICTED KEYWORD '{kw}'"
                    break

        # Web search on the post topic for context
        web_info = self.search_web(post_text[:100]) if not restricted and post_text else ""

        persona_prompt = self.persona.build_system_prompt()

        prompt = (
            f"You are the MASTERMIND. The Analyst wants to REPLY to a post.\n\n"
            f"SESSION BRIEF:\n{self._brief}\n\n"
            f"ANALYST RECENT ACTIONS:\n{analyst_context}\n\n"
            f"REPLYING TO — Author: {author}\n"
            f"POST TEXT: {post_text[:300]}\n\n"
        )
        if restricted:
            prompt += f"BLOCKED: {restricted}\n"
        elif web_info:
            prompt += f"WEB RESEARCH (for context):\n{web_info[:600]}\n"

        prompt += (
            f"\nPERSONA WRITING RULES:\n{persona_prompt}\n\n"
            f"YOUR JOB — write a relevant COMMENT on this post:\n"
            f"1. Is this post relevant to finance/forex/trading? If NO → REJECT.\n"
            f"2. Is it safe (not military/govt/NSFW)? If NO → REJECT.\n"
            f"3. If YES: write a SHORT, relevant reply. Match the post's language.\n"
            f"4. Add value — share your take, analysis, or insight. Don't just agree.\n\n"
            f"DECIDE:\n"
            f"- If YES: APPROVED: [exact reply text — under 200 chars. Natural, human, no hashtags.]\n"
            f"- If NO: REJECTED: [reason]. BEST-TO-DO: [specific action like search_topic('keyword') or click(target='...') or like(0)]\n\n"
            f"CRITICAL:\n"
            f"- NO emojis/emoticons. Use character expressions like :), :(, :D, ;), :p instead.\n"
            f"- Reply directly to the post content — don't change the subject.\n"
            f"- Match language (Bahasa for Bahasian posts, English for English posts).\n"
            f"- Positive framing. No hashtags or @mentions.\n"
            f"- Write as human finance/investor, not bot."
        )

        resp = self.llm.text_chat(
            system_prompt="You are a strategic mastermind. Write relevant, natural comments.",
            user_text=prompt,
            temperature=0.7,
            max_tokens=200,
        )

        if not resp or not resp.content:
            logger.warning("[MASTERMIND] Reply approval LLM returned nothing")
            return False, f"REJECTED: Mastermind unavailable. BEST-TO-DO: {self._best_do_fallback(post_text[:50])}"

        content = resp.content.strip()
        if content.startswith("REJECTED"):
            logger.info(f"[MASTERMIND] Reply REJECTED: {content[:100]}")
            if "BEST-TO-DO:" not in content:
                content += f" BEST-TO-DO: {self._best_do_fallback(post_text[:50])}"
            return False, content

        if content.startswith("APPROVED:"):
            reply_text = content[len("APPROVED:"):].strip()
            logger.info(f"[MASTERMIND] Reply APPROVED: {reply_text[:100]}")
            return True, reply_text

        logger.info(f"[MASTERMIND] Reply approved (raw): {content[:100]}")
        return True, content

    def save(self):
        self.knowledge.save()
