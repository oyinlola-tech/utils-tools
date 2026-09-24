"""Tests for the capability registry."""

from app.core.capabilities import (
    VERCEL_DRIVER,
    capability_registry,
)


def test_registry_contains_all_52_tools():
    assert len(capability_registry.tools) == 52


def test_all_tools_have_unique_ids():
    ids = [tool.id for tool in capability_registry.tools]
    assert len(ids) == len(set(ids))


def test_registry_covers_all_categories():
    categories = {
        tool.category for tool in capability_registry.tools
    }
    assert categories == {
        "image",
        "pdf",
        "file",
        "developer",
        "utility",
        "text",
    }


def test_available_tools_are_honest_in_local():
    available = [
        tool
        for tool in capability_registry.effective_tools()
        if tool["status"] == "available"
    ]
    available_ids = {tool["id"] for tool in available}
    # Every implemented tool is advertised locally.
    assert available_ids == {
        tool.id for tool in capability_registry.tools
    }


def test_pdf_compressor_is_advertised_on_vercel(monkeypatch):
    monkeypatch.setattr(capability_registry, "driver", VERCEL_DRIVER)
    tools = {
        tool["id"]: tool
        for tool in capability_registry.effective_tools()
    }
    # All tools, including PDF tools, are available on Vercel.
    assert tools["pdf-compressor"]["status"] == "available"
    assert tools["pdf-to-image"]["status"] == "available"
    assert tools["background-remover"]["status"] == "available"
    assert tools["image-compressor"]["status"] == "available"
    assert tools["qr-generator"]["status"] == "available"


def test_is_available_reflects_driver(monkeypatch):
    monkeypatch.setattr(capability_registry, "driver", "local")
    assert capability_registry.is_available("background-remover")
    assert capability_registry.is_available("qr-generator")

    monkeypatch.setattr(capability_registry, "driver", VERCEL_DRIVER)
    assert capability_registry.is_available("background-remover")
    assert capability_registry.is_available("pdf-compressor")
    assert capability_registry.is_available("qr-generator")


def test_get_returns_none_for_unknown_tool():
    assert capability_registry.get("does-not-exist") is None


def test_tool_limits_are_positive():
    for tool in capability_registry.tools:
        assert tool.max_files >= 1
        if tool.max_upload_mb is not None:
            assert tool.max_upload_mb > 0


def test_planned_tools_never_claim_availability():
    for tool in capability_registry.tools:
        if tool.status == "planned":
            effective = {
                item["id"]: item
                for item in capability_registry.effective_tools()
            }[tool.id]
            assert effective["status"] == "planned"


def test_system_capabilities_never_include_tokens():
    system = capability_registry.system_capabilities()
    assert "token" not in system
    assert "BLOB" not in " ".join(system.keys())


CLIENT_ONLY_DEV_TOOLS = {
    "uuid-generator",
    "hash-generator",
    "base64-encoder",
    "url-encoder",
    "timestamp-converter",
    "regex-tester",
    "color-converter",
    "password-generator",
    "cron-parser",
    "html-entities",
    "number-base-converter",
    "lorem-ipsum",
}


def test_client_only_dev_tools_run_everywhere(monkeypatch):
    for tool_id in CLIENT_ONLY_DEV_TOOLS:
        tool = capability_registry.get(tool_id)
        assert tool is not None, tool_id
        assert tool.client_only, tool_id
        assert tool.requires_module is None, tool_id
        assert tool.requires_binary is None, tool_id
        assert set(tool.environments) == {"local", VERCEL_DRIVER}, tool_id

    monkeypatch.setattr(capability_registry, "driver", VERCEL_DRIVER)
    effective = {
        tool["id"]: tool for tool in capability_registry.effective_tools()
    }
    for tool_id in CLIENT_ONLY_DEV_TOOLS:
        assert effective[tool_id]["status"] == "available", tool_id


def test_client_only_dev_tools_ship_page_and_script():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "frontend"
    for tool_id in CLIENT_ONLY_DEV_TOOLS:
        assert (root / "pages" / f"{tool_id}.html").is_file(), tool_id
        assert (
            root / "assets" / "js" / "pages" / f"{tool_id}.js"
        ).is_file(), tool_id
