import asyncio
import os
import uuid
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("SS_MRE_TEST_AMQP_URL"), reason="explicit isolated RabbitMQ URL required")]

def test_real_broker_fanout_replay_and_manual_ack(tmp_path, sample):
    import aio_pika
    from ss_contracts.core import Scope
    from ss_llm_client.core import FixtureClient
    from ss_session_source.core import SourceJournal, produce
    from ss_session_source.transport import RabbitPublisher
    from ss_archive_sink.core import Archive
    from ss_archive_sink.transport import consume as archive_consume
    from ss_platform_sink.core import Delivery, RecordingSender
    from ss_platform_sink.transport import consume as platform_consume
    from ss_speech_sink.core import SpeechQueue, RecordingPlayer
    from ss_speech_sink.transport import consume as speech_consume
    from ss_surface_sink.core import Projection
    from ss_surface_sink.transport import consume as surface_consume

    async def run():
        url = os.environ["SS_MRE_TEST_AMQP_URL"]
        unique = "ss.mre.test." + uuid.uuid4().hex
        scope = Scope(**sample["scope"])
        journal = SourceJournal(tmp_path / "source.db")
        events = await produce(sample["inputs"], scope, journal, FixtureClient())
        archive = Archive(tmp_path / "context.db", scope)
        delivery, sender = Delivery(tmp_path / "delivery.db", scope), RecordingSender()
        speech, player = SpeechQueue(tmp_path / "speech.db", scope), RecordingPlayer()
        surface = Projection(tmp_path / "surface.db", scope)
        def handle_speech(value):
            speech.enqueue(value, sample["playback_now"])
            speech.drain(player, sample["playback_now"])
        specifications = [(archive_consume, archive.handle, 8), (platform_consume, lambda e: delivery.handle(e, sender), 2), (speech_consume, handle_speech, 2), (surface_consume, surface.handle, 8)]
        ready = [asyncio.Event() for _ in specifications]
        names = [unique + "." + str(i) for i in range(4)]
        tasks = [asyncio.create_task(consumer(url, names[i], scope, handler, unique, limit, 15, ready[i])) for i, (consumer, handler, limit) in enumerate(specifications)]
        try:
            await asyncio.wait_for(asyncio.gather(*(e.wait() for e in ready)), 15)
            async with RabbitPublisher(url, unique) as publisher:
                for _ in range(2):
                    for event in events:
                        await publisher.publish(event)
            outcomes = await asyncio.wait_for(asyncio.gather(*tasks), 20)
            assert all(result["rejected"] == 0 for result in outcomes)
            assert [result["handled"] for result in outcomes] == [8, 2, 2, 8]
            assert len(sender.sent) == len(player.played) == 1
            assert surface.render().count("<li>") == 4
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            connection = await aio_pika.connect(url)
            try:
                channel = await connection.channel()
                for name in names:
                    await channel.queue_delete(name, if_unused=False, if_empty=False)
                    await channel.queue_delete(name + ".dlq", if_unused=False, if_empty=False)
                await channel.exchange_delete(unique, if_unused=False)
                await channel.exchange_delete(unique + ".dlx", if_unused=False)
            finally:
                await connection.close()
    asyncio.run(run())

def test_unroutable_publish_keeps_outbox(tmp_path, sample):
    import aio_pika
    from ss_contracts.core import Scope
    from ss_llm_client.core import FixtureClient
    from ss_session_source.core import SourceJournal, produce, flush
    from ss_session_source.transport import RabbitPublisher
    async def run():
        url = os.environ["SS_MRE_TEST_AMQP_URL"]
        unique = "ss.mre.unroutable." + uuid.uuid4().hex
        journal = SourceJournal(tmp_path / "source.db")
        await produce(sample["inputs"], Scope(**sample["scope"]), journal, FixtureClient())
        try:
            async with RabbitPublisher(url, unique) as publisher:
                with pytest.raises(Exception):
                    await flush(journal, publisher)
            assert len(SourceJournal(journal.path).pending()) == 4
        finally:
            connection = await aio_pika.connect(url)
            try:
                channel = await connection.channel()
                await channel.exchange_delete(unique, if_unused=False)
            finally:
                await connection.close()
    asyncio.run(run())

def test_wrong_scope_is_dead_lettered_without_archive_effect(tmp_path, sample):
    import aio_pika
    from ss_contracts.core import Scope, make_event
    from ss_archive_sink.core import Archive
    from ss_archive_sink.transport import consume
    from ss_context_store.core import snapshot
    from ss_session_source.transport import RabbitPublisher

    async def run():
        url = os.environ["SS_MRE_TEST_AMQP_URL"]
        unique = "ss.mre.scope." + uuid.uuid4().hex
        queue_name = unique + ".archive"
        scope = Scope(**sample["scope"])
        archive = Archive(tmp_path / "context.db", scope)
        ready = asyncio.Event()
        task = asyncio.create_task(consume(url, queue_name, scope, archive.handle, unique, 1, 15, ready))
        connection = None
        try:
            await asyncio.wait_for(ready.wait(), 15)
            wrong = make_event("chat.observed", {"user_id": "fixture:user-1", "platform": "fixture", "text": "synthetic wrong-scope input"}, Scope("other-profile", scope.channel_id, scope.session_id), "wrong-1", 1000)
            async with RabbitPublisher(url, unique) as publisher:
                await publisher.publish(wrong)
            outcome = await asyncio.wait_for(task, 15)
            assert outcome == {"handled": 0, "rejected": 1}
            assert not snapshot(archive.path, scope, 2000).events
            connection = await aio_pika.connect(url)
            channel = await connection.channel()
            queue = await channel.declare_queue(queue_name + ".dlq", passive=True)
            async with queue.iterator(timeout=5) as iterator:
                message = await iterator.__anext__()
                assert message.message_id == wrong.event_id
                await message.ack()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if connection is None:
                connection = await aio_pika.connect(url)
            try:
                channel = await connection.channel()
                await channel.queue_delete(queue_name, if_unused=False, if_empty=False)
                await channel.queue_delete(queue_name + ".dlq", if_unused=False, if_empty=False)
                await channel.exchange_delete(unique, if_unused=False)
                await channel.exchange_delete(unique + ".dlx", if_unused=False)
            finally:
                await connection.close()
    asyncio.run(run())
