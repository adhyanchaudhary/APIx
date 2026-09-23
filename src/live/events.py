"""Live index event types — the payload an engine tick produces.

A single IndexUpdate is the JSON-able unit the live engine emits every time a
cell median moves.  Consumers (CLI logger, SQLite writer, a future Streamlit
tab) subscribe through SubscriberHub and receive these as they happen — the
engine knows nothing about who is listening.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Callable, Sequence


@dataclass(frozen=True)
class IndexUpdate:
    """One recorded move of the live APIx headline.

    ``delta`` is the change in the *aggregate* index caused by this tick
    (not the per-route change).  ``route_index`` and ``route_price`` are the
    cell's new values after the update.  ``open_index``/``close_index`` are
    today's day-session brackets: open is frozen at the first value of the
    day, close is the latest headline.
    """

    index_date: str
    tick_timestamp: datetime
    route: str
    lead_window_days: int
    route_price: float
    route_index: float
    aggregate_index: float
    delta: float
    estimator: str
    open_index: float | None = None
    close_index: float | None = None

    def to_dict(self) -> dict:
        """Plain-dict form suitable for logging or SQLite writes."""
        d = asdict(self)
        d["tick_timestamp"] = self.tick_timestamp.isoformat(timespec="seconds")
        return d


@dataclass
class SubscriberHub:
    """A single-place emit/subscribe bus for index updates.

    The engine calls ``emit``; anything that wants to react registers a
    callback via ``subscribe``.  A callback that raises is logged through the
    module logger so one broken subscriber can never kill the live loop.
    """

    _subscribers: list[Callable[[IndexUpdate], None]] = field(default_factory=list)

    def subscribe(self, callback: Callable[[IndexUpdate], None]) -> Callable[[IndexUpdate], None]:
        """Register ``callback`` and return it, so ``unsubscribe`` works."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)
        return callback

    def unsubscribe(self, callback: Callable[[IndexUpdate], None]) -> None:
        """Remove a previously registered callback (idempotent)."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def emit(self, update: IndexUpdate) -> None:
        """Fan an update out to every subscriber, isolating failures."""
        for callback in list(self._subscribers):
            try:
                callback(update)
            except Exception as exc:  # noqa: BLE001 - a bad subscriber must not break the feed
                import logging

                logging.getLogger(__name__).exception("Subscriber %r failed: %s", callback, exc)

    def callbacks(self) -> Sequence[Callable[[IndexUpdate], None]]:
        """Return the current subscribers (read-only view)."""
        return tuple(self._subscribers)