from abc import ABC, abstractmethod
from datetime import date

from src.models.schemas import FlightRecord


class BaseScraper(ABC):
    """Every scraper must implement these methods."""

    @abstractmethod
    async def fetch_flights(
        self, origin: str, dest: str, travel_date: date, lead_window_days: int
    ) -> list[FlightRecord]:
        """Scrape flights for one route on one date. Return validated records."""
        ...
