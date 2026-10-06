import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from ss_contracts.core import Scope
from ss_context_store.core import snapshot
from ss_llm_client.core import FixtureClient
from ss_session_source.core import SourceJournal, produce, flush, CollectingPublisher
from ss_archive_sink.core import Archive
from ss_platform_sink.core import Delivery, RecordingSender
from ss_speech_sink.core import SpeechQueue, RecordingPlayer
from ss_surface_sink.core import Projection

async def run_scenario(data, directory):
    directory = Path(directory)
    scope = Scope(**data["scope"])
    journal = SourceJournal(directory / "source.db")
    archive = Archive(directory / "context.db", scope)
    delivery = Delivery(directory / "delivery.db", scope)
    speech = SpeechQueue(directory / "speech.db", scope)
    surface = Projection(directory / "surface.db", scope)
    client = FixtureClient(data.get("response", "合成回答"))
    collector = CollectingPublisher()
    reader = lambda scoped, now, user: snapshot(archive.path, scoped, now, user_id=user)
    await produce(data["inputs"], scope, journal, client, context_reader=reader)
    published = await flush(journal, collector)
    sender, player = RecordingSender(), RecordingPlayer()
    inserted, shown = 0, 0
    for event in collector.events:
        value = event.as_dict()
        inserted += archive.handle(value)["inserted"]
        shown += surface.handle(value)
        if event.kind == "answer.completed":
            delivery.handle(value, sender)
            speech.enqueue(value, data["playback_now"])
    speech.drain(player, data["playback_now"])
    # Deliberately replay deliveries at every sink, with independent checkpoints.
    for event in collector.events:
        value = event.as_dict()
        assert not archive.handle(value)["inserted"]
        assert not surface.handle(value)
        if event.kind == "answer.completed":
            assert delivery.handle(value, sender)["newly_sent"] == 0
            assert speech.enqueue(value, data["playback_now"]) == "duplicate"
    assert speech.drain(player, data["playback_now"]) == 0
    html_path = directory / "surface.html"
    html_path.write_text(surface.render(), encoding="utf-8")
    return {"ok": True, "published": published, "archived": inserted, "surface_inserted": shown, "model_calls": client.calls, "delivered_parts": len(sender.sent), "played": len(player.played), "context_events": len(snapshot(archive.path, scope, 2000, user_id="fixture:user-1").events), "events": [e.as_dict() for e in collector.events]}

def demo(data):
    with TemporaryDirectory() as temp:
        return asyncio.run(run_scenario(data, temp))
