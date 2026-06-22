import random
import time
from datetime import datetime, timezone


import math


def random_delay(min_sec: float = 8, max_sec: float = 18) -> float:
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    return delay


def human_delay(short: bool = False) -> float:
    base = random.uniform(1, 3) if short else random.uniform(3, 12)
    jitter = random.gauss(0, base * 0.3)
    delay = max(0.5, base + jitter)
    time.sleep(delay)
    return delay


def reading_delay(text_length: int = 100) -> float:
    wpm = random.randint(200, 400)
    words = text_length / 5
    seconds = (words / wpm) * 60
    time.sleep(max(2, seconds * random.uniform(0.5, 1.5)))
    return seconds


def is_active_hours(start: int = 8, end: int = 22) -> bool:
    hour = datetime.now(timezone.utc).hour
    return start <= hour < end


def truncate(text: str, max_len: int = 100) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text
