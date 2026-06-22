import json
import os
import time
from collections import Counter
from pathlib import Path


ENGAGEMENT_ACTIONS = {"like", "reply", "retweet", "bookmark", "tweet"}
POST_ACTIONS = {"tweet", "compose", "post"}
PERSISTENCE_FILE = Path(__file__).resolve().parent.parent / "data" / "persistence.json"


class Memory:
    def __init__(self):
        self.actions: list[dict] = []
        self.seen_tweets: set[str] = set()
        self.engagement_counts: Counter = Counter()
        self.last_tweet_time: float | None = None
        self._load()

    def record_action(self, action: str, params: dict, reason: str, success: bool):
        entry = {
            "action": action,
            "params": params,
            "reason": reason,
            "success": success,
        }
        self.actions.append(entry)
        if action in POST_ACTIONS and success:
            self.last_tweet_time = time.time()
            self._save()
        if action in ENGAGEMENT_ACTIONS and success:
            self.engagement_counts[action] += 1

    def can_tweet(self, cooldown_hours: float = 1.0) -> bool:
        if self.last_tweet_time is None:
            return True
        elapsed = time.time() - self.last_tweet_time
        return elapsed >= cooldown_hours * 3600

    def last_action(self) -> dict | None:
        return self.actions[-1] if self.actions else None

    def total_engagements(self) -> int:
        return sum(self.engagement_counts.values())

    def recent_summary(self, n: int = 5) -> str:
        recent = self.actions[-n:]
        if not recent:
            return "No actions yet"
        return "; ".join(
            f"{a['action']}: {a.get('reason', '')[:60]}" for a in recent
        )

    def is_tweet_seen(self, tweet_id: str) -> bool:
        return tweet_id in self.seen_tweets

    def mark_tweet_seen(self, tweet_id: str):
        self.seen_tweets.add(tweet_id)

    def used_indices(self, action: str) -> set[int]:
        indices: set[int] = set()
        for a in self.actions:
            if a["action"] == action and a.get("success"):
                idx = (a.get("params") or {}).get("tweet_index")
                if idx is not None:
                    indices.add(int(idx))
        return indices

    def _load(self):
        try:
            if PERSISTENCE_FILE.exists():
                data = json.loads(PERSISTENCE_FILE.read_text())
                self.last_tweet_time = data.get("last_tweet_time")
        except Exception:
            self.last_tweet_time = None

    def _save(self):
        try:
            PERSISTENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {"last_tweet_time": self.last_tweet_time}
            PERSISTENCE_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to persist state: {e}")

    def save(self):
        self._save()
