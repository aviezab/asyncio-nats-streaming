import asyncio
import traceback

from nats_stream.aio.client import StreamClient, Publisher

async def run(loop):
    sc = StreamClient()
    await sc.connect("test-cluster", "test-client", io_loop=loop)
    pub = Publisher(sc, "test", lambda ack: print(ack))

    try:
        await pub.publish(b'test publish')
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
