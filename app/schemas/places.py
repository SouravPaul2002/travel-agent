"""Schemas for places and points of interest (POIs)."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Place(BaseModel):
    """A point of interest or attraction."""

    id: Optional[str] = Field(default=None, description="Unique place identifier from source provider")
    name: str = Field(..., min_length=1, description="Name of the place or attraction")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate")
    category: str = Field(default="general", description="Category e.g. 'history', 'food', 'nature', 'monument'")
    rating: Optional[float] = Field(default=None, ge=0.0, le=5.0, description="Rating between 0.0 and 5.0")
    opening_hours: Optional[str] = Field(default=None, description="Opening hours string if available")
    is_outdoor: Optional[bool] = Field(default=True, description="Whether the attraction is primarily outdoors")
    source: str = Field(..., min_length=1, description="Origin source or data provider (e.g. 'geoapify', 'osm')")

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Place name cannot be empty")
        return cleaned
