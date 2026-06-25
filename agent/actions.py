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


BLOCKED_CLICKS = {"unfollow", "like", "direct_message", "send"}


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
    steps = random.randint(2, 4)
    try:
        for _ in range(steps):
            page.mouse.wheel(0, random.randint(150, 350))
            time.sleep(1)
        logger.info(f"Scrolled down in {steps} steps")
        time.sleep(random.uniform(0.5, 2))
        return True
    except Exception as e:
        logger.warning(f"Scroll down failed: {e}")
        return False


def scroll_up(page: Page, amount: int = 600) -> bool:
    steps = random.randint(2, 4)
    try:
        for _ in range(steps):
            page.mouse.wheel(0, random.randint(-350, -150))
            time.sleep(1)
        logger.info(f"Scrolled up in {steps} steps")
        time.sleep(random.uniform(0.3, 1))
        return True
    except Exception as e:
        logger.warning(f"Scroll up failed: {e}")
        return False


def navigate(page: Page, url: str) -> bool:
    logger.info(f"Navigating to {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        return True
    except Exception as e:
        logger.warning(f"Navigate failed: {e}")
        return False


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
    article = tweets[index]
    try:
        article.scroll_into_view_if_needed(timeout=3000)
        time.sleep(random.uniform(0.3, 0.8))
        rt_btn = article.locator(SELECTORS["retweet_button"]).first
        if not rt_btn.is_visible(timeout=2000):
            logger.warning(f"Retweet button not visible on tweet #{index}")
            return False
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
    article = tweets[index]
    try:
        _jitter_mouse(page)
        article.scroll_into_view_if_needed(timeout=3000)
        time.sleep(random.uniform(0.3, 0.8))

        rt_btn = article.locator(SELECTORS["retweet_button"]).first
        if not rt_btn.is_visible(timeout=2000):
            logger.warning(f"Retweet/repost button not visible on tweet #{index}")
            return False
        rt_btn.click(force=True, timeout=5000)
        time.sleep(random.uniform(1, 2))

        quote_btn = page.locator(SELECTORS["quote_option"])
        for attempt in range(3):
            try:
                quote_btn.wait_for(timeout=2000)
                if quote_btn.is_visible():
                    break
            except Exception:
                if attempt < 2:
                    rt_btn.click(force=True, timeout=3000)
                    time.sleep(random.uniform(1, 2))
                else:
                    logger.warning("Quote option not found, falling back to retweet")
                    retweet_btn = article.locator(SELECTORS["retweet_button"]).first
                    if retweet_btn.is_visible(timeout=1000):
                        retweet_btn.click(force=True)
                        logger.info(f"Retweeted tweet #{index} (quote unavailable)")
                        time.sleep(1)
                        return True
                    return False

        quote_btn.click(force=True)
        time.sleep(random.uniform(1, 2))
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


def not_interested(page: Page, index: int = 0) -> bool:
    """Mark a tweet as 'Not interested in this post' to train the algorithm."""
    tweets = page.locator(SELECTORS["tweet_article"]).all()
    if index >= len(tweets):
        return False
    for attempt in range(2):
        try:
            _jitter_mouse(page)
            caret = tweets[index].locator(SELECTORS["tweet_caret"])
            caret.scroll_into_view_if_needed(timeout=3000)
            time.sleep(random.uniform(0.3, 0.8))
            caret.click(timeout=5000)
            time.sleep(random.uniform(1.5, 3))

            menu_item = page.locator(SELECTORS["not_interested"]).first
            menu_item.wait_for(timeout=5000)
            menu_item.click()
            logger.info(f"Marked tweet #{index} as not interested")
            time.sleep(1)
            return True
        except Exception as e:
            if attempt == 0:
                logger.info(f"not_interested attempt 1 failed for tweet #{index}, retrying: {e}")
                time.sleep(1)
            else:
                logger.warning(f"Failed to mark tweet #{index} as not interested: {e}")
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
    Articles[0] is the main tweet; comments start at index 1.
    like_comment(0) = first comment.
    """
    comments = page.locator(SELECTORS["tweet_article"]).all()
    comment_idx = index + 1
    if comment_idx < len(comments):
        try:
            like_btn = comments[comment_idx].locator(SELECTORS["like_button"])
            if like_btn.is_visible(timeout=3000):
                like_btn.click()
                logger.info(f"Liked comment #{index}")
                time.sleep(1)
                return True
        except Exception as e:
            logger.warning(f"Failed to like comment #{index}: {e}")
    return False


def open_profile(page: Page, index: int = 0) -> bool:
    tweets = page.locator(SELECTORS["tweet_article"]).all()
    if index >= len(tweets):
        logger.warning(f"Tweet index {index} out of range ({len(tweets)} tweets)")
        return False
    try:
        _jitter_mouse(page)
        user_link = tweets[index].locator(SELECTORS["user_name_link"])
        user_link.scroll_into_view_if_needed(timeout=3000)
        time.sleep(random.uniform(0.3, 1))
        user_link.click(force=True, timeout=5000)
        logger.info(f"Opened profile from tweet #{index}")
        time.sleep(random.uniform(1.5, 3))
        return True
    except Exception as e:
        logger.warning(f"Failed to open profile from tweet #{index}: {e}")
        return False


def follow(page: Page) -> bool:
    try:
        follow_btn = page.locator(SELECTORS["follow_button"])
        if not follow_btn.is_visible(timeout=3000):
            logger.warning("Follow button not visible")
            return False
        text = follow_btn.inner_text(timeout=1000).strip().lower()
        if text in ("following",):
            logger.info("Already following this account")
            return False
        _jitter_mouse(page)
        follow_btn.scroll_into_view_if_needed(timeout=3000)
        time.sleep(random.uniform(0.3, 1))
        follow_btn.click(force=True, timeout=5000)
        logger.info("Clicked follow button")
        time.sleep(random.uniform(1, 2))
        return True
    except Exception as e:
        logger.warning(f"Failed to follow: {e}")
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
            time.sleep(1.5)
            if not page.locator('[data-testid="sheetDialog"]').is_visible(timeout=2000):
                logger.info("Closed compose dialog")
                return True
            logger.warning("Close button clicked but compose still visible — trying Escape")
        page.keyboard.press("Escape")
        time.sleep(1.5)
        if not page.locator('[data-testid="sheetDialog"]').is_visible(timeout=2000):
            logger.info("Closed compose via Escape")
            return True
        logger.warning("Cancel compose failed — dialog persists")
        return False
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


def click_trend(page: Page, index: int = 0) -> bool:
    trends = page.locator(SELECTORS["trend_item"]).all()
    if index >= len(trends):
        logger.warning(f"Trend index {index} out of range ({len(trends)} trends)")
        return False
    try:
        _jitter_mouse(page)
        cell = trends[index]
        cell.scroll_into_view_if_needed(timeout=3000)
        time.sleep(random.uniform(0.3, 1))
        link = cell.locator('a, [role="link"]')
        if link.count() > 0:
            link.first.click(force=True, timeout=5000)
        else:
            cell.click(force=True, timeout=5000)
        logger.info(f"Clicked trend #{index}")
        time.sleep(random.uniform(1.5, 3))
        return True
    except Exception as e:
        logger.warning(f"Failed to click trend #{index}: {e}")
        return False


def scroll_down_long(page: Page, amount: int = 2500) -> bool:
    steps = random.randint(3, 6)
    try:
        for i in range(steps):
            step_px = random.randint(400, 900)
            page.mouse.wheel(0, step_px)
            time.sleep(random.uniform(1, 5))
        logger.info(f"Scrolled down long in {steps} steps")
        time.sleep(random.uniform(1, 2.5))
        return True
    except Exception as e:
        logger.warning(f"Long scroll down failed: {e}")
        return False


def search_topic(page: Page, query: str) -> bool:
    if not query:
        logger.warning("No search query provided")
        return False
    query = query[:50]  # truncate long queries
    try:
        search_input = page.locator(SELECTORS["search_box"])
        if search_input.count() == 0:
            logger.warning("Search box not found")
            return False
        _jitter_mouse(page)
        search_input.first.click(force=True, timeout=5000)
        time.sleep(random.uniform(0.5, 1.5))
        search_input.first.fill("")
        page.keyboard.type(query, delay=random.randint(30, 80))
        time.sleep(random.uniform(0.5, 1))
        page.keyboard.press("Enter")
        logger.info(f"Searched for: {query}")
        time.sleep(random.uniform(2, 4))
        return True
    except Exception as e:
        logger.warning(f"Search failed: {e}")
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
    "open_profile": lambda page, params: open_profile(page, params.get("tweet_index", 0)),
    "back": lambda page, params: go_back(page),
    "follow": lambda page, params: follow(page),
    "click_trend": lambda page, params: click_trend(page, params.get("tweet_index", 0)),
    "not_interested": lambda page, params: not_interested(page, params.get("tweet_index", 0)),
    "search_topic": lambda page, params: search_topic(page, params.get("text", "")),
    "rest": lambda page, params: rest(page),
}


def execute_action(page: Page, action_name: str, params: dict) -> bool:
    handler = ACTION_REGISTRY.get(action_name)
    if not handler:
        logger.warning(f"Unknown action: {action_name}")
        return False
    return handler(page, params)
