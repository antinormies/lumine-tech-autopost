from datetime import datetime, timezone

from config import config


class Context:
    def __init__(self):
        self.step_count = 0
        self.session_start = datetime.now(timezone.utc)

    def is_active_hours(self) -> bool:
        hour = datetime.now(timezone.utc).hour
        return config.ACTIVE_HOURS_START <= hour < config.ACTIVE_HOURS_END

    def can_tweet(self) -> bool:
        return self.step_count < config.MAX_TWEETS_PER_SESSION

    def can_like(self) -> bool:
        return self.step_count < config.MAX_LIKES_PER_SESSION

    def increment(self):
        self.step_count += 1
