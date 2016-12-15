import asyncio
import json
import time

from nats.aio import client as NATS
from nats.aio.utils import new_inbox

from nats_stream import pb
from nats_stream.aio.client import DEFAULT_MAX_INFLIGHT, DEFAULT_ACK_WAIT


class Subscriber:
    NEW_ONLY = 0
    LAST_RECEIVED = 1
    TIME_DELTA_START = 2
    SEQUENCE_START = 3
    FIRST = 4

    def __init__(self,
                 sc,
                 subject,
                 message_cb,
                 queue_name='',
                 durable_name='',
                 max_inflight=DEFAULT_MAX_INFLIGHT,
                 ack_wait=DEFAULT_ACK_WAIT,
                 start_position=NEW_ONLY,
                 start_sequence=None,
                 start_time=None,
                 manual_acks=False,
                 ):
        """
        A nice little wrapper around subscribing.

        :type sc StreamClient
        :type subject basestring
        :type message_cb callable(msg: Msg)
        :type queue_name basestring
        :type max_inflight int
        :type ack_wait: int
        :type start_position: int
        :type start_sequence: int
        :type start_time datetime.datetime
        :type manual_acks bool
        """

        self.sc = sc
        self.subject = subject
        self.queue_name = queue_name
        self.message_cb = message_cb

        self.durable_name = durable_name
        self.max_inflight = max_inflight
        self.ack_wait = ack_wait

        self.start_position = start_position
        self.start_sequence = start_sequence  # sequence to start at
        self.start_time = start_time  # datetime to start at
        self.start_at = None

        if start_time and start_sequence:
            raise NATS.ErrBadSubscription("Cannot start at sequence and time! Pick either time or sequence.")
        if start_time:
            self.start_at = pb.TimeDeltaStart()
            self.start_at = int((time.time() - self.start_time.timestamp()) / 1e-9)  # nano?

        self.manual_acks = manual_acks

        self.inbox = new_inbox()
        self.inbox_sub = None
        self.ack_inbox = None

    @asyncio.coroutine
    def subscribe(self):
        yield from self.sc.subscribe(self)

    @asyncio.coroutine
    def close(self):
        """
        To be used if you plan on restarting the subscriber and continuing where you left off.
        """
        yield from self.sc.unsubscribe(self, close=True)

    @asyncio.coroutine
    def unsubscribe(self):
        """
        To be used if you do not plan on restarting the subscriber and continuing where you left off.
        :return:
        """
        yield from self.sc.unsubscribe(self)


class JSONSubscriber(Subscriber):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.original_message_cb = self.message_cb
        self.message_cb = self._parse_json

    @asyncio.coroutine
    def _parse_json(self, msg):
        msg.data = json.loads(msg.data.decode(encoding='UTF-8'))
        yield from self.original_message_cb(msg)
