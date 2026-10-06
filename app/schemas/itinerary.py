"""Schemas for structured itineraries and validation results."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.hotel import Hotel
from app.schemas.places import Place
from app.schemas.trip import TripRequest
from app.schemas.weather import DailyWeather


class DayPlan(BaseModel):
    """Itinerary schedule for a single day."""

    day_number: int = Field(..., ge=1, description="Day number (1-indexed)")
    date: Optional[str] = Field(default=None, description="Date of the day plan (YYYY-MM-DD) if known")
    weather_summary: Optional[str] = Field(default=None, description="Expected weather for this day")
    places: list[Place] = Field(default_factory=list, description="Ordered list of places to visit on this day")
    theme_or_notes: Optional[str] = Field(default=None, description="Daily theme, routing notes, or rationale")


class ValidationResult(BaseModel):
    """Deterministic validation output for an itinerary."""

    is_valid: bool = Field(..., description="Whether the itinerary passes all strict validation rules")
    errors: list[str] = Field(default_factory=list, description="List of rule violations that caused failure")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal warnings or soft constraint notices")


class Itinerary(BaseModel):
    """Complete, validated, structured travel itinerary."""

    request: TripRequest = Field(..., description="Original user trip request")
    hotel: Hotel = Field(..., description="Selected accommodation near attractions centroid")
    days: list[DayPlan] = Field(..., min_length=1, description="Day-by-day plan")
    weather_forecast: list[DailyWeather] = Field(
        default_factory=list, description="Full forecast used during planning"
    )
    sources: list[str] = Field(
        default_factory=list, description="Citations and data sources for all included facts"
    )
    validation: Optional[ValidationResult] = Field(
        default=None, description="Deterministic validation outcome"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 creation timestamp",
    )
