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
    "Trending": "explore_link",
    "trending": "explore_link",
    "For you": "home_link",
    "for you": "home_link",
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
    "retweet_button": '[data-testid="retweet"]',
    "retweet_confirm": '[data-testid="retweetConfirm"]',
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
}
