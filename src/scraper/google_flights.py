"""Google Flights scraper using Playwright.

Strategy: Google Flights embeds structured aria-label text on each flight card
that contains price, carrier, times, duration, and stops in plain English.
We parse this aria-label instead of hunting for fragile CSS class names.
"""
import asyncio
import logging
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import yaml
from playwright.async_api import Page, TimeoutError as PwTimeout

from src.scraper.base import BaseScraper
from src.scraper.driver import create_browser_context, load_scraper_config
from src.models.schemas import FlightRecord

log = logging.getLogger(__name__)

ROUTES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "routes.yaml"

CITY_NAMES = {
    "DEL": "New Delhi",
    "BOM": "Mumbai",
    "BLR": "Bengaluru",
    "MAA": "Chennai",
}


def _load_routes() -> dict:
    with open(ROUTES_PATH) as f:
        return yaml.safe_load(f)


class GoogleFlightsScraper(BaseScraper):
    """Scrapes one-way flight results from Google Flights via aria-label parsing."""

    def __init__(self, config: dict | None = None):
        self.cfg = config or load_scraper_config()
        self.max_retries = self.cfg.get("max_retries", 3)
        self.backoff = self.cfg.get("backoff_multiplier", 2)
        self.delay_min = self.cfg["delay_between_requests"]["min_seconds"]
        self.delay_max = self.cfg["delay_between_requests"]["max_seconds"]
        self._hourly_count = 0
        self._hour_limit = self.cfg.get("max_requests_per_hour", 60)

    # ── Public API ──────────────────────────────────────────────────────

    async def fetch_flights(
        self,
        origin: str,
        dest: str,
        travel_date: date,
        lead_window_days: int,
    ) -> list[FlightRecord]:
        base_delay = self.delay_min
        last_err: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                await self._respect_rate_limit()
                result = await self._scrape(origin, dest, travel_date, lead_window_days)
                self._hourly_count += 1
                return result
            except PwTimeout as exc:
                last_err = exc
                wait = base_delay * (self.backoff ** (attempt - 1))
                log.warning(
                    "Timeout on %s->%s (attempt %d/%d) - retrying in %.1fs",
                    origin, dest, attempt, self.max_retries, wait,
                )
                await asyncio.sleep(wait)
            except Exception as exc:
                last_err = exc
                wait = base_delay * (self.backoff ** (attempt - 1))
                log.warning(
                    "Error on %s->%s (attempt %d/%d): %s - retrying in %.1fs",
                    origin, dest, attempt, self.max_retries, exc, wait,
                )
                await asyncio.sleep(wait)

        log.error("All %d attempts failed for %s->%s", self.max_retries, origin, dest)
        raise last_err  # type: ignore[misc]

    # ── Internal ────────────────────────────────────────────────────────

    async def _respect_rate_limit(self) -> None:
        if self._hourly_count >= self._hour_limit:
            log.warning("Rate limit reached (%d req/h). Waiting 60s.", self._hour_limit)
            await asyncio.sleep(60)
            self._hourly_count = 0
        delay = random.uniform(self.delay_min, self.delay_max)
        await asyncio.sleep(delay)

    async def _scrape(
        self,
        origin: str,
        dest: str,
        travel_date: date,
        lead_window_days: int,
    ) -> list[FlightRecord]:
        async with create_browser_context(self.cfg) as ctx:
            page = await ctx.new_page()
            url = self._build_url(origin, dest, travel_date)
            log.info("Navigating: %s", url)
            await page.goto(url, wait_until="domcontentloaded")
            await self._wait_for_results(page)
            await self._random_delay(3.0, 6.0)

            labels = await self._collect_aria_labels(page)
            log.info("Collected %d aria-labels from page", len(labels))

            records: list[FlightRecord] = []
            for label in labels:
                rec = self._parse_aria_label(
                    label, origin, dest, travel_date, lead_window_days
                )
                if rec:
                    records.append(rec)

            log.info("Parsed %d valid flights for %s->%s", len(records), origin, dest)
            return records

    # ── URL builder ─────────────────────────────────────────────────────

    @staticmethod
    def _build_url(origin: str, dest: str, travel_date: date) -> str:
        date_str = travel_date.strftime("%Y-%m-%d")
        o_name = CITY_NAMES.get(origin, origin)
        d_name = CITY_NAMES.get(dest, dest)
        query = f"Flights from {o_name} to {d_name} on {date_str}"
        return f"https://www.google.com/travel/flights?q={quote(query)}&hl=en&curr=INR"

    # ── Wait for flight results ─────────────────────────────────────────

    async def _wait_for_results(self, page: Page) -> None:
        selectors = [
            "li.pIav2d",
            "div[role='link'][aria-label*='flight']",
            "li[class*='pIav2d']",
            "ul[role='list'] > li",
        ]
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=15000)
                log.debug("Results loaded with: %s", sel)
                return
            except PwTimeout:
                continue
        log.warning("No result selector matched after 15s - page may have no flights")

    # ── Collect all aria-labels from flight cards ────────────────────────

    async def _collect_aria_labels(self, page: Page) -> list[str]:
        """Google Flights puts full flight descriptions in aria-label on
        div.JMc5Xc elements (one per flight card).

        Uses page.evaluate() for reliability — runs JS directly in the browser.
        """
        labels: list[str] = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('[aria-label]').forEach(el => {
                    const label = el.getAttribute('aria-label');
                    if (label && label.includes('rupees') && label.includes('flight')) {
                        results.push(label);
                    }
                });
                return results;
            }
        """)
        return labels

    # ── Parse one aria-label string into a FlightRecord ─────────────────

    def _parse_aria_label(
        self,
        label: str,
        origin: str,
        dest: str,
        travel_date: date,
        lead_window_days: int,
    ) -> FlightRecord | None:
        try:
            price = self._extract_price_from_label(label)
            carrier = self._extract_carrier_from_label(label)
            stops = self._extract_stops_from_label(label)
            dep_time = self._extract_time_from_label(label, which="departure")
            arr_time = self._extract_time_from_label(label, which="arrival")
            duration = self._extract_duration_from_label(label)

            if price is None or carrier is None:
                log.debug("Missing price or carrier in label, skipping")
                return None

            if not dep_time:
                log.debug("No departure time found in label, skipping")
                return None

            dep_dt = self._to_datetime(dep_time, travel_date)

            if arr_time:
                arr_dt = self._to_datetime(arr_time, travel_date)
            elif duration:
                arr_dt = dep_dt + timedelta(minutes=duration)
            else:
                log.debug("No arrival time or duration found, skipping")
                return None

            if arr_dt < dep_dt:
                arr_dt += timedelta(days=1)

            return FlightRecord(
                route=f"{origin}-{dest}",
                origin=origin,
                dest=dest,
                carrier=carrier,
                flight_no="N/A",
                depart_time=dep_dt,
                arrive_time=arr_dt,
                duration_mins=duration or 120,
                stops=stops,
                base_fare=0.0,
                taxes=0.0,
                total_fare=float(price),
                currency="INR",
                lead_window_days=lead_window_days,
                scrape_timestamp=datetime.now(),
            )
        except Exception as exc:
            log.debug("Label parse failed: %s | label=%s", exc, label[:80])
            return None

    # ── Extractors (all work on raw aria-label text) ────────────────────

    @staticmethod
    def _extract_price_from_label(label: str) -> int | None:
        """'From 12882 Indian rupees' -> 12882"""
        m = re.search(r"From\s+([\d,]+)\s+Indian\s+rupees", label)
        if m:
            return int(m.group(1).replace(",", ""))
        m = re.search(r"([\d,]+)\s*(?:Indian\s+)?rupees?", label)
        if m:
            return int(m.group(1).replace(",", ""))
        return None

    @staticmethod
    def _extract_carrier_from_label(label: str) -> str | None:
        """'Nonstop flight with IndiGo' -> 'IndiGo'"""
        m = re.search(r"with\s+(.+?)(?:\.|Leaves|$)", label)
        if m:
            return m.group(1).strip()
        return None

    @staticmethod
    def _extract_stops_from_label(label: str) -> int:
        """'Nonstop flight' -> 0, '1 stop flight' -> 1"""
        low = label.lower()
        if "nonstop" in low or "non-stop" in low:
            return 0
        m = re.search(r"(\d+)\s+stop", low)
        if m:
            return int(m.group(1))
        return 0

    @staticmethod
    def _extract_time_from_label(label: str, which: str) -> str | None:
        """Extract departure or arrival time.
        Pattern: 'Leaves ... at 8:45 AM ... arrives ... at 11:00 AM'"""
        times = re.findall(r"at\s+(\d{1,2}:\d{2}\s*[AP]M)", label, re.IGNORECASE)
        if not times:
            times = re.findall(r"(\d{1,2}:\d{2}\s*[AP]M)", label, re.IGNORECASE)
        if len(times) >= 2:
            return times[0] if which == "departure" else times[1]
        if len(times) == 1:
            log.debug("Only 1 time found in label, need both departure and arrival — skipping")
            return None
        return None

    @staticmethod
    def _extract_duration_from_label(label: str) -> int | None:
        """'Total duration 2 hr 15 min' -> 135"""
        m = re.search(r"Total duration\s+(\d+)\s*hr?\s*(\d*)\s*min?", label, re.IGNORECASE)
        if m:
            hours = int(m.group(1))
            mins = int(m.group(2)) if m.group(2) else 0
            return hours * 60 + mins
        m = re.search(r"(\d+)\s*hr?\s*(\d*)\s*min?", label, re.IGNORECASE)
        if m:
            hours = int(m.group(1))
            mins = int(m.group(2)) if m.group(2) else 0
            return hours * 60 + mins
        return None

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _to_datetime(time_str: str, d: date) -> datetime:
        t = time_str.strip().replace(".", ":")
        for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
            try:
                parsed = datetime.strptime(t, fmt)
                return datetime.combine(d, parsed.time())
            except ValueError:
                continue
        return datetime.combine(d, datetime.min.time())

    @staticmethod
    async def _random_delay(lo: float, hi: float) -> None:
        await asyncio.sleep(random.uniform(lo, hi))
