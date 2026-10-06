"""Schemas for weather forecasts."""

from pydantic import BaseModel, Field


class DailyWeather(BaseModel):
    """Daily weather forecast record."""

    date: str = Field(..., description="Forecast date (YYYY-MM-DD)")
    temp_min: float = Field(..., description="Minimum temperature in Celsius")
    temp_max: float = Field(..., description="Maximum temperature in Celsius")
    precipitation_prob: float = Field(
        ..., ge=0.0, le=100.0, description="Precipitation probability percentage (0-100)"
    )
    summary: str = Field(..., min_length=1, description="Weather condition summary (e.g. 'Sunny', 'Rainy')")
    source: str = Field(default="open-meteo", description="Weather data source provider")
