import asyncio


class Publisher:
    def __init__(self, sc, subject, ack_cb):
        """
        A nice little wrapper around publishing messages.

        :type sc StreamClient
        :type subject basestring
        :type ack_cb callable(ack)
        """
        self.sc = sc
        self.subject = subject
        self.ack_cb = ack_cb

    @asyncio.coroutine
    def publish(self, data):
        """
        Sends the data on the subject of the producer and calls ack_cb(ack_msg)
        """
        yield from self.sc.publish(self, data)