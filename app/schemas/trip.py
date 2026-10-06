"""Schemas for user trip requests."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class BudgetLevel(str, Enum):
    """Budget tier for trip planning."""
    BUDGET = "budget"
    MID = "mid"
    LUXURY = "luxury"


class GeocodedLocation(BaseModel):
    """Geocoded geographical destination with coordinates and administrative hierarchy."""

    name: str = Field(..., description="Matched locality or city name")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate")
    country: Optional[str] = Field(default=None, description="Country name e.g. 'India'")
    country_code: Optional[str] = Field(default=None, description="Country code e.g. 'IN'")
    admin1: Optional[str] = Field(default=None, description="Administrative subdivision, state, or province e.g. 'Rajasthan'")
    timezone: Optional[str] = Field(default=None, description="Local timezone identifier e.g. 'Asia/Kolkata'")

    @property
    def coords(self) -> tuple[float, float]:
        """Return (latitude, longitude) coordinate tuple."""
        return (self.lat, self.lon)



class TripRequest(BaseModel):
    """Parsed and validated user travel request."""

    city: str = Field(..., min_length=2, description="Target destination city name (e.g. 'Jaipur')")
    days: int = Field(..., ge=1, le=14, description="Trip duration in days (1 to 14)")
    budget: BudgetLevel = Field(default=BudgetLevel.MID, description="Budget tier: budget, mid, or luxury")
    interests: list[str] = Field(default_factory=list, description="Traveler interests e.g. ['history', 'food']")
    start_date: Optional[str] = Field(
        default=None,
        description="Trip start date in YYYY-MM-DD format if specified",
    )

    @field_validator("city")
    @classmethod
    def clean_city(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("City name cannot be empty or blank")
        return cleaned.title()

    @field_validator("interests")
    @classmethod
    def clean_interests(cls, v: list[str]) -> list[str]:
        return [i.strip().lower() for i in v if i.strip()]
