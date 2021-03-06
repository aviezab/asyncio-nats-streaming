import asyncio
import signal

import time

from nats_stream.aio.client import StreamClient, Msg
from nats_stream.aio.subscriber import JSONSubscriber


async def message_handler(msg: Msg):
    print(type(msg.data))
    print(msg.data)


async def run(loop):
    sc = StreamClient()
    sub = JSONSubscriber(sc, 'test.json', message_handler, start_sequence=0)

    async def closed_cb():
        print("Connection to NATS closed.")
        await asyncio.sleep(0.1, loop=loop)
        loop.stop()

    async def reconnected_cb():
        print("Connected to NATS at {}...".format(sc.nc.connected_url.netloc))

    def signal_handler():
        if sc.nc.is_closed:
            return
        print("Disconnecting...")
        loop.create_task(sub.unsubscribe())
        time.sleep(2)
        loop.create_task(sc.close())

    for sig in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, sig), signal_handler)

    options = {
        'io_loop': loop,
        'closed_cb': closed_cb,
        'reconnected_cb': reconnected_cb,
    }
    await sc.connect("test-cluster", "test-client-2", **options)
    await sub.subscribe()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(loop))
    try:
        loop.run_forever()
    finally:
        loop.close()
