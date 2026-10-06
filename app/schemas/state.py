"""Graph state schemas for LangGraph multi-agent orchestration."""

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

from app.schemas.hotel import Hotel
from app.schemas.itinerary import Itinerary, ValidationResult
from app.schemas.places import Place
from app.schemas.trip import TripRequest
from app.schemas.weather import DailyWeather

try:
    from langgraph.graph.message import add_messages
except ImportError:
    # Fallback reducer if langgraph is not yet imported
    def add_messages(left: list[Any], right: list[Any]) -> list[Any]:
        return list(left) + list(right)


class TravelState(TypedDict, total=False):
    """LangGraph execution state passed across graph nodes."""

    # Chat / reasoning message stream
    messages: Annotated[list[Any], add_messages]

    # Parsed request & intermediate tool outputs
    trip_request: Optional[TripRequest]
    places: list[Place]
    weather: list[DailyWeather]
    hotel: Optional[Hotel]

    # Assembled itinerary & validation loop tracking
    itinerary: Optional[Itinerary]
    validation_result: Optional[ValidationResult]
    retry_count: int
    errors: list[str]
    sources: list[str]


class TravelStateModel(BaseModel):
    """Pydantic model equivalent of TravelState for serialization and validation."""

    trip_request: Optional[TripRequest] = None
    places: list[Place] = Field(default_factory=list)
    weather: list[DailyWeather] = Field(default_factory=list)
    hotel: Optional[Hotel] = None
    itinerary: Optional[Itinerary] = None
    validation_result: Optional[ValidationResult] = None
    retry_count: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
