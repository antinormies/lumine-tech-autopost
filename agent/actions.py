import random
import time
from playwright.sync_api import Page

from twitter.selectors import SELECTORS, ELEMENT_DESCRIPTIONS, resolve_target
from utils.logger import logger


def find_element(page: Page, target: str):
    target = resolve_target(target)
    selector = SELECTORS.get(target)
    if selector:
        return page.locator(selector).first
    text_locator = page.get_by_text(target, exact=False)
    if text_locator.count() > 0:
        return text_locator.first
    return page.locator(f'[data-testid="{target}"]').first


def _jitter_mouse(page: Page):
    try:
        vp = page.viewport_size
        x = random.randint(100, vp["width"] - 100)
        y = random.randint(100, vp["height"] - 100)
        page.mouse.move(x, y, steps=random.randint(5, 15))
    except Exception:
        pass


def click(page: Page, target: str) -> bool:
    if not target:
        logger.warning("No target specified for click")
        return False
    el = find_element(page, target)
    desc = ELEMENT_DESCRIPTIONS.get(target, target)
    try:
        _jitter_mouse(page)
        el.scroll_into_view_if_needed(timeout=3000)
        time.sleep(random.uniform(0.3, 1.2))
        el.click(force=True, timeout=5000)
        logger.info(f"Clicked {desc}")
        time.sleep(random.uniform(0.5, 2))
        return True
    except Exception as e:
        logger.warning(f"Failed to click {desc}: {e}")
        return False


def type_text(page: Page, target: str, text: str) -> bool:
    if not target:
        compose = page.locator(SELECTORS["tweet_compose"]).first
        if compose.is_visible(timeout=2000):
            target = "tweet_compose"
        else:
            logger.warning("No target specified and no compose textarea visible")
            return False
    el = find_element(page, target)
    desc = ELEMENT_DESCRIPTIONS.get(target, target)
    try:
        el.scroll_into_view_if_needed(timeout=3000)
        el.click(force=True, timeout=5000)
        page.keyboard.insert_text(text)
        logger.info(f"Typed into {desc}")
        time.sleep(0.5)
        return True
    except Exception as e:
        logger.warning(f"Failed to type into {desc}: {e}")
        return False


def scroll_down(page: Page, amount: int = 600) -> bool:
    amount = random.randint(300, 800)
    steps = random.randint(3, 8)
    per_step = amount // steps
    try:
        for _ in range(steps):
            page.evaluate(f"window.scrollBy(0, {per_step})")
            time.sleep(random.uniform(0.05, 0.3))
        logger.info(f"Scrolled down ~{amount}px")
        time.sleep(random.uniform(0.5, 2))
        return True
    except Exception as e:
        logger.warning(f"Scroll down failed: {e}")
        return False


def scroll_up(page: Page, amount: int = 600) -> bool:
    amount = random.randint(100, 400)
    steps = random.randint(2, 5)
    per_step = amount // steps
    try:
        for _ in range(steps):
            page.evaluate(f"window.scrollBy(0, -{per_step})")
            time.sleep(random.uniform(0.05, 0.2))
        logger.info(f"Scrolled up ~{amount}px")
        time.sleep(random.uniform(0.3, 1))
        return True
    except Exception as e:
        logger.warning(f"Scroll up failed: {e}")
        return False


def navigate(page: Page, url: str) -> bool:
    logger.info(f"Navigating to {url}")
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(3)
    return True


def wait(seconds: int) -> bool:
    logger.info(f"Waiting {seconds}s")
    time.sleep(seconds)
    return True


def tweet(page: Page, text: str) -> bool:
    try:
        post_btn = page.locator(SELECTORS["tweet_button"])
        compose_open = post_btn.is_visible(timeout=2000) or page.locator(SELECTORS["tweet_compose"]).first.is_visible(timeout=2000)

        if not compose_open:
            sidebar = page.locator(SELECTORS["sidebar_tweet"])
            if sidebar.is_visible(timeout=3000):
                sidebar.click()
                time.sleep(1.5)

        compose = page.locator(SELECTORS["tweet_compose"]).first
        compose.click()
        compose.fill(text)
        time.sleep(1)

        if post_btn.is_visible(timeout=3000):
            post_btn.click()
            logger.info(f"Tweet posted: {text[:50]}...")
            time.sleep(2)
            return True

        btn2 = page.locator(SELECTORS["tweet_button_small"])
        if btn2.is_visible(timeout=3000):
            btn2.click()
            logger.info(f"Tweet posted: {text[:50]}...")
            time.sleep(2)
            return True

        logger.warning("Could not find tweet button")
        return False
    except Exception as e:
        logger.error(f"Failed to tweet: {e}")
        return False


def like_nth_tweet(page: Page, index: int = 0) -> bool:
    tweets = page.locator(SELECTORS["tweet_article"]).all()
    if index >= len(tweets):
        logger.warning(f"Tweet index {index} out of range ({len(tweets)} tweets)")
        return False
    try:
        like_btn = tweets[index].locator(SELECTORS["like_button"])
        if like_btn.is_visible(timeout=3000):
            like_btn.click()
            logger.info(f"Liked tweet #{index}")
            time.sleep(1)
            return True
    except Exception as e:
        logger.warning(f"Failed to like tweet #{index}: {e}")
    return False


def reply_to_tweet(page: Page, index: int, text: str) -> bool:
    tweets = page.locator(SELECTORS["tweet_article"]).all()
    if index >= len(tweets):
        return False
    try:
        reply_btn = tweets[index].locator(SELECTORS["reply_button"])
        reply_btn.click()
        time.sleep(2)
        reply_area = page.locator('[data-testid="tweetTextarea_0"]')
        reply_area.fill(text)
        time.sleep(1)
        page.locator('[data-testid="tweetButton"]').click()
        logger.info(f"Replied to tweet #{index}")
        time.sleep(2)
        return True
    except Exception as e:
        logger.warning(f"Failed to reply: {e}")
        return False


def retweet_nth(page: Page, index: int = 0) -> bool:
    tweets = page.locator(SELECTORS["tweet_article"]).all()
    if index >= len(tweets):
        return False
    try:
        rt_btn = tweets[index].locator(SELECTORS["retweet_button"])
        rt_btn.click()
        time.sleep(1)
        confirm = page.locator(SELECTORS["retweet_confirm"])
        confirm.click()
        logger.info(f"Retweeted tweet #{index}")
        time.sleep(1)
        return True
    except Exception as e:
        logger.warning(f"Failed to retweet: {e}")
        return False


def bookmark_nth(page: Page, index: int = 0) -> bool:
    tweets = page.locator(SELECTORS["tweet_article"]).all()
    if index >= len(tweets):
        return False
    try:
        bm_btn = tweets[index].locator(SELECTORS["bookmark_button"])
        bm_btn.click()
        logger.info(f"Bookmarked tweet #{index}")
        time.sleep(1)
        return True
    except Exception as e:
        logger.warning(f"Failed to bookmark: {e}")
        return False


def cancel_compose(page: Page) -> bool:
    try:
        close_btn = page.locator('[data-testid="app-bar-close"]')
        if close_btn.is_visible(timeout=2000):
            close_btn.click()
            logger.info("Closed compose dialog")
            time.sleep(1)
            return True
        page.keyboard.press("Escape")
        time.sleep(1)
        return True
    except Exception as e:
        logger.warning(f"Failed to close compose: {e}")
        return False


ACTION_REGISTRY = {
    "click": lambda page, params: click(page, params.get("target", "")),
    "type": lambda page, params: type_text(page, params.get("target", ""), params.get("text", "")),
    "scroll_down": lambda page, params: scroll_down(page, params.get("amount", 600)),
    "scroll_up": lambda page, params: scroll_up(page, params.get("amount", 600)),
    "navigate": lambda page, params: navigate(page, params.get("url", "")),
    "wait": lambda page, params: wait(params.get("seconds", 5)),
    "tweet": lambda page, params: tweet(page, params.get("text", "")),
    "like": lambda page, params: like_nth_tweet(page, params.get("tweet_index", 0)),
    "reply": lambda page, params: reply_to_tweet(page, params.get("tweet_index", 0), params.get("text", "")),
    "retweet": lambda page, params: retweet_nth(page, params.get("tweet_index", 0)),
    "bookmark": lambda page, params: bookmark_nth(page, params.get("tweet_index", 0)),
    "cancel_compose": lambda page, params: cancel_compose(page),
}


def execute_action(page: Page, action_name: str, params: dict) -> bool:
    handler = ACTION_REGISTRY.get(action_name)
    if not handler:
        logger.warning(f"Unknown action: {action_name}")
        return False
    return handler(page, params)
