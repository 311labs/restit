from redis import ConnectionPool, StrictRedis

from ws4redis import settings

from rest import UberDict
from rest.log import getLogger
logger = getLogger("async", filename="async.log")

REDIS_CON_POOL = None


def getRedisClient():
    global REDIS_CON_POOL
    if REDIS_CON_POOL is None:
        REDIS_CON_POOL = ConnectionPool(**settings.WS4REDIS_CONNECTION)
    return StrictRedis(connection_pool=REDIS_CON_POOL)


class RedisMessage(bytes):
    def __new__(cls, value):
        if isinstance(value, str):
            if value != settings.WS4REDIS_HEARTBEAT:
                return bytes(value, 'utf-8')
        elif isinstance(value, list):
            if len(value) >= 2 and value[0] == b'message':
                return value[2]
        elif isinstance(value, dict):
            if not isinstance(value, UberDict):
                value = UberDict(value)
            return bytes(value.toJSON(as_string=True), 'utf-8')
        elif isinstance(value, bytes):
            return value
        return None


class RedisStore():
    def __init__(self, connection=None):
        self.connection = connection
        if self.connection is None:
            self.connection = getRedisClient()
        self.subscriptions = []
        self.pubsub = None
        self.online_pk = None
        self.online_channel = None
        self.only_one = False  # don't count connections, only allows one instance
        self.expire = settings.WS4REDIS_EXPIRE

    def publish(self, message, channel, facility="events", pk=None, expire=None, prefix=settings.WS4REDIS_PREFIX):
        if expire is None:
            expire = self.expire
        if not isinstance(message, RedisMessage):
            message = RedisMessage(message)

        if not isinstance(message, bytes):
            raise ValueError('message is {} but should be bytes'.format(type(message)))

        if isinstance(pk, list):
            count = 0
            for spk in pk:
                count += self.publish(message, channel, facility, pk=spk, expire=expire, prefix=prefix)
            return count

        channel_key = self.channelToKey(channel, facility, pk, prefix)
        logger.info("publishing to: {0}".format(channel_key))
        count = self.connection.publish(channel_key, message)
        return count

    def getSubMessage(self):
        # get a message pending from subscription
        if self.pubsub:
            return self.pubsub.parse_response()
        return None

    def getPendingMessage(self, channel, facility="events", pk=None, prefix=settings.WS4REDIS_PREFIX):
        # get a message from the connection channel
        channel_key = self.channelToKey(channel, facility, pk, prefix)
        return self.connection.get(channel_key)

    def channelToKey(self, channel, facility="events", pk=None, prefix=settings.WS4REDIS_PREFIX):
        if not pk:
            key = F'{prefix}:{channel}:{facility}'
        else:
            key = F'{prefix}:{channel}:{pk}:{facility}'
        return key

    def subscribe(self, channel, facility, pk=None, prefix=settings.WS4REDIS_PREFIX):
        if self.pubsub is None:
            self.pubsub = self.connection.pubsub()
        key = self.channelToKey(channel, facility, pk, prefix)
        if key not in self.subscriptions:
            logger.info(F"subscribing to: {key}")
            self.subscriptions.append(key)
            self.pubsub.subscribe(key)
        return key

    def unsubscribe(self, channel, facility, pk=None, prefix=settings.WS4REDIS_PREFIX):
        key = self.channelToKey(channel, facility, pk, prefix)
        if key in self.subscriptions:
            logger.info(F"unsubscribing to: {key}")
            self.subscriptions.remove(key)
            self.pubsub.unsubscribe(key)

    def publishModelOnline(self, name, pk, only_one=False):
        if self.online_pk is None:
            self.online_pk = pk
            self.online_channel = name
            self.only_one = only_one
            if self.only_one:
                self.connection.sadd(F"{name}:online", pk)
            else:
                count = self.connection.hincrby(F"{name}:online:connections", pk, 1)
                if count == 1:
                    self.connection.sadd(F"{name}:online", pk)

    def unpublishModelOnline(self):
        if self.online_pk:
            name = self.online_channel
            pk = self.online_pk
            self.online_channel = None
            self.online_pk = None
            if self.only_one:
                self.connection.srem(F"{name}:online", pk)
            else:
                count = self.connection.hincrby(F"{name}:online:connections", pk, -1)
                if count == 0:
                    self.connection.srem(F"{name}:online", pk)

    def get_file_descriptor(self):
        """
        Returns the file descriptor used for passing to the select call when listening
        on the message queue.
        """
        if self.pubsub.connection:
            return self.pubsub.connection._sock.fileno()
        return None

    def release(self):
        """
        New implementation to free up Redis subscriptions when websockets close. This prevents
        memory sap when Redis Output Buffer and Output Lists build when websockets are abandoned.
        """
        self.unpublishModelOnline()
        if self.pubsub and self.pubsub.subscribed:
            self.pubsub.unsubscribe()
            self.pubsub.reset()

