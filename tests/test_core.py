import asyncio
import importlib
import pytest
from ss_assembly.core import run_scenario

def test_composed_repos_and_replay(tmp_path, sample):
    result = asyncio.run(run_scenario(sample, tmp_path))
    assert result["published"] == result["archived"] == result["surface_inserted"] == result["context_events"] == 4
    assert result["model_calls"] == result["delivered_parts"] == result["played"] == 1
    assert (tmp_path / "surface.html").exists()
    assert all(set(e["payload"]).isdisjoint({"prompt", "diagnostics", "context"}) for e in result["events"])

def test_input_scope_failure_stops_pipeline(tmp_path, sample):
    sample["inputs"][0]["scope"] = {**sample["scope"], "profile_id": "other"}
    with pytest.raises(ValueError, match="scope"):
        asyncio.run(run_scenario(sample, tmp_path))

def test_publish_and_consume_capabilities_are_separate():
    from ss_session_source.transport import RabbitPublisher
    assert not hasattr(RabbitPublisher, "consume")
    assert not hasattr(RabbitPublisher, "subscribe")
    for package in ("ss_archive_sink", "ss_platform_sink", "ss_speech_sink", "ss_surface_sink"):
        transport = importlib.import_module(package + ".transport")
        assert hasattr(transport, "consume")
        assert not hasattr(transport, "publish")

def test_real_model_and_external_services_are_not_needed(tmp_path, sample):
    result = asyncio.run(run_scenario(sample, tmp_path))
    assert result["ok"] is True
