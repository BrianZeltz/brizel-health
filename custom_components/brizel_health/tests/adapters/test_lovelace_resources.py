"""Tests for Brizel Health Lovelace resource registration."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from custom_components.brizel_health.adapters.homeassistant.lovelace_resources import (
    _async_sync_resource_collection,
    async_ensure_lovelace_resources,
)


class _FakeResourceCollection:
    """Minimal fake Lovelace resource collection for adapter tests."""

    def __init__(self, items: list[dict[str, object]]) -> None:
        self._items = items
        self.create_calls: list[dict[str, object]] = []
        self.update_calls: list[tuple[object, dict[str, object]]] = []
        self.get_info_calls = 0

    async def async_get_info(self) -> dict[str, object]:
        self.get_info_calls += 1
        return {"resources": self._items}

    def async_items(self) -> list[dict[str, object]]:
        return list(self._items)

    async def async_create_item(self, data: dict[str, object]) -> dict[str, object]:
        item_id = f"generated_{len(self._items) + 1}"
        item = {"id": item_id, "type": data["res_type"], "url": data["url"]}
        self._items.append(item)
        self.create_calls.append(data)
        return item

    async def async_update_item(
        self, item_id: object, data: dict[str, object]
    ) -> dict[str, object]:
        for item in self._items:
            if item.get("id") == item_id:
                item["type"] = data["res_type"]
                self.update_calls.append((item_id, data))
                return item
        raise AssertionError(f"Unknown item id: {item_id}")


@pytest.fixture
def stub_lovelace_const_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide the minimal Home Assistant Lovelace constants module."""
    homeassistant_module = sys.modules.setdefault("homeassistant", ModuleType("homeassistant"))
    components_module = sys.modules.setdefault(
        "homeassistant.components",
        ModuleType("homeassistant.components"),
    )
    lovelace_module = sys.modules.setdefault(
        "homeassistant.components.lovelace",
        ModuleType("homeassistant.components.lovelace"),
    )
    const_module = ModuleType("homeassistant.components.lovelace.const")
    const_module.LOVELACE_DATA = "lovelace"
    const_module.MODE_YAML = "yaml"

    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant_module)
    monkeypatch.setitem(sys.modules, "homeassistant.components", components_module)
    monkeypatch.setitem(sys.modules, "homeassistant.components.lovelace", lovelace_module)
    monkeypatch.setitem(
        sys.modules,
        "homeassistant.components.lovelace.const",
        const_module,
    )


@pytest.mark.asyncio
async def test_sync_resource_collection_creates_missing_resources() -> None:
    """Missing Brizel Health resources should be created."""
    collection = _FakeResourceCollection([])

    await _async_sync_resource_collection(
        collection,
        resource_urls=("/api/brizel_health/frontend/hero.js",),
    )

    assert collection.get_info_calls == 1
    assert collection.create_calls == [
        {
            "url": "/api/brizel_health/frontend/hero.js",
            "res_type": "module",
        }
    ]
    assert collection.update_calls == []


@pytest.mark.asyncio
async def test_sync_resource_collection_skips_existing_module_resources() -> None:
    """Existing module resources should not be duplicated."""
    collection = _FakeResourceCollection(
        [
            {
                "id": "existing_1",
                "type": "module",
                "url": "/api/brizel_health/frontend/hero.js",
            }
        ]
    )

    await _async_sync_resource_collection(
        collection,
        resource_urls=("/api/brizel_health/frontend/hero.js",),
    )

    assert collection.create_calls == []
    assert collection.update_calls == []


@pytest.mark.asyncio
async def test_sync_resource_collection_updates_wrong_resource_type() -> None:
    """Existing Brizel Health resources should be normalized to module."""
    collection = _FakeResourceCollection(
        [
            {
                "id": "existing_1",
                "type": "js",
                "url": "/api/brizel_health/frontend/hero.js",
            }
        ]
    )

    await _async_sync_resource_collection(
        collection,
        resource_urls=("/api/brizel_health/frontend/hero.js",),
    )

    assert collection.create_calls == []
    assert collection.update_calls == [
        ("existing_1", {"res_type": "module"})
    ]


@pytest.mark.asyncio
async def test_ensure_lovelace_resources_accepts_auto_gen_mode(
    stub_lovelace_const_module: None,
) -> None:
    """Auto-generated Lovelace dashboards should still get storage resources."""
    collection = _FakeResourceCollection([])
    hass = SimpleNamespace(
        data={
            "lovelace": SimpleNamespace(
                resource_mode="auto-gen",
                resources=collection,
            )
        }
    )

    result = await async_ensure_lovelace_resources(hass)

    assert result is True
    assert collection.create_calls


@pytest.mark.asyncio
async def test_ensure_lovelace_resources_retries_when_resources_not_ready(
    stub_lovelace_const_module: None,
) -> None:
    """Non-YAML dashboards should retry if the resource collection is not ready."""
    hass = SimpleNamespace(
        data={
            "lovelace": SimpleNamespace(
                resource_mode="storage",
                resources=None,
            )
        }
    )

    result = await async_ensure_lovelace_resources(hass)

    assert result is False
