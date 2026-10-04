"""Passive parameters for the weather/solar native review cases."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WeatherSolarCase(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['weather-solar']
    program: Literal['ice_storm', 'sleet_storm', 'sunbeam', 'sunburst']
    empty: bool = False
    expire: bool = False
    repeat: bool = False
    heading: int = Field(default=0, ge=0, le=7)
