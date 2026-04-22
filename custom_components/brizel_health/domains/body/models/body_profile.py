"""Per-profile body data owned by the Body module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from ..errors import BrizelBodyProfileValidationError

SEX_FEMALE = "female"
SEX_MALE = "male"
ALLOWED_SEXES = {
    SEX_FEMALE,
    SEX_MALE,
}

ACTIVITY_LEVEL_SEDENTARY = "sedentary"
ACTIVITY_LEVEL_LIGHT = "light"
ACTIVITY_LEVEL_MODERATE = "moderate"
ACTIVITY_LEVEL_ACTIVE = "active"
ACTIVITY_LEVEL_VERY_ACTIVE = "very_active"
ALLOWED_ACTIVITY_LEVELS = {
    ACTIVITY_LEVEL_SEDENTARY,
    ACTIVITY_LEVEL_LIGHT,
    ACTIVITY_LEVEL_MODERATE,
    ACTIVITY_LEVEL_ACTIVE,
    ACTIVITY_LEVEL_VERY_ACTIVE,
}


def validate_profile_id(profile_id: str) -> str:
    """Validate and normalize a profile ID."""
    normalized_value = str(profile_id).strip()
    if not normalized_value:
        raise BrizelBodyProfileValidationError("A profile ID is required.")
    return normalized_value


def validate_age_years(age_years: int | None) -> int | None:
    """Validate the optional age value."""
    if age_years is None:
        return None

    normalized_value = int(age_years)
    if normalized_value < 1 or normalized_value > 120:
        raise BrizelBodyProfileValidationError(
            "age_years must be between 1 and 120."
        )

    return normalized_value


def validate_birth_date(birth_date: str | None) -> str | None:
    """Validate and normalize the optional birth date value."""
    if birth_date is None:
        return None

    normalized_value = str(birth_date).strip()
    if not normalized_value:
        return None

    try:
        if "T" in normalized_value or " " in normalized_value:
            parsed = datetime.fromisoformat(
                normalized_value.replace("Z", "+00:00")
            ).date()
        else:
            parsed = date.fromisoformat(normalized_value)
    except ValueError as err:
        raise BrizelBodyProfileValidationError(
            "birth_date must be a valid ISO date string."
        ) from err

    if parsed > date.today():
        raise BrizelBodyProfileValidationError("birth_date must not be in the future.")

    return parsed.isoformat()


def validate_height_cm(height_cm: float | int | None) -> float | None:
    """Validate the optional height value."""
    if height_cm is None:
        return None

    normalized_value = float(height_cm)
    if normalized_value < 50 or normalized_value > 250:
        raise BrizelBodyProfileValidationError(
            "height_cm must be between 50 and 250."
        )

    return normalized_value


def validate_weight_kg(weight_kg: float | int | None) -> float | None:
    """Validate the optional weight value."""
    if weight_kg is None:
        return None

    normalized_value = float(weight_kg)
    if normalized_value < 10 or normalized_value > 300:
        raise BrizelBodyProfileValidationError(
            "weight_kg must be between 10 and 300."
        )

    return normalized_value


def validate_sex(sex: str | None) -> str | None:
    """Validate and normalize the optional sex value."""
    if sex is None:
        return None

    normalized_value = str(sex).strip().lower()
    if not normalized_value:
        return None

    if normalized_value not in ALLOWED_SEXES:
        raise BrizelBodyProfileValidationError(
            f"sex must be one of {sorted(ALLOWED_SEXES)}."
        )

    return normalized_value


def validate_activity_level(activity_level: str | None) -> str | None:
    """Validate and normalize the optional activity level."""
    if activity_level is None:
        return None

    normalized_value = str(activity_level).strip().lower()
    if not normalized_value:
        return None

    if normalized_value not in ALLOWED_ACTIVITY_LEVELS:
        raise BrizelBodyProfileValidationError(
            f"activity_level must be one of {sorted(ALLOWED_ACTIVITY_LEVELS)}."
        )

    return normalized_value


@dataclass(slots=True)
class BodyProfile:
    """Body-owned per-profile data used for target calculations."""

    profile_id: str
    birth_date: str | None = None
    age_years: int | None = None
    sex: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    activity_level: str | None = None

    @classmethod
    def create(
        cls,
        profile_id: str,
        age_years: int | None = None,
        sex: str | None = None,
        height_cm: float | int | None = None,
        weight_kg: float | int | None = None,
        activity_level: str | None = None,
        birth_date: str | None = None,
        date_of_birth: str | None = None,
    ) -> "BodyProfile":
        """Create a validated body profile."""
        normalized_birth_date = validate_birth_date(birth_date or date_of_birth)
        return cls(
            profile_id=validate_profile_id(profile_id),
            birth_date=normalized_birth_date,
            age_years=validate_age_years(age_years),
            sex=validate_sex(sex),
            height_cm=validate_height_cm(height_cm),
            weight_kg=validate_weight_kg(weight_kg),
            activity_level=validate_activity_level(activity_level),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BodyProfile":
        """Load a body profile from persisted data."""
        return cls.create(
            profile_id=str(data.get("profile_id", "")),
            birth_date=data.get("birth_date"),
            date_of_birth=data.get("date_of_birth"),
            age_years=data.get("age_years"),
            sex=data.get("sex"),
            height_cm=data.get("height_cm"),
            weight_kg=data.get("weight_kg"),
            activity_level=data.get("activity_level"),
        )

    def update(
        self,
        age_years: int | None = None,
        sex: str | None = None,
        height_cm: float | int | None = None,
        weight_kg: float | int | None = None,
        activity_level: str | None = None,
        birth_date: str | None = None,
        date_of_birth: str | None = None,
    ) -> None:
        """Replace the mutable body data with a validated new state."""
        if birth_date is not None or date_of_birth is not None:
            raw_birth_date = birth_date
            if raw_birth_date is None or not str(raw_birth_date).strip():
                raw_birth_date = date_of_birth
            if raw_birth_date is not None and str(raw_birth_date).strip():
                self.birth_date = validate_birth_date(raw_birth_date)
        self.age_years = validate_age_years(age_years)
        self.sex = validate_sex(sex)
        self.height_cm = validate_height_cm(height_cm)
        self.weight_kg = validate_weight_kg(weight_kg)
        self.activity_level = validate_activity_level(activity_level)

    def is_empty(self) -> bool:
        """Return whether no body data has been captured yet."""
        return (
            self.birth_date is None
            and self.age_years is None
            and self.sex is None
            and self.height_cm is None
            and self.weight_kg is None
            and self.activity_level is None
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the body profile for persistence."""
        return {
            "profile_id": self.profile_id,
            "birth_date": self.birth_date,
            "date_of_birth": self.birth_date,
            "age_years": self.age_years,
            "sex": self.sex,
            "height_cm": self.height_cm,
            "weight_kg": self.weight_kg,
            "activity_level": self.activity_level,
        }
