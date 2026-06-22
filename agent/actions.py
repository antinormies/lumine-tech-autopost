import os
import random
import re
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


BLOCKED_CLICKS = {"follow", "following", "unfollow", "like", "direct_message", "send"}


def click(page: Page, target: str) -> bool:
    if not target:
        logger.warning("No target specified for click")
        return False
    resolved = resolve_target(target)
    if resolved in BLOCKED_CLICKS:
        logger.info(f"Blocked: {target}")
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


COMPOSE_TARGETS = {"compose", "tweet_compose", "compose_textarea", "composer", "textarea", "post"}


def type_text(page: Page, target: str, text: str) -> bool:
    if not target or target.lower() in COMPOSE_TARGETS:
        textarea = page.locator(SELECTORS["tweet_compose"]).first
        if textarea.is_visible(timeout=2000):
            textarea.focus()
            page.keyboard.type(clean_text(text), delay=random.randint(20, 60))
            logger.info(f"Typed into compose textarea")
            time.sleep(0.5)
            return True
        logger.warning("No compose textarea visible")
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


def clean_text(text: str) -> str:
    text = re.sub(r'[#＃][\w\u0080-\uFFFF]+', '', text)
    text = re.sub(r'[@＠][\w\u0080-\uFFFF]+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text or "."


def tweet(page: Page, text: str) -> bool:
    try:
        text = clean_text(text)
        textarea = page.locator(SELECTORS["tweet_compose"]).first
        if not textarea.is_visible(timeout=3000):
            sidebar = page.locator(SELECTORS["sidebar_tweet"])
            sidebar.wait_for(timeout=5000)
            sidebar.click()
            time.sleep(1.5)
            textarea.wait_for(timeout=5000)

        _jitter_mouse(page)
        textarea.focus()
        time.sleep(0.3)
        page.keyboard.type(text, delay=random.randint(30, 90))
        time.sleep(0.5)

        post_btn = page.locator(SELECTORS["tweet_button_small"])
        if not post_btn.is_visible(timeout=2000):
            post_btn = page.locator(SELECTORS["tweet_button"])
        post_btn.wait_for(timeout=5000)
        timeout_end = time.time() + 10
        while time.time() < timeout_end:
            if post_btn.is_enabled():
                break
            time.sleep(0.5)
        post_btn.click(force=True)
        logger.info(f"Tweet posted: {text[:50]}...")
        time.sleep(1)
        return True
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
        reply_area.fill(clean_text(text))
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
        confirm = page.locator(SELECTORS["retweet_confirm"])
        confirm.wait_for(timeout=3000)
        confirm.click()
        logger.info(f"Retweeted tweet #{index}")
        return True
    except Exception as e:
        logger.warning(f"Failed to retweet: {e}")
        return False


def quote_tweet(page: Page, index: int, text: str) -> bool:
    tweets = page.locator(SELECTORS["tweet_article"]).all()
    if index >= len(tweets):
        return False
    try:
        _jitter_mouse(page)
        rt_btn = tweets[index].locator(SELECTORS["retweet_button"])
        rt_btn.scroll_into_view_if_needed(timeout=3000)
        rt_btn.click()
        time.sleep(random.uniform(0.5, 1.5))
        quote_btn = page.locator(SELECTORS["quote_option"])
        quote_btn.wait_for(timeout=5000)
        quote_btn.click()
        time.sleep(random.uniform(0.5, 1.5))
        compose = page.locator(SELECTORS["tweet_compose"])
        compose.wait_for(timeout=5000)
        compose.focus()
        page.keyboard.type(clean_text(text), delay=random.randint(20, 60))
        time.sleep(random.uniform(0.5, 1.5))
        post_btn = page.locator(SELECTORS["tweet_button_small"])
        if not post_btn.is_visible(timeout=2000):
            post_btn = page.locator(SELECTORS["tweet_button"])
        post_btn.wait_for(timeout=5000)
        timeout_end = time.time() + 10
        while time.time() < timeout_end:
            if post_btn.is_enabled():
                break
            time.sleep(0.5)
        post_btn.click(force=True)
        logger.info(f"Quoted tweet #{index}")
        time.sleep(1)
        return True
    except Exception as e:
        logger.warning(f"Failed to quote: {e}")
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


def open_tweet(page: Page, index: int = 0) -> bool:
    tweets = page.locator(SELECTORS["tweet_article"]).all()
    if index >= len(tweets):
        logger.warning(f"Tweet index {index} out of range ({len(tweets)} tweets)")
        return False
    try:
        _jitter_mouse(page)
        article = tweets[index]
        article.scroll_into_view_if_needed(timeout=3000)
        time.sleep(random.uniform(0.3, 1))
        article.click(force=True, timeout=5000)
        logger.info(f"Opened tweet #{index} detail view")
        time.sleep(random.uniform(1, 2))
        return True
    except Exception as e:
        logger.warning(f"Failed to open tweet #{index}: {e}")
        return False


def like_comment(page: Page, index: int = 0) -> bool:
    """Like a comment/reply within a tweet detail page.
    Comments are articles with data-testid='tweet' inside the detail view.
    """
    comments = page.locator(SELECTORS["tweet_article"]).all()
    if 0 <= index < len(comments):
        try:
            like_btn = comments[index].locator(SELECTORS["like_button"])
            if like_btn.is_visible(timeout=3000):
                like_btn.click()
                logger.info(f"Liked comment #{index}")
                time.sleep(1)
                return True
        except Exception as e:
            logger.warning(f"Failed to like comment #{index}: {e}")
    return False


def go_back(page: Page) -> bool:
    try:
        page.go_back(wait_until="domcontentloaded")
        time.sleep(2)
        logger.info("Navigated back")
        return True
    except Exception as e:
        logger.warning(f"Failed to go back: {e}")
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


def rest(page: Page) -> bool:
    try:
        profile_url = f"https://x.com/{os.getenv('TWITTER_USERNAME', '')}"
        if profile_url:
            page.goto(profile_url, wait_until="domcontentloaded")
            time.sleep(3)
        duration = random.randint(2700, 7200)
        logger.info(f"Resting for {duration // 60}-{duration // 60 + 1}min on profile")
        time.sleep(duration)
        return True
    except Exception as e:
        logger.warning(f"Rest failed: {e}")
        return False


def scroll_down_long(page: Page, amount: int = 2500) -> bool:
    amount = random.randint(2000, 5000)
    steps = random.randint(8, 15)
    per_step = amount // steps
    try:
        for _ in range(steps):
            page.evaluate(f"window.scrollBy(0, {per_step})")
            time.sleep(random.uniform(0.08, 0.3))
        logger.info(f"Scrolled down long ~{amount}px")
        time.sleep(random.uniform(1, 2.5))
        return True
    except Exception as e:
        logger.warning(f"Long scroll down failed: {e}")
        return False


ACTION_REGISTRY = {
    "click": lambda page, params: click(page, params.get("target", "")),
    "type": lambda page, params: type_text(page, params.get("target", ""), params.get("text", "")),
    "scroll_down": lambda page, params: scroll_down(page, params.get("amount", 600)),
    "scroll_up": lambda page, params: scroll_up(page, params.get("amount", 600)),
    "scroll": lambda page, params: scroll_down(page, params.get("amount", 600)),
    "scroll_down_long": lambda page, params: scroll_down_long(page, params.get("amount", 2500)),
    "post": lambda page, params: tweet(page, params.get("text", "")),
    "navigate": lambda page, params: navigate(page, params.get("url", "")),
    "wait": lambda page, params: wait(params.get("seconds", 5)),
    "tweet": lambda page, params: tweet(page, params.get("text", "")),
    "like": lambda page, params: like_nth_tweet(page, params.get("tweet_index", 0)),
    "reply": lambda page, params: reply_to_tweet(page, params.get("tweet_index", 0), params.get("text", "")),
    "retweet": lambda page, params: retweet_nth(page, params.get("tweet_index", 0)),
    "quote": lambda page, params: quote_tweet(page, params.get("tweet_index", 0), params.get("text", "")),
    "bookmark": lambda page, params: bookmark_nth(page, params.get("tweet_index", 0)),
    "compose": lambda page, params: tweet(page, params.get("text", "")),
    "cancel_compose": lambda page, params: cancel_compose(page),
    "open_tweet": lambda page, params: open_tweet(page, params.get("tweet_index", 0)),
    "like_comment": lambda page, params: like_comment(page, params.get("tweet_index", 0)),
    "back": lambda page, params: go_back(page),
    "rest": lambda page, params: rest(page),
}


def execute_action(page: Page, action_name: str, params: dict) -> bool:
    handler = ACTION_REGISTRY.get(action_name)
    if not handler:
        logger.warning(f"Unknown action: {action_name}")
        return False
    return handler(page, params)
