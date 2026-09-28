import json

import pytest

from src.rag.system_capabilities import (
    SystemCapabilitiesProvider,
)


@pytest.fixture
def capabilities_path(
    tmp_path,
):

    data = [
        {
            "capability": "live_data_access",
            "available": False,
            "content": ("ResolveAI has no live data access."),
        },
        {
            "capability": "human_support_routing",
            "available": False,
            "content": ("ResolveAI cannot transfer customers."),
        },
    ]

    path = tmp_path / "system_capabilities.json"

    path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    return path


def test_capabilities_are_loaded(
    capabilities_path,
):

    provider = SystemCapabilitiesProvider(capabilities_path)

    result = provider.build()

    assert result.capability_count == 2

    assert "live_data_access" in result.capabilities

    assert "human_support_routing" in result.capabilities


def test_context_is_generated(
    capabilities_path,
):

    provider = SystemCapabilitiesProvider(capabilities_path)

    result = provider.build()

    assert "System capability 1" in result.context

    assert "Status: unavailable" in result.context

    assert "ResolveAI has no live data access." in result.context


def test_missing_file_raises_error(
    tmp_path,
):

    path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError):
        SystemCapabilitiesProvider(path)


def test_empty_list_raises_error(
    tmp_path,
):

    path = tmp_path / "system_capabilities.json"

    path.write_text(
        "[]",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        SystemCapabilitiesProvider(path)


def test_invalid_available_value_raises_error(
    tmp_path,
):

    data = [
        {
            "capability": "live_data_access",
            "available": "no",
            "content": "No live access.",
        }
    ]

    path = tmp_path / "system_capabilities.json"

    path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        SystemCapabilitiesProvider(path)


def test_duplicate_capability_raises_error(
    tmp_path,
):

    data = [
        {
            "capability": "live_data_access",
            "available": False,
            "content": "No live access.",
        },
        {
            "capability": "live_data_access",
            "available": False,
            "content": "Still unavailable.",
        },
    ]

    path = tmp_path / "system_capabilities.json"

    path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        SystemCapabilitiesProvider(path)
