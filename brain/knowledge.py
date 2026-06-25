import json
import os
import time

from utils.logger import logger

KNOWLEDGE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "knowledge.json"
)


class Knowledge:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(KNOWLEDGE_FILE):
            try:
                with open(KNOWLEDGE_FILE) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load knowledge: {e}")
        return {
            "interests": [],
            "trending_topics": [],
            "past_posts": [],
            "learnings": [],
            "research_cache": {},
            "last_updated": 0,
        }

    def save(self):
        self.data["last_updated"] = time.time()
        os.makedirs(os.path.dirname(KNOWLEDGE_FILE), exist_ok=True)
        with open(KNOWLEDGE_FILE, "w") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def add_learning(self, topic: str, content: str):
        self.data["learnings"].append({
            "topic": topic,
            "content": content,
            "timestamp": time.time(),
        })
        if len(self.data["learnings"]) > 100:
            self.data["learnings"] = self.data["learnings"][-100:]
        self.save()

    def add_post(self, text: str):
        self.data["past_posts"].append({
            "text": text[:200],
            "timestamp": time.time(),
        })
        if len(self.data["past_posts"]) > 200:
            self.data["past_posts"] = self.data["past_posts"][-200:]
        self.save()

    def get_recent_learnings(self, limit: int = 10) -> list[dict]:
        return self.data["learnings"][-limit:]

    def summary(self) -> str:
        k = self.data
        parts = []
        if k["learnings"]:
            recent = k["learnings"][-5:]
            parts.append("Recent learnings: " + "; ".join(
                f"{l['topic']}: {l['content'][:100]}" for l in recent
            ))
        if k["trending_topics"]:
            parts.append("Trending: " + ", ".join(k["trending_topics"][-8:]))
        if k["past_posts"]:
            parts.append(f"Total posts made: {len(k['past_posts'])}")
        return "\n".join(parts) if parts else "No prior knowledge."
