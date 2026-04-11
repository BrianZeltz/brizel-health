"""Nutrition domain errors."""

from __future__ import annotations


class BrizelNutritionError(Exception):
    """Base exception for nutrition domain errors."""


class BrizelFoodValidationError(BrizelNutritionError):
    """Raised when food data is invalid."""


class BrizelFoodAlreadyExistsError(BrizelNutritionError):
    """Raised when a food already exists."""


class BrizelFoodNotFoundError(BrizelNutritionError):
    """Raised when a food could not be found."""


class BrizelImportedFoodValidationError(BrizelNutritionError):
    """Raised when imported food data is invalid or incomplete."""


class BrizelImportedFoodNotFoundError(BrizelNutritionError):
    """Raised when an imported food could not be fetched from a source."""


class BrizelImportedFoodSourceError(BrizelNutritionError):
    """Raised when an external food source is unavailable or returns an error."""


class BrizelFoodEntryError(BrizelNutritionError):
    """Base exception for food entry errors."""


class BrizelFoodEntryValidationError(BrizelFoodEntryError):
    """Raised when food entry data is invalid."""


class BrizelFoodEntryNotFoundError(BrizelFoodEntryError):
    """Raised when a food entry could not be found."""
