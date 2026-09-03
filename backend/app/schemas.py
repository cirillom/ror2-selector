from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class UserUpdate(UserCreate):
    pass


class UserRead(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime


class SurvivorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    image_url: HttpUrl | None = None
    dlc_name: str = Field(default="Base Game", min_length=1, max_length=80)

    @field_validator("name", "dlc_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class SurvivorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    image_url: HttpUrl | None = None
    dlc_name: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("name", "dlc_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @model_validator(mode="after")
    def require_a_field(self) -> "SurvivorUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class SurvivorRead(BaseModel):
    id: int
    name: str
    image_url: str
    dlc_name: str
    created_at: datetime
    updated_at: datetime


class EclipseLevelCreate(BaseModel):
    user_id: int = Field(gt=0)
    survivor_id: int = Field(gt=0)
    level: int = Field(default=1, ge=1, le=8)
    completed: bool = False

    @model_validator(mode="after")
    def completed_requires_level_eight(self) -> "EclipseLevelCreate":
        if self.completed and self.level != 8:
            raise ValueError("completed progress must be at level 8")
        return self


class EclipseLevelUpdate(BaseModel):
    level: int | None = Field(default=None, ge=1, le=8)
    completed: bool | None = None

    @model_validator(mode="after")
    def require_a_field(self) -> "EclipseLevelUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class PartyWinRequest(BaseModel):
    eclipse_level_ids: list[int] = Field(min_length=1, max_length=4)

    @field_validator("eclipse_level_ids")
    @classmethod
    def validate_eclipse_level_ids(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("eclipse level IDs must be positive")
        if len(values) != len(set(values)):
            raise ValueError("eclipse level IDs must be unique")
        return values


class EclipseLevelRead(BaseModel):
    id: int
    user_id: int
    survivor_id: int
    level: int
    completed: bool
    created_at: datetime
    updated_at: datetime


class ProgressEntry(BaseModel):
    eclipse_level_id: int
    survivor_id: int
    survivor_name: str
    image_url: str
    dlc_name: str
    level: int
    completed: bool


class UserProgress(BaseModel):
    user_id: int
    user_name: str
    levels: list[ProgressEntry]
