import time

from playwright.sync_api import Page

from twitter.selectors import SELECTORS
from utils.logger import logger


def tweet(page: Page, text: str) -> bool:
    try:
        sidebar = page.locator(SELECTORS["sidebar_tweet"])
        if sidebar.is_visible(timeout=3000):
            sidebar.click()
            time.sleep(1.5)

        compose = page.locator(SELECTORS["tweet_compose"])
        compose.click()
        compose.fill(text)
        time.sleep(1)

        btn = page.locator(SELECTORS["tweet_button"])
        if btn.is_visible(timeout=3000):
            btn.click()
            logger.info(f"Posted tweet")
            time.sleep(2)
            return True

        btn2 = page.locator(SELECTORS["tweet_button_small"])
        if btn2.is_visible(timeout=3000):
            btn2.click()
            logger.info(f"Posted tweet")
            time.sleep(2)
            return True
        return False
    except Exception as e:
        logger.error(f"Tweet failed: {e}")
        return False


def like_tweet_by_index(page: Page, index: int = 0) -> bool:
    tweets = page.locator(SELECTORS["tweet_article"]).all()
    if index >= len(tweets):
        return False
    try:
        btn = tweets[index].locator(SELECTORS["like_button"])
        if btn.is_visible(timeout=3000):
            btn.click()
            time.sleep(1)
            return True
    except Exception as e:
        logger.warning(f"Like failed: {e}")
    return False
