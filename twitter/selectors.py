VISIBLE_TEXT_MAP: dict[str, str] = {
    "Explore": "explore_link",
    "explore": "explore_link",
    "Home": "home_link",
    "home": "home_link",
    "Search": "search_box",
    "search": "search_box",
    "Notifications": "notifications_link",
    "Post": "sidebar_tweet",
    "post": "sidebar_tweet",
    "Messages": "messages_link",
    "Like": "like_button",
    "like": "like_button",
    "Reply": "reply_button",
    "reply": "reply_button",
    "Retweet": "retweet_button",
    "retweet": "retweet_button",
    "Bookmark": "bookmark_button",
    "bookmark": "bookmark_button",
    "Trend": "explore_link",
    "trend": "explore_link",
    "Following": "home_link",
    "following": "home_link",
}


def resolve_target(target: str) -> str:
    clean = target.strip().lower()
    for key, mapped in VISIBLE_TEXT_MAP.items():
        if (
            clean == key.lower()
            or clean == f"{key.lower()} button"
            or clean == f"{key.lower()} section"
            or clean.startswith(key.lower())
        ):
            return mapped
    return target


SELECTORS = {
    # Login
    "login_username": 'input[autocomplete="username"]',
    "login_password": 'input[name="password"]',
    "next_button": '//span[text()="Next"]',
    "login_button": '//span[text()="Log in"]',
    "email_input": 'input[data-testid="ocfEnterTextTextInput"]',
    "verify_button": '//span[text()="Verify"]',
    # Compose
    "tweet_compose": '[data-testid="tweetTextarea_0"]',
    "tweet_button": '[data-testid="tweetButtonInline"]',
    "tweet_button_small": '[data-testid="tweetButton"]',
    "sidebar_tweet": '[data-testid="SideNav_NewTweet_Button"]',
    "compose_textarea": '[data-testid="tweetTextarea_0"]',
    # Timeline
    "tweet_article": 'article[data-testid="tweet"]',
    "tweet_text": '[data-testid="tweetText"]',
    "user_name": '[data-testid="User-Name"]',
    "primary_column": 'section[aria-label="Timeline"]',
    # Engagement
    "like_button": '[data-testid="like"]',
    "unlike_button": '[data-testid="unlike"]',
    "retweet_button": '[data-testid="retweet"], [data-testid="repost"]',
    "retweet_confirm": '[data-testid="retweetConfirm"], [data-testid="repostConfirm"]',
    "quote_option": '[data-testid="quote"]',
    "bookmark_button": '[data-testid="bookmark"]',
    "reply_button": '[data-testid="reply"]',
    # Navigation
    "home_link": '[data-testid="AppTabBar_Home_Link"]',
    "explore_link": '[data-testid="AppTabBar_Explore_Link"]',
    "notifications_link": '[data-testid="AppTabBar_Notifications_Link"]',
    "messages_link": '[data-testid="AppTabBar_DirectMessage_Link"]',
    # Layout
    "trends_panel": '[data-testid="sidebarColumn"]',
    "search_box": '[data-testid="SearchBox_Search_Input"]',
    # Compose dialog
    "cancel_compose": '[data-testid="app-bar-close"]',
    "compose_close": '[data-testid="close"]',
    # Profile
    "follow_button": '[data-testid="followButton"]',
    "unfollow_button": '[data-testid="unfollowButton"]',
    "user_name_link": '[data-testid="User-Name"] a',
    "tweet_caret": '[data-testid="caret"]',
    "not_interested": '[role="menuitem"]:has-text("Mute"), [role="menuitem"]:has-text("Not interested"), [role="menuitem"]:has-text("Show fewer")',
    # Trends
    "trend_item": '[data-testid="trend"]',
    "explore_trends": '//span[contains(text(), "Trends")]',
    "trending_tab": '[role="tablist"] [role="tab"]:has-text("Trending")',
    "for_you_tab": '[role="tablist"] [role="tab"]:has-text("For you")',
    "show_more": '//span[contains(text(), "Show more")]',
}

ELEMENT_DESCRIPTIONS = {
    "tweet_compose": "the tweet composition textarea",
    "tweet_button": "the send tweet button",
    "sidebar_tweet": "the new tweet button in the sidebar",
    "like_button": "the like/heart button on a tweet",
    "retweet_button": "the retweet button on a tweet",
    "bookmark_button": "the bookmark button on a tweet",
    "reply_button": "the reply/comment button on a tweet",
    "home_link": "the Home navigation link",
    "explore_link": "the Explore navigation link",
    "cancel_compose": "the close/cancel button on the compose dialog",
    "tweet_article": "a tweet to open and view details",
    "trend_item": "a trending topic",
    "follow_button": "the follow button",
    "user_name_link": "the tweet author name",
    "not_interested": "mark a post as not interested",
}
