import asyncio
import traceback

from nats_stream.aio.client import StreamClient
from nats_stream.aio.publisher import JSONPublisher


async def run(loop):
    sc = StreamClient()
    await sc.connect("test-cluster", "test-client", io_loop=loop)
    pub = JSONPublisher(sc, "test.json", lambda ack: print(ack))

    value_1 = 1
    value_2 = 2
    try:
        await pub.publish({
            "value_1": value_1,
            "value_2": value_2
        })
    except Exception as e:
        print(traceback.format_exc())

    await asyncio.sleep(2)
    await sc.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run(loop))
    finally:
        loop.close()
