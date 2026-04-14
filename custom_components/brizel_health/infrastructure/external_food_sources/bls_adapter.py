"""Bundeslebensmittelschluessel (BLS) adapter backed by a local open-data snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import gzip
import json
from pathlib import Path
import re
from typing import Any
import unicodedata

from ...domains.nutrition.errors import BrizelImportedFoodValidationError
from ...domains.nutrition.models.external_food_search_result import (
    ExternalFoodSearchResult,
)
from ...domains.nutrition.models.imported_food_data import ImportedFoodData

SOURCE_NAME = "bls"
_DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "bls_foods.v1.json.gz"
)
_GERMAN_ORTHOGRAPHY_REPLACEMENTS = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "ß": "ss",
}
_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class _BlsFoodRecord:
    """Compact runtime representation of one BLS food."""

    source_id: str
    name: str
    name_en: str | None
    kcal_per_100g: float | None
    protein_per_100g: float | None
    carbs_per_100g: float | None
    fat_per_100g: float | None
    hydration_ml_per_100g: float | None
    normalized_name: str
    normalized_name_en: str
    name_tokens: tuple[str, ...]
    name_en_tokens: tuple[str, ...]


def _normalize_optional_text(value: Any) -> str | None:
    """Normalize one optional text field conservatively."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_search_text_for_matching(value: str) -> str:
    """Return an ASCII-friendly comparison form for local BLS search."""
    normalized = value.strip().casefold()
    for original, replacement in _GERMAN_ORTHOGRAPHY_REPLACEMENTS.items():
        normalized = normalized.replace(original, replacement)
    decomposed = unicodedata.normalize("NFKD", normalized)
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )


def _tokenize_search_text(value: str) -> tuple[str, ...]:
    """Split text into conservative normalized tokens."""
    normalized = _normalize_search_text_for_matching(value)
    return tuple(token for token in _TOKEN_SPLIT_RE.split(normalized) if token)


def _parse_optional_float(value: Any) -> float | None:
    """Parse one optional numeric field conservatively."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_snapshot_records(snapshot_path: Path) -> tuple[dict[str, Any], list[_BlsFoodRecord]]:
    """Load compact BLS metadata and records from the gzip snapshot."""
    if not snapshot_path.exists():
        raise FileNotFoundError(f"BLS snapshot not found at '{snapshot_path}'.")

    with gzip.open(snapshot_path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)

    metadata = payload.get("metadata", {})
    raw_foods = payload.get("foods", [])
    if not isinstance(raw_foods, list):
        raise BrizelImportedFoodValidationError("BLS snapshot foods payload is invalid.")

    records: list[_BlsFoodRecord] = []
    for item in raw_foods:
        if not isinstance(item, dict):
            continue
        source_id = _normalize_optional_text(item.get("source_id"))
        name = _normalize_optional_text(item.get("name"))
        if source_id is None or name is None:
            continue

        name_en = _normalize_optional_text(item.get("name_en"))
        records.append(
            _BlsFoodRecord(
                source_id=source_id,
                name=name,
                name_en=name_en,
                kcal_per_100g=_parse_optional_float(item.get("kcal_per_100g")),
                protein_per_100g=_parse_optional_float(item.get("protein_per_100g")),
                carbs_per_100g=_parse_optional_float(item.get("carbs_per_100g")),
                fat_per_100g=_parse_optional_float(item.get("fat_per_100g")),
                hydration_ml_per_100g=_parse_optional_float(
                    item.get("hydration_ml_per_100g")
                ),
                normalized_name=_normalize_search_text_for_matching(name),
                normalized_name_en=_normalize_search_text_for_matching(name_en or ""),
                name_tokens=_tokenize_search_text(name),
                name_en_tokens=_tokenize_search_text(name_en or ""),
            )
        )

    return metadata, records


class BlsAdapter:
    """Local BLS adapter for generic food search and import."""

    source_name = SOURCE_NAME
    supports_barcode_lookup = False

    def __init__(
        self,
        *,
        snapshot_path: Path | None = None,
        records: list[dict[str, Any]] | None = None,
        fetched_at: str | None = None,
        source_updated_at: str | None = None,
    ) -> None:
        """Initialize the BLS adapter from either injected fixtures or the snapshot."""
        self._snapshot_path = snapshot_path or _DEFAULT_SNAPSHOT_PATH
        self._fixture_records = records
        self._fetched_at = fetched_at or datetime.now(UTC).isoformat()
        self._source_updated_at = source_updated_at
        self._metadata: dict[str, Any] | None = None
        self._records_by_id: dict[str, _BlsFoodRecord] | None = None
        self._records: list[_BlsFoodRecord] | None = None

    def _ensure_loaded(self) -> None:
        """Load the BLS snapshot lazily once."""
        if self._records is not None and self._records_by_id is not None:
            return

        if self._fixture_records is not None:
            metadata: dict[str, Any] = {}
            records: list[_BlsFoodRecord] = []
            for item in self._fixture_records:
                source_id = _normalize_optional_text(item.get("source_id"))
                name = _normalize_optional_text(item.get("name"))
                if source_id is None or name is None:
                    continue
                name_en = _normalize_optional_text(item.get("name_en"))
                records.append(
                    _BlsFoodRecord(
                        source_id=source_id,
                        name=name,
                        name_en=name_en,
                        kcal_per_100g=_parse_optional_float(item.get("kcal_per_100g")),
                        protein_per_100g=_parse_optional_float(
                            item.get("protein_per_100g")
                        ),
                        carbs_per_100g=_parse_optional_float(item.get("carbs_per_100g")),
                        fat_per_100g=_parse_optional_float(item.get("fat_per_100g")),
                        hydration_ml_per_100g=_parse_optional_float(
                            item.get("hydration_ml_per_100g")
                        ),
                        normalized_name=_normalize_search_text_for_matching(name),
                        normalized_name_en=_normalize_search_text_for_matching(
                            name_en or ""
                        ),
                        name_tokens=_tokenize_search_text(name),
                        name_en_tokens=_tokenize_search_text(name_en or ""),
                    )
                )
        else:
            metadata, records = _load_snapshot_records(self._snapshot_path)

        self._metadata = metadata
        self._records = records
        self._records_by_id = {record.source_id: record for record in records}

    def _resolve_source_updated_at(self) -> str | None:
        """Return one conservative BLS source-updated timestamp."""
        if self._source_updated_at is not None:
            return self._source_updated_at

        if self._metadata is None:
            return None

        raw_value = _normalize_optional_text(self._metadata.get("source_updated_at"))
        return raw_value

    def _score_record(self, record: _BlsFoodRecord, query: str) -> int:
        """Score one BLS record for local top-N filtering."""
        normalized_query = _normalize_search_text_for_matching(query)
        query_tokens = set(_tokenize_search_text(query))
        if not normalized_query and not query_tokens:
            return 0

        score = 0

        if record.normalized_name == normalized_query:
            score += 1200
        elif record.normalized_name.startswith(normalized_query):
            score += 680
        elif normalized_query and normalized_query in record.normalized_name:
            score += 280

        if record.normalized_name_en:
            if record.normalized_name_en == normalized_query:
                score += 760
            elif record.normalized_name_en.startswith(normalized_query):
                score += 360
            elif normalized_query and normalized_query in record.normalized_name_en:
                score += 150

        name_token_set = set(record.name_tokens)
        name_en_token_set = set(record.name_en_tokens)
        if query_tokens:
            matched_de = sum(token in name_token_set for token in query_tokens)
            matched_en = sum(token in name_en_token_set for token in query_tokens)
            score += matched_de * 85
            score += matched_en * 55
            if query_tokens <= name_token_set:
                score += 260
            elif query_tokens <= name_en_token_set:
                score += 150

        if all(
            value is not None
            for value in (
                record.kcal_per_100g,
                record.protein_per_100g,
                record.carbs_per_100g,
                record.fat_per_100g,
            )
        ):
            score += 25

        return score

    def _record_to_search_result(self, record: _BlsFoodRecord) -> ExternalFoodSearchResult:
        """Map one BLS record into a source-neutral search result."""
        return ExternalFoodSearchResult.create(
            source_name=self.source_name,
            source_id=record.source_id,
            name=record.name,
            brand=None,
            barcode=None,
            kcal_per_100g=record.kcal_per_100g,
            protein_per_100g=record.protein_per_100g,
            carbs_per_100g=record.carbs_per_100g,
            fat_per_100g=record.fat_per_100g,
            hydration_ml_per_100g=record.hydration_ml_per_100g,
            market_country_codes=["de"],
            market_region_codes=["eu"],
        )

    def _record_to_imported_food(self, record: _BlsFoodRecord) -> ImportedFoodData:
        """Map one BLS record into an importable food payload."""
        return ImportedFoodData.create(
            source_name=self.source_name,
            source_id=record.source_id,
            name=record.name,
            brand=None,
            barcode=None,
            kcal_per_100g=record.kcal_per_100g,
            protein_per_100g=record.protein_per_100g,
            carbs_per_100g=record.carbs_per_100g,
            fat_per_100g=record.fat_per_100g,
            ingredients=None,
            ingredients_known=False,
            allergens=None,
            allergens_known=False,
            labels=None,
            labels_known=False,
            hydration_kind=None,
            hydration_ml_per_100g=record.hydration_ml_per_100g,
            market_country_codes=["de"],
            market_region_codes=["eu"],
            fetched_at=self._fetched_at,
            source_updated_at=self._resolve_source_updated_at(),
        )

    async def fetch_food_by_id(self, source_id: str) -> ImportedFoodData | None:
        """Return one BLS food by source ID."""
        normalized_source_id = str(source_id).strip()
        if not normalized_source_id:
            raise BrizelImportedFoodValidationError("A source_id is required.")

        self._ensure_loaded()
        assert self._records_by_id is not None
        record = self._records_by_id.get(normalized_source_id)
        if record is None:
            return None
        return self._record_to_imported_food(record)

    async def search_foods(
        self,
        query: str,
        limit: int = 10,
    ) -> list[ExternalFoodSearchResult]:
        """Search the local BLS dataset for generically matching foods."""
        normalized_query = str(query).strip()
        if not normalized_query or limit <= 0:
            return []

        self._ensure_loaded()
        assert self._records is not None

        ranked: list[tuple[int, str, str, _BlsFoodRecord]] = []
        for record in self._records:
            score = self._score_record(record, normalized_query)
            if score <= 0:
                continue
            ranked.append(
                (
                    score,
                    record.name.casefold(),
                    (record.name_en or "").casefold(),
                    record,
                )
            )

        ranked.sort(key=lambda item: (-item[0], item[1], item[2], item[3].source_id))
        return [self._record_to_search_result(item[3]) for item in ranked[:limit]]
