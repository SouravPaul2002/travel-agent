"""Schemas for weather forecasts."""

from typing import Optional
from pydantic import BaseModel, Field


class DailyWeather(BaseModel):
    """Daily weather forecast record."""

    date: str = Field(..., description="Forecast date (YYYY-MM-DD)")
    temp_min: Optional[float] = Field(default=None, description="Minimum temperature in Celsius")
    temp_max: Optional[float] = Field(default=None, description="Maximum temperature in Celsius")
    precipitation_prob: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Precipitation probability percentage (0-100)"
    )
    summary: Optional[str] = Field(default=None, description="Weather condition summary (e.g. 'Sunny', 'Rainy')")
    source: str = Field(default="open-meteo", description="Weather data source provider")

