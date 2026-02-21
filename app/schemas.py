from __future__ import annotations

from datetime import date
from pydantic import BaseModel, Field


class TripRequest(BaseModel):
    origin_city: str = Field(..., description="Origin city")
    destination_city: str = Field(..., description="Destination city")
    start_date: date = Field(..., description="Start date")
    days: int = Field(..., ge=1, le=30, description="Number of days")
    travelers: int = Field(1, ge=1, le=20, description="Number of travelers")
    budget_level: str | None = Field(None, description="Budget level: budget/moderate/premium")
    hotel_level: str | None = Field(None, description="Hotel level: budget/comfort/premium")
    preferences: list[str] = Field(default_factory=list, description="Preference tags")
    pace: str = Field("balanced", description="Pace: relaxed/balanced/fast")


class POIItem(BaseModel):
    name: str
    location: str | None = None
    address: str | None = None
    type: str | None = None
    tel: str | None = None


class WeatherInfo(BaseModel):
    city: str | None = None
    weather: str | None = None
    temperature: str | None = None
    report_time: str | None = None


class RouteInfo(BaseModel):
    distance: str | None = None
    duration: str | None = None
    taxi_cost: str | None = None


class DayPlan(BaseModel):
    day_index: int
    title: str
    schedule: list[str]


class TripPlan(BaseModel):
    overview: str
    days: list[DayPlan]
    attractions: list[POIItem] = []
    hotels: list[POIItem] = []
    weather: WeatherInfo | None = None
    route: RouteInfo | None = None


class TripResponse(BaseModel):
    request: TripRequest
    plan: TripPlan
    raw: dict
