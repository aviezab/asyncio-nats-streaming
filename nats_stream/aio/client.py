import asyncio
import traceback

from nats.aio import client as NATS
from nats.aio.utils import new_inbox

from nats_stream import pb
from nats_stream.utils import create_guid

DEFAULT_DISCOVER_PREFIX = "_STAN.discover"
DEFAULT_ACK_PREFIX = "_STAN.acks"
DEFAULT_CONNECT_WAIT = 2

# Sub options
DEFAULT_ACK_WAIT = 30  # seconds
DEFAULT_MAX_INFLIGHT = 1024


class Ack:
    def __init__(self, handler, pub):
        """
        :param handler: Func(msg, error)
        :type pub nats_stream.aio.publisher.Publisher
        """
        self.handler = handler
        self.pub = pub


class Msg:
    def __init__(self, proto_msg, sub):
        """
        :type proto_msg: pb.Msg
        :type sub: Subscriber
        """
        self.sub = sub  # Subscription
        self.sequence = proto_msg.sequence
        self.subject = proto_msg.subject
        self.reply = proto_msg.reply
        self.data = proto_msg.data
        self.timestamp = proto_msg.timestamp
        self.redelivered = proto_msg.redelivered
        self.crc = proto_msg.CRC32


class StreamClient:
    def __init__(self):

        self.nc = None
        self.io_loop = None

        self.nc = NATS.Client()
        self.nc_owned = True

        self.client_id = ''
        self.server_id = ''
        self.pub_prefix = ''

        self.sub_requests = ''
        self.unsub_requests = ''
        self.close_requests = ''

        self.sub_map = {}
        self.pub_ack_map = {}

        self.heart_beat_inbox = ''
        self.heart_beat_sub = None

        self.ack_subject = ''
        self.ack_subscription = None

    @asyncio.coroutine
    def connect(self,
                server_id,
                client_id,
                nc=None,
                connect_timeout=DEFAULT_CONNECT_WAIT,
                io_loop=None,
                verbose=False,
                **options):
        """
        Set's up the Stream client and the NATS client if needed.
        """
        if nc:
            self.nc_owned = False
        if not self.nc.is_connected:
            yield from self.nc.connect(
                io_loop=io_loop,
                verbose=verbose,
                **options
            )
        self.server_id = server_id
        self.client_id = client_id
        yield from self._sub_to_heartbeat()
        yield from self._send_connection_request()
        yield from self._sub_to_acks()

    @asyncio.coroutine
    def _send_connection_request(self):
        # Create connect request for streaming service
        connect_req = pb.ConnectRequest()
        connect_req.clientID = self.client_id
        connect_req.heartbeatInbox = self.heart_beat_inbox

        discover_subject = DEFAULT_DISCOVER_PREFIX + "." + self.server_id
        # TODO: Add Timeout
        reply = yield from self.nc.timed_request(discover_subject,
                                                 connect_req.SerializeToString())

        connect_response = pb.ConnectResponse()
        connect_response.ParseFromString(reply.data)
        if connect_response.error:
            raise NATS.NatsError("Connection error: '{}'".format(connect_response.error))

        self.pub_prefix = connect_response.pubPrefix
        self.sub_requests = connect_response.subRequests
        self.unsub_requests = connect_response.unsubRequests
        self.close_requests = connect_response.closeRequests

    @asyncio.coroutine
    def _sub_to_acks(self):
        self.ack_subject = DEFAULT_ACK_PREFIX + "." + create_guid()
        self.ack_subscription = yield from self.nc.subscribe(self.ack_subject, cb=self._process_ack, is_async=True)

    @asyncio.coroutine
    def _sub_to_heartbeat(self):
        # Setup the heartbeat inbox
        self.heart_beat_inbox = new_inbox()
        self.heart_beat_sub = yield from self.nc.subscribe(
            self.heart_beat_inbox, cb=self._process_heartbeat,
            is_async=True
        )

    @asyncio.coroutine
    def close(self):
        """
        Shut's down the Stream Client and possibly the NATS Client.
        """
        if not self.nc.is_connected:
            return

        yield from self.nc.unsubscribe(self.ack_subscription)

        close_req = pb.CloseRequest()
        close_req.clientID = self.client_id
        response = yield from self.nc.timed_request(self.close_requests, close_req.SerializeToString())
        close_resp = pb.CloseResponse()
        close_resp.ParseFromString(response.data)
        if close_resp.error:
            if "unknown clientID" not in close_resp.error:
                raise NATS.NatsError(close_resp.error)
            else:
                print(close_resp.error)
        elif self.nc_owned:
            yield from self.nc.close()

    @asyncio.coroutine
    def _process_heartbeat(self, msg):
        print("Processing HeartBeat: {msg}".format(msg=msg))
        yield from self.nc.publish(msg.reply, b'')

    @asyncio.coroutine
    def publish(self, pub, data):
        """
        Sends the data on the publishers subject.
        Sets up an Ack to call the publishers ack_cb with the message.
        """
        pm = pb.PubMsg()
        pm.clientID = self.client_id
        pm.guid = create_guid()
        pm.subject = pub.subject
        pm.data = data

        ack = Ack(handler=pub.ack_cb, pub=pub)
        self.pub_ack_map[pm.guid] = ack

        subj = self.pub_prefix + "." + pub.subject
        try:
            yield from self.nc.publish_request(subj, self.ack_subject, pm.SerializeToString())
        except Exception:
            print(traceback.format_exc())
            raise

    @asyncio.coroutine
    def _process_ack(self, msg):
        print("Processing ACK: {msg}".format(msg=msg))
        pub_ack = pb.PubAck()
        pub_ack.ParseFromString(msg.data)
        ack = self.pub_ack_map.pop(pub_ack.guid)
        if ack:
            if pub_ack.error:
                raise NATS.NatsError(pub_ack.error)
            if ack.handler and callable(ack.handler):
                if asyncio.iscoroutine(ack.handler):
                    yield from ack.hanlder(pub_ack.guid)
                else:
                    ack.handler(pub_ack.guid)

    @asyncio.coroutine
    def _process_msg(self, raw):
        msg = pb.MsgProto()
        msg.ParseFromString(raw.data)
        msg = Msg(msg, self.sub_map.get(raw.subject))

        if not msg.sub or self.nc.is_closed:
            return

        if msg.sub.message_cb:
            yield from msg.sub.message_cb(msg)

        if self.nc.is_connected and not msg.sub.manual_acks:
            ack_subject = msg.sub.ack_inbox
            ack = pb.Ack()
            ack.subject = msg.subject
            ack.sequence = msg.sequence
            yield from self.nc.publish(ack_subject, ack.SerializeToString())

    @asyncio.coroutine
    def subscribe(self, sub):
        self.sub_map[sub.inbox] = sub

        sub.inbox_sub = yield from self.nc.subscribe_async(sub.inbox, cb=self._process_msg)

        # Setup STAN sub request
        stan_sub = pb.SubscriptionRequest()
        stan_sub.clientID = self.client_id
        stan_sub.subject = sub.subject
        stan_sub.qGroup = sub.queue_name
        stan_sub.inbox = sub.inbox
        stan_sub.maxInFlight = sub.max_inflight
        stan_sub.ackWaitInSecs = sub.ack_wait
        stan_sub.startPosition = sub.start_position
        stan_sub.durableName = sub.durable_name

        if sub.start_at:
            stan_sub.startTimeDelta = sub.start_at
        else:
            stan_sub.startSequence = sub.start_sequence

        # TODO: Timeout?
        reply = yield from self.nc.timed_request(self.sub_requests, stan_sub.SerializeToString())

        sub_resp = pb.SubscriptionResponse()
        sub_resp.ParseFromString(reply.data)
        if sub_resp.error:
            print("Error subscribing {}".format(sub_resp.error))
            yield from self.unsubscribe(sub)
            return

        sub.ack_inbox = sub_resp.ackInbox

    @asyncio.coroutine
    def unsubscribe(self, sub):
        yield from self.nc.unsubscribe(sub.inbox_sub)
        del self.sub_map[sub.inbox]

        unsub_req = pb.UnsubscribeRequest()
        unsub_req.clientID = self.client_id
        unsub_req.subject = sub.subject
        unsub_req.inbox = sub.inbox

        reply = yield from self.nc.request(self.unsub_requests, unsub_req.SerializeToString())
        if reply.error:
            print("Error unsubscribing {}".format(reply.error))
            return

        unsub_resp = pb.SubscriptionResponse()
        unsub_resp.ParseFromString(reply.data)
        if unsub_resp.error:
            print("Error unsubscribing {}".format(unsub_resp.error))


