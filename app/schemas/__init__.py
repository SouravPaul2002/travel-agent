"""Schemas package providing all Pydantic models and state definitions."""

from app.schemas.hotel import Hotel
from app.schemas.itinerary import DayPlan, Itinerary, ValidationResult
from app.schemas.places import Place
from app.schemas.state import TravelState, TravelStateModel
from app.schemas.trip import BudgetLevel, GeocodedLocation, TripRequest
from app.schemas.weather import DailyWeather

__all__ = [
    "BudgetLevel",
    "DailyWeather",
    "DayPlan",
    "GeocodedLocation",
    "Hotel",
    "Itinerary",
    "Place",
    "TravelState",
    "TravelStateModel",
    "TripRequest",
    "ValidationResult",
]
