"""Build a compact BLS snapshot for the Brizel Health integration.

This script reads the official BLS 4.0 XLSX export and writes a compact
gzip-compressed JSON payload that only contains the fields Brizel Health
currently needs for search, import and ranking.
"""

from __future__ import annotations

from argparse import ArgumentParser
from collections.abc import Iterable
from dataclasses import dataclass
import gzip
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

_SPREADSHEET_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

_COLUMN_SOURCE_ID = "A"
_COLUMN_NAME_DE = "B"
_COLUMN_NAME_EN = "C"
_COLUMN_KCAL = "G"
_COLUMN_WATER = "J"
_COLUMN_PROTEIN = "M"
_COLUMN_FAT = "P"
_COLUMN_CARBS = "S"

_BLS_METADATA = {
    "source_name": "bls",
    "display_name": "Bundeslebensmittelschluessel (BLS)",
    "version": "4.0",
    "release_year": 2025,
    "license": "CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "official_download_page": "https://blsdb.de/download",
    "citation": (
        "Max Rubner-Institut (2025): Bundeslebensmittelschluessel (BLS), "
        "Version 4.0 - Deutsche Naehrstoffdatenbank. Karlsruhe. "
        "DOI: 10.25826/Data20251217-134202-0"
    ),
}


@dataclass(frozen=True, slots=True)
class _BlsFoodRow:
    """Compact in-memory BLS row used for snapshot output."""

    source_id: str
    name: str
    name_en: str | None
    kcal_per_100g: float | None
    protein_per_100g: float | None
    carbs_per_100g: float | None
    fat_per_100g: float | None
    hydration_ml_per_100g: float | None

    def to_dict(self) -> dict[str, object]:
        """Serialize one compact BLS row."""
        return {
            "source_id": self.source_id,
            "name": self.name,
            "name_en": self.name_en,
            "kcal_per_100g": self.kcal_per_100g,
            "protein_per_100g": self.protein_per_100g,
            "carbs_per_100g": self.carbs_per_100g,
            "fat_per_100g": self.fat_per_100g,
            "hydration_ml_per_100g": self.hydration_ml_per_100g,
        }


def _normalize_optional_text(value: str | None) -> str | None:
    """Normalize one optional text value conservatively."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _parse_optional_float(value: str | None) -> float | None:
    """Parse one numeric spreadsheet cell conservatively."""
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None

    lowered = normalized.casefold()
    if lowered in {"-", "na", "n/a"}:
        return None
    if lowered.startswith("<"):
        return None

    try:
        return float(normalized.replace(",", "."))
    except ValueError:
        return None


def _read_shared_strings(workbook_path: Path) -> list[str]:
    """Read XLSX shared strings."""
    with zipfile.ZipFile(workbook_path) as archive:
        with archive.open("xl/sharedStrings.xml") as handle:
            root = ET.parse(handle).getroot()

    strings: list[str] = []
    for item in root.findall("main:si", _SPREADSHEET_NS):
        texts = [node.text or "" for node in item.iterfind(".//main:t", _SPREADSHEET_NS)]
        strings.append("".join(texts))
    return strings


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str | None:
    """Read one XLSX cell value as text."""
    value_node = cell.find("main:v", _SPREADSHEET_NS)
    if value_node is None or value_node.text is None:
        return None

    raw_value = value_node.text
    if cell.attrib.get("t") == "s":
        return shared_strings[int(raw_value)]
    return raw_value


def _iter_sheet_rows(workbook_path: Path) -> Iterable[dict[str, str]]:
    """Yield sheet rows as sparse column->value mappings."""
    shared_strings = _read_shared_strings(workbook_path)
    with zipfile.ZipFile(workbook_path) as archive:
        with archive.open("xl/worksheets/sheet1.xml") as handle:
            root = ET.parse(handle).getroot()

    for row in root.findall(".//main:sheetData/main:row", _SPREADSHEET_NS):
        mapped_row: dict[str, str] = {}
        for cell in row.findall("main:c", _SPREADSHEET_NS):
            reference = cell.attrib.get("r", "")
            column = "".join(character for character in reference if character.isalpha())
            if not column:
                continue

            value = _cell_value(cell, shared_strings)
            if value is None:
                continue
            mapped_row[column] = value
        if mapped_row:
            yield mapped_row


def _build_food_row(row: dict[str, str]) -> _BlsFoodRow | None:
    """Convert one sparse worksheet row into one compact food entry."""
    source_id = _normalize_optional_text(row.get(_COLUMN_SOURCE_ID))
    name = _normalize_optional_text(row.get(_COLUMN_NAME_DE))
    if source_id is None or name is None:
        return None

    return _BlsFoodRow(
        source_id=source_id,
        name=name,
        name_en=_normalize_optional_text(row.get(_COLUMN_NAME_EN)),
        kcal_per_100g=_parse_optional_float(row.get(_COLUMN_KCAL)),
        protein_per_100g=_parse_optional_float(row.get(_COLUMN_PROTEIN)),
        carbs_per_100g=_parse_optional_float(row.get(_COLUMN_CARBS)),
        fat_per_100g=_parse_optional_float(row.get(_COLUMN_FAT)),
        hydration_ml_per_100g=_parse_optional_float(row.get(_COLUMN_WATER)),
    )


def build_bls_snapshot(workbook_path: Path, output_path: Path) -> dict[str, object]:
    """Build the compact BLS snapshot payload and write it as gzip JSON."""
    foods: list[dict[str, object]] = []
    for index, row in enumerate(_iter_sheet_rows(workbook_path)):
        if index == 0:
            continue

        food_row = _build_food_row(row)
        if food_row is None:
            continue
        foods.append(food_row.to_dict())

    payload = {
        "metadata": _BLS_METADATA,
        "foods": foods,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output_path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))

    return {
        "foods": len(foods),
        "output_path": str(output_path),
        "output_size_bytes": output_path.stat().st_size,
    }


def _build_argument_parser() -> ArgumentParser:
    """Return the CLI argument parser."""
    parser = ArgumentParser(description="Build a compact BLS snapshot for Brizel Health.")
    parser.add_argument(
        "workbook",
        type=Path,
        help="Path to BLS_4_0_Daten_2025_DE.xlsx",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Path to the output gzip JSON snapshot file.",
    )
    return parser


def main() -> int:
    """Run the snapshot builder as a CLI."""
    parser = _build_argument_parser()
    args = parser.parse_args()
    result = build_bls_snapshot(args.workbook, args.output)
    print(
        json.dumps(
            result,
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
