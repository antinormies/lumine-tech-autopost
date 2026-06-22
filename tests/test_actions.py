from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from playwright.sync_api import Page

from agent.actions import (
    BLOCKED_CLICKS,
    ACTION_REGISTRY,
    cancel_compose,
    clean_text,
    click,
    execute_action,
    find_element,
    go_back,
    like_comment,
    like_nth_tweet,
    navigate,
    open_tweet,
    quote_tweet,
    reply_to_tweet,
    rest,
    retweet_nth,
    bookmark_nth,
    scroll_down,
    scroll_down_long,
    scroll_up,
    tweet,
    type_text,
    wait,
)
from twitter.selectors import SELECTORS


@pytest.fixture(autouse=True)
def _mock_time_sleep():
    with patch("time.sleep"):
        yield


@pytest.fixture
def page():
    return MagicMock(spec=Page)


def _make_locator(visible=True, count=1, enabled=True, **kwargs):
    loc = MagicMock()
    loc.is_visible.return_value = visible
    loc.is_enabled.return_value = enabled
    loc.count.return_value = count
    type(loc).first = PropertyMock(return_value=loc)
    for k, v in kwargs.items():
        setattr(loc, k, v)
    return loc


def _make_article(locator_return=None):
    a = MagicMock()
    if locator_return is not None:
        a.locator.return_value = locator_return
    else:
        like = _make_locator()
        a.locator.return_value = like
    return a


def _make_tweet_articles(n=3):
    btn = _make_locator()
    articles = [_make_article(locator_return=MagicMock()) for _ in range(n)]
    for a in articles:
        a.locator.return_value = btn
    return articles, btn


# ─── clean_text ───


class TestCleanText:
    def test_removes_hashtags(self):
        assert clean_text("Hello #World") == "Hello"

    def test_removes_mentions(self):
        assert clean_text("Hello @user") == "Hello"

    def test_removes_wide_hashtags(self):
        assert clean_text("Hello ＃World") == "Hello"

    def test_removes_wide_mentions(self):
        assert clean_text("Hello ＠user") == "Hello"

    def test_normalizes_whitespace(self):
        assert clean_text("Hello   World") == "Hello World"

    def test_empty_becomes_dot(self):
        assert clean_text("") == "."

    def test_only_hashtag_becomes_dot(self):
        assert clean_text("#foo") == "."

    def test_mixed_clean(self):
        assert clean_text("Check out #trend @someone  here") == "Check out here"

    def test_no_change_needed(self):
        assert clean_text("Hello World") == "Hello World"


# ─── find_element ───


class TestFindElement:
    def test_by_selector(self, page):
        loc = _make_locator()
        page.locator.return_value = loc
        result = find_element(page, "like_button")
        assert result is not None

    def test_by_text_when_no_selector(self, page):
        empty = MagicMock()
        empty.count.return_value = 0
        page.locator.return_value = empty
        text_loc = _make_locator()
        page.get_by_text.return_value = text_loc
        result = find_element(page, "Some Text")
        page.get_by_text.assert_called_with("Some Text", exact=False)

    def test_by_data_testid_fallback(self, page):
        empty = MagicMock()
        empty.count.return_value = 0
        page.locator.return_value = empty
        page.get_by_text.return_value = MagicMock()
        page.get_by_text.return_value.count.return_value = 0
        fallback = _make_locator()
        page.locator.return_value = fallback
        result = find_element(page, "custom-id")

    def test_resolves_visible_text_target(self, page):
        loc = _make_locator()
        page.locator.return_value = loc
        result = find_element(page, "Explore")
        page.locator.assert_called_with('[data-testid="AppTabBar_Explore_Link"]')


# ─── BLOCKED_CLICKS ───


class TestBlockedClicks:
    def test_blocked_targets_are_defined(self):
        assert "follow" in BLOCKED_CLICKS
        assert "following" in BLOCKED_CLICKS
        assert "unfollow" in BLOCKED_CLICKS
        assert "like" in BLOCKED_CLICKS
        assert "direct_message" in BLOCKED_CLICKS
        assert "send" in BLOCKED_CLICKS

    @pytest.mark.parametrize("target", ["follow", "unfollow"])
    def test_click_returns_false_for_blocked(self, page, target):
        assert click(page, target) is False

    def test_click_blocked_like_resolves_to_like_button(self, page):
        assert click(page, "like") is True

    def test_click_no_target(self, page):
        assert click(page, "") is False


# ─── click ───


class TestClick:
    def test_click_success(self, page):
        loc = _make_locator()
        page.locator.return_value = loc
        assert click(page, "explore_link") is True
        loc.click.assert_called_once_with(force=True, timeout=5000)

    def test_click_exception(self, page):
        loc = _make_locator()
        loc.scroll_into_view_if_needed.side_effect = Exception("fail")
        page.locator.return_value = loc
        assert click(page, "explore_link") is False


# ─── type_text ───


class TestTypeText:
    def test_type_into_compose(self, page):
        textarea = _make_locator()
        page.locator.return_value = textarea
        with patch("agent.actions.clean_text", return_value="hello"):
            with patch("agent.actions.random.randint", return_value=30):
                assert type_text(page, "compose", "hello #world") is True
        textarea.focus.assert_called_once()

    def test_type_into_compose_not_visible(self, page):
        textarea = _make_locator(visible=False)
        page.locator.return_value = textarea
        assert type_text(page, "compose", "hello") is False

    def test_type_into_specific_element(self, page):
        loc = _make_locator()
        page.locator.return_value = loc
        assert type_text(page, "search_box", "query") is True
        page.keyboard.insert_text.assert_called_with("query")

    def test_type_specific_element_exception(self, page):
        loc = _make_locator()
        loc.click.side_effect = Exception("fail")
        page.locator.return_value = loc
        assert type_text(page, "search_box", "query") is False


# ─── scroll_down / scroll_up ───


class TestScroll:
    def test_scroll_down(self, page):
        assert scroll_down(page) is True
        assert page.evaluate.called
        args = [c[0][0] for c in page.evaluate.call_args_list]
        assert all("window.scrollBy(0," in a for a in args)

    def test_scroll_down_exception(self, page):
        page.evaluate.side_effect = Exception("fail")
        assert scroll_down(page) is False

    def test_scroll_up(self, page):
        assert scroll_up(page) is True
        args = [c[0][0] for c in page.evaluate.call_args_list]
        assert all("window.scrollBy(0, -" in a for a in args)

    def test_scroll_up_exception(self, page):
        page.evaluate.side_effect = Exception("fail")
        assert scroll_up(page) is False

    def test_scroll_down_long(self, page):
        assert scroll_down_long(page) is True
        args = [c[0][0] for c in page.evaluate.call_args_list]
        assert all("window.scrollBy(0," in a for a in args)
        assert len(args) >= 8

    def test_scroll_down_long_exception(self, page):
        page.evaluate.side_effect = Exception("fail")
        assert scroll_down_long(page) is False


# ─── navigate ───


class TestNavigate:
    def test_navigate(self, page):
        assert navigate(page, "https://x.com/home") is True
        page.goto.assert_called_with("https://x.com/home", wait_until="domcontentloaded")


# ─── wait ───


class TestWait:
    def test_wait(self, page):
        with patch("time.sleep") as mock_sleep:
            assert wait(5) is True
        mock_sleep.assert_called_with(5)


# ─── tweet ───


class TestTweet:
    def test_tweet_success(self, page):
        textarea = _make_locator()
        textarea.wait_for.return_value = None
        post_btn = _make_locator(enabled=True)

        def locator_side(sel):
            if sel == SELECTORS["tweet_compose"]:
                return textarea
            if "tweetButton" in sel:
                return post_btn
            return _make_locator()

        page.locator.side_effect = locator_side

        with patch("agent.actions.clean_text", return_value="hello world"):
            assert tweet(page, "hello #world") is True
        textarea.focus.assert_called_once()

    def test_tweet_from_sidebar(self, page):
        textarea = _make_locator(visible=False)
        textarea.wait_for.return_value = None
        sidebar = _make_locator()
        post_btn = _make_locator(enabled=True)

        def locator_side(sel):
            if sel == SELECTORS["tweet_compose"]:
                return textarea
            if sel == SELECTORS["sidebar_tweet"]:
                return sidebar
            if "tweetButton" in sel:
                return post_btn
            return _make_locator()

        page.locator.side_effect = locator_side
        textarea.is_visible.side_effect = [False, True]

        with patch("agent.actions.clean_text", return_value="hello"):
            assert tweet(page, "hello") is True
        sidebar.click.assert_called_once()

    def test_tweet_exception(self, page):
        page.locator.side_effect = Exception("fail")
        assert tweet(page, "text") is False


# ─── like_nth_tweet ───


class TestLikeNthTweet:
    def test_like_success(self, page):
        articles, btn = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        assert like_nth_tweet(page, 0) is True

    def test_like_index_out_of_range(self, page):
        articles, _ = _make_tweet_articles(n=2)
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        assert like_nth_tweet(page, 5) is False

    def test_like_exception(self, page):
        articles, _ = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        articles[0].locator.side_effect = Exception("fail")
        assert like_nth_tweet(page, 0) is False


# ─── reply_to_tweet ───


class TestReplyToTweet:
    def test_reply_success(self, page):
        articles, btn = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles

        reply_area = _make_locator()
        tweet_btn = _make_locator()

        def locator_side(sel):
            if sel == SELECTORS["tweet_compose"]:
                return reply_area
            if sel == '[data-testid="tweetButton"]':
                return tweet_btn
            m = MagicMock()
            m.all.return_value = articles
            return m

        page.locator.side_effect = locator_side

        with patch("agent.actions.clean_text", return_value="nice post"):
            assert reply_to_tweet(page, 0, "nice post") is True
        btn.click.assert_called_once()

    def test_reply_index_out_of_range(self, page):
        articles, _ = _make_tweet_articles(n=1)
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        assert reply_to_tweet(page, 5, "text") is False

    def test_reply_exception(self, page):
        articles, _ = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        articles[0].locator.side_effect = Exception("fail")
        assert reply_to_tweet(page, 0, "text") is False


# ─── retweet_nth ───


class TestRetweetNth:
    def test_retweet_success(self, page):
        articles, btn = _make_tweet_articles()
        confirm = _make_locator()

        def locator_side(sel):
            if sel == SELECTORS["retweet_confirm"]:
                return confirm
            m = MagicMock()
            m.all.return_value = articles
            return m

        page.locator.side_effect = locator_side
        assert retweet_nth(page, 0) is True
        btn.click.assert_called_once()
        confirm.click.assert_called_once()

    def test_retweet_index_out_of_range(self, page):
        articles, _ = _make_tweet_articles(n=1)
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        assert retweet_nth(page, 5) is False

    def test_retweet_exception(self, page):
        articles, _ = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        articles[0].locator.side_effect = Exception("fail")
        assert retweet_nth(page, 0) is False


# ─── quote_tweet ───


class TestQuoteTweet:
    def test_quote_success(self, page):
        articles, btn = _make_tweet_articles()
        quote_btn = _make_locator()
        compose = _make_locator()
        compose.wait_for.return_value = None
        post_small = _make_locator(visible=False)
        post_btn = _make_locator(enabled=True)

        def locator_side(sel):
            mapping = {
                SELECTORS["quote_option"]: quote_btn,
                SELECTORS["tweet_compose"]: compose,
                SELECTORS["tweet_button_small"]: post_small,
                SELECTORS["tweet_button"]: post_btn,
            }
            if sel in mapping:
                return mapping[sel]
            m = MagicMock()
            m.all.return_value = articles
            return m

        page.locator.side_effect = locator_side
        page.keyboard.type.return_value = None

        with patch("agent.actions.clean_text", return_value="great point"):
            assert quote_tweet(page, 0, "great point") is True
        page.keyboard.type.assert_called()

    def test_quote_index_out_of_range(self, page):
        articles, _ = _make_tweet_articles(n=1)
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        assert quote_tweet(page, 5, "text") is False

    def test_quote_exception(self, page):
        articles, _ = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        articles[0].locator.side_effect = Exception("fail")
        assert quote_tweet(page, 0, "text") is False


# ─── bookmark_nth ───


class TestBookmarkNth:
    def test_bookmark_success(self, page):
        articles, btn = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        assert bookmark_nth(page, 0) is True
        btn.click.assert_called_once()

    def test_bookmark_index_out_of_range(self, page):
        articles, _ = _make_tweet_articles(n=1)
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        assert bookmark_nth(page, 5) is False

    def test_bookmark_exception(self, page):
        articles, _ = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        articles[0].locator.side_effect = Exception("fail")
        assert bookmark_nth(page, 0) is False


# ─── open_tweet ───


class TestOpenTweet:
    def test_open_success(self, page):
        articles, _ = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        assert open_tweet(page, 0) is True
        articles[0].click.assert_called_once_with(force=True, timeout=5000)

    def test_open_index_out_of_range(self, page):
        articles, _ = _make_tweet_articles(n=1)
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        assert open_tweet(page, 5) is False

    def test_open_exception(self, page):
        articles, _ = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        articles[0].click.side_effect = Exception("fail")
        assert open_tweet(page, 0) is False


# ─── like_comment ───


class TestLikeComment:
    def test_like_comment_success(self, page):
        articles, btn = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        assert like_comment(page, 0) is True
        btn.click.assert_called_once()

    def test_like_comment_index_out_of_range(self, page):
        articles, _ = _make_tweet_articles(n=1)
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        assert like_comment(page, 5) is False

    def test_like_comment_exception(self, page):
        articles, _ = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        articles[0].locator.side_effect = Exception("fail")
        assert like_comment(page, 0) is False


# ─── go_back ───


class TestGoBack:
    def test_go_back(self, page):
        assert go_back(page) is True
        page.go_back.assert_called_with(wait_until="domcontentloaded")

    def test_go_back_exception(self, page):
        page.go_back.side_effect = Exception("fail")
        assert go_back(page) is False


# ─── cancel_compose ───


class TestCancelCompose:
    def test_cancel_via_close_button(self, page):
        close_btn = _make_locator()
        page.locator.return_value = close_btn
        assert cancel_compose(page) is True
        close_btn.click.assert_called_once()

    def test_cancel_via_escape(self, page):
        close_btn = _make_locator(visible=False)
        page.locator.return_value = close_btn
        assert cancel_compose(page) is True
        page.keyboard.press.assert_called_with("Escape")

    def test_cancel_exception(self, page):
        page.locator.side_effect = Exception("fail")
        assert cancel_compose(page) is False


# ─── rest ───


class TestRest:
    def test_rest_success(self, page):
        page.goto.return_value = None
        with patch("time.sleep"):
            assert rest(page) is True
            page.goto.assert_called_once()

    def test_rest_exception(self, page):
        page.goto.side_effect = Exception("fail")
        with patch("time.sleep"):
            assert rest(page) is False


# ─── ACTION_REGISTRY ───


class TestActionRegistry:
    def test_all_actions_have_handlers(self):
        expected = {
            "click", "type", "scroll_down", "scroll_up", "scroll",
            "scroll_down_long",
            "post", "navigate", "wait", "tweet", "like", "reply",
            "retweet", "quote", "bookmark", "compose", "cancel_compose",
            "open_tweet", "like_comment", "back", "rest",
        }
        assert set(ACTION_REGISTRY.keys()) == expected
        assert len(ACTION_REGISTRY) == 21

    @pytest.mark.parametrize("action_name", [
        "click", "type", "scroll_down", "scroll_up", "scroll",
        "scroll_down_long",
        "post", "navigate", "wait", "tweet", "like", "reply",
        "retweet", "quote", "bookmark", "compose", "cancel_compose",
        "open_tweet", "like_comment", "back", "rest",
    ])
    def test_each_action_is_callable(self, action_name):
        handler = ACTION_REGISTRY.get(action_name)
        assert handler is not None
        page = MagicMock(spec=Page)
        params = {}
        result = handler(page, params)
        assert result is not None


# ─── execute_action ───


class TestExecuteAction:
    def test_unknown_action(self, page):
        assert execute_action(page, "fly_to_moon", {}) is False

    def test_known_action(self, page):
        loc = _make_locator()
        page.locator.return_value = loc
        assert execute_action(page, "click", {"target": "explore_link"}) is True

    @pytest.mark.parametrize("action,params", [
        ("scroll_down", {}),
        ("scroll_up", {}),
        ("scroll", {}),
        ("scroll_down_long", {}),
        ("wait", {"seconds": 1}),
        ("navigate", {"url": "https://x.com/home"}),
        ("cancel_compose", {}),
        ("back", {}),
        ("rest", {}),
    ])
    def test_basic_actions_via_execute(self, page, action, params):
        with patch("time.sleep"):
            result = execute_action(page, action, params)
            assert result is not None

    def test_execute_tweet(self, page):
        textarea = _make_locator()
        post_btn = _make_locator(enabled=True)

        def locator_side(sel):
            if "tweetButton" in sel:
                return post_btn
            return textarea

        page.locator.side_effect = locator_side
        with patch("agent.actions.clean_text", return_value="hello"):
            with patch("time.sleep"):
                assert execute_action(page, "tweet", {"text": "hello"}) is True

    def test_execute_like(self, page):
        articles, _ = _make_tweet_articles()
        page.locator.return_value = MagicMock()
        page.locator.return_value.all.return_value = articles
        with patch("time.sleep"):
            assert execute_action(page, "like", {"tweet_index": 0}) is True
