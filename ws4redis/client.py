import time

from rest import UberDict

from ws4redis.redis import RedisMessage, RedisStore, getRedisClient


def buildEventMessage(name, message=None, priority=0, model=None, model_pk=None, custom=None):
    msg = UberDict(name=name, priority=priority)

    if message:
        msg["message"] = message

    if model:
        msg["component"] = UberDict(pk=model_pk, model=model)

    if custom:
        msg.update(custom)
    return msg.toJSON(as_string=True)


def get(key, default=None):
    c = getRedisClient()
    v = c.get(key)
    if v is None:
        return default
    return v


def set(key, value):
    c = getRedisClient()
    return c.set(key, value)


def incr(key, amount=1):
    c = getRedisClient()
    return c.incr(key, amount)


def decr(key, amount=1):
    c = getRedisClient()
    return c.decr(key, amount)


def delete(key):
    c = getRedisClient()
    return c.delete(key)


# SET FUNCTIONS
def sadd(name, *values):
    # add value to set
    c = getRedisClient()
    return c.sadd(name, *values)


def srem(name, *values):
    # remove value from set
    c = getRedisClient()
    return c.srem(name, *values)


def sismember(name, value):
    # return items in set
    c = getRedisClient()
    return c.sismember(name, value)


def scard(name):
    # count items in set
    c = getRedisClient()
    return c.scard(name)


def smembers(name):
    # return items in set
    c = getRedisClient()
    return c.smembers(name)


# HASH FUNCTIONS
def hget(name, field, default=None):
    c = getRedisClient()
    v = c.hget(name, field)
    if v is None:
        return default
    return v


def hgetall(name):
    c = getRedisClient()
    return c.hgetall(name)


def hset(name, field, value):
    c = getRedisClient()
    return c.hset(name, field, value)


def hdel(name, field):
    c = getRedisClient()
    return c.hdel(name, field)


def hincrby(name, field, inc=1):
    c = getRedisClient()
    return c.hincrby(name, field, inc)


def sendToUser(user, name, message=None, priority=0, model=None, model_pk=None, custom=None):
    return sendMessageToUsers([user], buildEventMessage(name, message, priority, model, model_pk, custom))


def sendToUsers(users, name, message=None, priority=0, model=None, model_pk=None, custom=None):
    return sendMessageToUsers(users, buildEventMessage(name, message, priority, model, model_pk, custom))


def sendMessageToUsers(users, msg):
    return RedisStore().publish(RedisMessage(msg), channel="user", pk=[u.username for u in users])


def sendToGroup(group, name, message=None, priority=0, model=None, model_pk=None, custom=None):
    return sendMessageToModels("group", [group], buildEventMessage(name, message, priority, model, model_pk, custom))


def sendToGroups(groups, name, message=None, priority=0, model=None, model_pk=None, custom=None):
    return sendMessageToModels("group", groups, buildEventMessage(name, message, priority, model, model_pk, custom))


def sendMessageToModels(channel, models, msg):
    return RedisStore().publish(RedisMessage(msg), channel=channel, pk=[g.pk for g in models])


def sendMessageToPK(channel, pk, msg):
    return RedisStore().publish(RedisMessage(msg), channel=channel, pk=pk)


def broadcast(name, message=None, priority=0, model=None, model_pk=None, custom=None):
    return broadcastMessage(buildEventMessage(name, message, priority, model, model_pk, custom))


def broadcastMessage(msg):
    return RedisStore().publish(RedisMessage(msg), channel="broadcast")


def publish(key, data):
    c = getRedisClient()
    if isinstance(data, dict):
        if not isinstance(data, UberDict):
            data = UberDict(data)
        data = data.toJSON(as_string=True)
    return c.publish(key, data)


def subscribe(channel):
    c = getRedisClient()
    pubsub = c.pubsub()
    pubsub.subscribe(channel)
    return pubsub


def waitForMessage(pubsub, msg_filter):
    timeout_at = time.time() + 55
    while time.time() < timeout_at:
        message = pubsub.get_message()
        if message is not None:
            if message.get("type") == "message":
                msg = UberDict.fromJSON(message.get("data"))
                if msg_filter(msg):
                    pubsub.unsubscribe()
                    return msg
        time.sleep(1.0)
    pubsub.unsubscribe()
    return None
