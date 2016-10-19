import asyncio
import json


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


class JSONPublisher(Publisher):
    @asyncio.coroutine
    def publish(self, data):
        """
        Serializes your data to JSON before publishing.
        """
        try:
            data = bytes(json.dumps(data), encoding='UTF-8')
        except TypeError as e:
            print("Error encoding data to JSON: '{}'".format(e))
            raise
        yield from super().publish(data)
