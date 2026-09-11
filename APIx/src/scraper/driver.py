import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "scraper.yaml"
log = logging.getLogger(__name__)


def load_scraper_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)["scraper"]


@asynccontextmanager
async def create_browser_context(config: dict | None = None):
    """Launch headless Chromium and yield a fresh browser context.

    Usage:
        async with create_browser_context() as context:
            page = await context.new_page()
            await page.goto("https://google.com")
    """
    cfg = config or load_scraper_config()

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=cfg.get("headless", True),
        )
        context: BrowserContext = await browser.new_context(
            viewport={
                "width": cfg.get("viewport_width", 1280),
                "height": cfg.get("viewport_height", 900),
            },
            user_agent=cfg.get("user_agent"),
        )
        context.set_default_timeout(cfg.get("page_load_timeout", 30) * 1000)
        log.info("Browser context created")
        try:
            yield context
        finally:
            await context.close()
            await browser.close()
            log.info("Browser closed")
