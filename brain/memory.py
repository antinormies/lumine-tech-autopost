from collections import Counter


ENGAGEMENT_ACTIONS = {"like", "reply", "retweet", "bookmark", "tweet"}


class Memory:
    def __init__(self):
        self.actions: list[dict] = []
        self.seen_tweets: set[str] = set()
        self.engagement_counts: Counter = Counter()

    def record_action(self, action: str, params: dict, reason: str, success: bool):
        entry = {
            "action": action,
            "params": params,
            "reason": reason,
            "success": success,
        }
        self.actions.append(entry)
        if action in ENGAGEMENT_ACTIONS and success:
            self.engagement_counts[action] += 1

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

    def save(self):
        pass
