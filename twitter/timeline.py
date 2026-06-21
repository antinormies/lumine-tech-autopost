from typing import Optional

from playwright.sync_api import Page

from twitter.selectors import SELECTORS
from utils.logger import logger


class TimelineReader:
    def __init__(self, page: Page):
        self.page = page

    def get_visible_tweets(self) -> list[dict]:
        tweets = self.page.locator(SELECTORS["tweet_article"]).all()
        result = []
        for i, tweet_el in enumerate(tweets):
            try:
                text_el = tweet_el.locator(SELECTORS["tweet_text"])
                text = text_el.inner_text() if text_el.is_visible(timeout=1000) else ""
                name_el = tweet_el.locator(SELECTORS["user_name"])
                name = name_el.inner_text() if name_el.is_visible(timeout=1000) else ""
                result.append({"index": i, "author": name, "text": text})
            except Exception:
                result.append({"index": i, "author": "", "text": ""})
        return result

    def get_tweet_text(self, index: int = 0) -> Optional[str]:
        tweets = self.page.locator(SELECTORS["tweet_article"]).all()
        if index >= len(tweets):
            return None
        try:
            text_el = tweets[index].locator(SELECTORS["tweet_text"])
            return text_el.inner_text() if text_el.is_visible(timeout=3000) else None
        except Exception:
            return None

    def navigate_home(self):
        logger.info("Navigating to home timeline")
        self.page.goto("https://x.com/home", wait_until="domcontentloaded")
        import time
        time.sleep(3)
