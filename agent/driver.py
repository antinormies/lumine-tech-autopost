import json
import os
import random
import time
import urllib.request
from typing import Optional

from playwright.sync_api import sync_playwright, Page, Browser, Playwright, BrowserContext

from config import config
from utils.logger import logger

COOKIES_PATH = os.path.join(os.path.dirname(__file__), "..", "twitter_cookies.json")


class BrowserDriver:
    def __init__(self, headless: bool | None = None):
        self.headless = headless if headless is not None else config.BROWSER_HEADLESS
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def start(self) -> Page:
        self._pw = sync_playwright().start()
        ws_endpoint = config.BROWSER_WS_ENDPOINT

        if ws_endpoint:
            return self._connect_existing(ws_endpoint)
        return self._launch_new()

    def _verify_endpoint(self, ws_endpoint: str) -> bool:
        try:
            urllib.request.urlopen(f"{ws_endpoint}/json/version", timeout=5)
            return True
        except Exception:
            return False

    def _connect_existing(self, ws_endpoint: str) -> Page:
        logger.info(f"Connecting to existing browser at {ws_endpoint}")
        if not self._verify_endpoint(ws_endpoint):
            logger.error(
                f"Cannot reach {ws_endpoint}/json/version — "
                f"make sure Chrome is running with: chrome --remote-debugging-port=9222"
            )
            raise RuntimeError(f"Browser not reachable at {ws_endpoint}")

        self._browser = self._pw.chromium.connect_over_cdp(ws_endpoint)
        contexts = self._browser.contexts
        if contexts:
            self._context = contexts[0]
        else:
            self._context = self._browser.new_context()
        if self._context.pages:
            self.page = self._context.pages[0]
        else:
            self.page = self._context.new_page()

        self.page.set_default_timeout(30000)
        logger.info(f"Connected to existing browser at {self.page.url}")
        return self.page

    def _launch_new(self) -> Page:
        user_data_dir = config.BROWSER_USER_DATA_DIR
        executable_path = config.BROWSER_EXECUTABLE_PATH or None
        browser_name = "Brave" if executable_path else "Chromium"
        logger.info(f"Launching {browser_name} (headless={self.headless}, user_data={user_data_dir or 'none'})")

        launch_kwargs = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        }
        if executable_path:
            launch_kwargs["executable_path"] = executable_path

        if user_data_dir:
            self._context = self._pw.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                **launch_kwargs,
                viewport={"width": 1280, "height": 720},
            )
            self._browser = self._context.browser
            self.page = self._context.pages[0] if self._context.pages else self._context.new_page()
        else:
            self._browser = self._pw.chromium.launch(**launch_kwargs)
            self._context = self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                ),
            )
            self._load_cookies(self._context)
            self.page = self._context.new_page()

        self._close_extra_tabs()
        self.page.set_default_timeout(30000)
        logger.info(f"Browser ready")
        return self.page

    def _load_cookies(self, context):
        if os.path.exists(COOKIES_PATH):
            with open(COOKIES_PATH) as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            logger.info(f"Loaded {len(cookies)} cookies")

    def save_cookies(self):
        if not self._context:
            return
        cookies = self._context.cookies()
        with open(COOKIES_PATH, "w") as f:
            json.dump(cookies, f)
        logger.info(f"Saved {len(cookies)} cookies")

    def _close_extra_tabs(self):
        if self._context:
            for p in self._context.pages[1:]:
                try:
                    p.close()
                except Exception:
                    pass

    def _go_to_home(self):
        try:
            self.page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=20000)
            time.sleep(2 + random.uniform(0.5, 2))
        except Exception:
            pass

    def is_logged_in(self) -> bool:
        try:
            self._go_to_home()
            if self.page.locator('[data-testid="SideNav_NewTweet_Button"]').is_visible(timeout=8000):
                logger.info("Already logged in")
                return True
        except Exception:
            pass
        return False

    def login(self):
        logger.info("Logging in to Twitter")
        self.page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")
        time.sleep(3)

        self.page.locator('input[autocomplete="username"]').fill(config.TWITTER_USERNAME)
        self.page.locator('//span[text()="Next"]').click()
        time.sleep(2)

        if self.page.locator('input[data-testid="ocfEnterTextTextInput"]').is_visible(timeout=3000):
            self.page.locator('input[data-testid="ocfEnterTextTextInput"]').fill(config.TWITTER_EMAIL)
            self.page.locator('//span[text()="Verify"]').click()
            time.sleep(2)

        self.page.locator('input[name="password"]').fill(config.TWITTER_PASSWORD)
        self.page.locator('//span[text()="Log in"]').click()
        time.sleep(5)

        self.save_cookies()
        logger.info("Login complete")

    def close(self):
        if self._pw:
            self._pw.stop()
        logger.info("Browser closed")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.close()
