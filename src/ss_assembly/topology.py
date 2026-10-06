from ss_archive_sink.transport import BINDINGS as ARCHIVE
from ss_platform_sink.transport import BINDINGS as PLATFORM
from ss_speech_sink.transport import BINDINGS as SPEECH
from ss_surface_sink.transport import BINDINGS as SURFACE

TOPOLOGY = {"ss-archive-sink": ARCHIVE, "ss-platform-sink": PLATFORM, "ss-speech-sink": SPEECH, "ss-surface-sink": SURFACE}

async def configure(url, profile_id, exchange="ss.mre.events"):
    """Configure-only: no message publishing or consumption."""
    import aio_pika
    connection = await aio_pika.connect_robust(url)
    try:
        channel = await connection.channel(publisher_confirms=False)
        bus = await channel.declare_exchange(exchange, aio_pika.ExchangeType.TOPIC, durable=True)
        dead = await channel.declare_exchange(exchange + ".dlx", aio_pika.ExchangeType.DIRECT, durable=True)
        names = []
        for name, bindings in TOPOLOGY.items():
            queue_name = name + "." + profile_id
            dlq = await channel.declare_queue(queue_name + ".dlq", durable=True)
            await dlq.bind(dead, routing_key=queue_name)
            queue = await channel.declare_queue(queue_name, durable=True, arguments={"x-dead-letter-exchange": exchange + ".dlx", "x-dead-letter-routing-key": queue_name})
            for key in bindings:
                await queue.bind(bus, routing_key=key)
            names.append(queue_name)
        return {"ok": True, "exchange": exchange, "queues": names}
    finally:
        await connection.close()
