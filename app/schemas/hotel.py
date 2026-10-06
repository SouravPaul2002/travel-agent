"""Schemas for accommodation and hotels."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Hotel(BaseModel):
    """Hotel or accommodation recommendation."""

    id: Optional[str] = Field(default=None, description="Unique hotel identifier from source provider")
    name: str = Field(..., min_length=1, description="Name of the hotel")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate")
    distance_km: float = Field(..., ge=0.0, description="Distance in km to the centroid of planned places")
    rating: Optional[float] = Field(default=None, ge=0.0, le=5.0, description="Rating between 0.0 and 5.0")
    source: str = Field(..., min_length=1, description="Origin source or data provider (e.g. 'osm', 'geoapify')")

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Hotel name cannot be empty")
        return cleaned
