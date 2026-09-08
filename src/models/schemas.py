from datetime import datetime
from pydantic import BaseModel, Field


class FlightRecord(BaseModel):
    """One scraped flight — the raw unit of data we collect."""

    route: str = Field(..., description="e.g. DEL-BOM")
    origin: str = Field(..., min_length=3, max_length=3)
    dest: str = Field(..., min_length=3, max_length=3)
    carrier: str = Field(..., description="e.g. IndiGo")
    flight_no: str = Field(..., description="e.g. 6E-201")
    depart_time: datetime
    arrive_time: datetime
    duration_mins: int = Field(..., ge=0)
    stops: int = Field(..., ge=0, le=5)
    base_fare: float = Field(default=0.0, ge=0)
    taxes: float = Field(default=0.0, ge=0)
    total_fare: float = Field(..., gt=0)
    currency: str = Field(default="INR", max_length=3)
    lead_window_days: int = Field(..., ge=1, le=90)
    scrape_timestamp: datetime = Field(default_factory=datetime.now)


class RouteConfig(BaseModel):
    """One route from routes.yaml."""

    origin: str
    dest: str


class CityConfig(BaseModel):
    """One city from routes.yaml."""

    name: str
    code: str
    weight: float = Field(..., ge=0, le=1)


class IndexEntry(BaseModel):
    """One row in the daily_index / weekly_index / monthly_index tables."""

    index_date: str
    route: str
    weight: float
    route_price: float
    route_index: float
    aggregate_index: float
    base_period: str
