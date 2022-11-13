import time
from rest.jwtoken import JWToken
from rest import UberDict
from rest.crypto import util
from django.core.handlers.wsgi import WSGIRequest
from django.apps import apps

from ws4redis import settings as private_settings
from ws4redis.redis import RedisStore, RedisMessage

from rest.log import getLogger
logger = getLogger("async", filename="async.log")

MODEL_CACHE = dict()  # caching of app.Model for faster access


def getRemoteIP(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class WebsocketConnection():
    def __init__(self, server, environ, start_response):
        self.server = server
        self.request = WSGIRequest(environ)
        self.ip = getRemoteIP(self.request)
        self.ua = self.request.META.get('HTTP_USER_AGENT', '')
        self.facility = self.request.path_info.replace(private_settings.WEBSOCKET_URL, '', 1)
        self.credentials = UberDict()
        self.listening_fds = None
        self.redis = RedisStore(server._redis_connection)
        self.websocket = server.upgrade_websocket(environ, start_response)
        self.last_beat = time.time()
        self.last_msg = None
        self._heart_beat = util.toString(private_settings.WS4REDIS_HEARTBEAT)

    def refreshFDs(self):
        if len(self.listening_fds) == 1:
            sub_sd = self.redis.get_file_descriptor()
            if sub_sd:
                self.listening_fds.append(sub_sd)

    def on_auth(self, msg):
        if msg.kind == "jwt":
            self.on_auth_jwt(msg)
            return
        # check our other auth mechanisms
        auther = self.getAuthenticator(msg.kind)
        if auther is None or not hasattr(auther, "authWS4RedisConnection"):
            logger.error("invalid auth", msg)
            raise Exception("invalid auther")

        self.credentials = auther.authWS4RedisConnection(msg)
        if self.credentials is None or self.credentials.pk is None:
            logger.error("invalid credentials for", msg, self.credentials)
            raise Exception("invalid credentials")
        self.on_authenticated()

    def on_auth_jwt(self, msg):
        token = JWToken(msg.token)
        if token.payload is None:
            raise Exception("invalid auth token")
        Member = apps.get_model("account", "Member")
        member = Member.objects.filter(pk=token.payload.user_id).last()
        if member is None:
            raise Exception("invalid user token")
        token.key = member.security_token
        if not token.is_valid:
            raise Exception("invalid signature")
        if not token.isExpired():
            raise Exception("token expired")
        member.canLogin(self.request)
        self.credentials = UberDict(kind="member", instance=member, pk=member.pk, uuid=member.username)
        self.on_authenticated()
 
    def on_authenticated(self):
        logger.info(F"authenticated {self.credentials.kind}: {self.credentials.uuid}")
        if self.credentials.kind == "member":
            channel_key = self.redis.subscribe("user", self.facility, self.credentials.uuid)
            self.forwardPending(channel_key)
        else:
            channel_key = self.redis.subscribe(self.credentials.kind, self.facility, self.credentials.uuid)
            self.forwardPending(channel_key)

        self.redis.publishModelOnline(self.credentials.kind, self.credentials.pk, only_one=self.credentials.only_one)
        self.refreshFDs()

    def forwardPending(self, channel_key):
        msg = self.redis.getPendingMessage(channel_key)
        if msg:
            logger.info("pending messages", repr(msg))
            channel, pk = self.parseChannel(channel_key)
            self.sendToWS(channel, msg, pk)

    def on_resubscribe(self, msg):
        for ch in msg.channels:
            self.redis.subscribe(ch.channel, self.facility, ch.pk)

    def getAppModel(self, app_model):
        if app_model not in MODEL_CACHE:
            app_label, model_name = app_model.split('.')
            MODEL_CACHE[app_model] = apps.get_model(app_label, model_name)
        return MODEL_CACHE[app_model]

    def getAuthenticator(self, channel):
        auther_path = private_settings.WS4REDIS_AUTHENTICATORS.get(channel, None)
        if auther_path is not None:
            return self.getAppModel(auther_path)
        return None

    def on_subscribe(self, msg):
        pks = self.canSubscribeTo(msg)
        if bool(pks):
            for pk in pks:
                channel_key = self.redis.subscribe(msg.channel, self.facility, pk)
        else:
            logger.warning("subscribe permission denied", msg)
            self.sendToWS(msg.channel, dict(error="subscribe permission denied"))

    def canSubscribeTo(self, msg):
        ch_model = private_settings.WS4REDIS_CHANNELS.get(msg.channel, None)
        if not ch_model:
            return None
        if ch_model == "any":
            # this allows anything to be sent
            return [msg.pk]
        Model = self.getAppModel(ch_model)
        if not hasattr(Model, "canSubscribeTo"):
            return None
        return Model.canSubscribeTo(self.credentials, msg)

    def on_unsubscribe(self, msg):
        self.redis.unsubscribe(msg.channel, self.facility, msg.pk)

    def on_publish(self, msg):
        if self.canPublishTo(msg):
            self.redis.publish(msg.message, channel=msg.channel, pk=msg.pk)
        else:
            logger.warning("publish permission denied", msg)
            self.sendToWS(msg.channel, dict(error="publish permission denied"))

    def canPublishTo(self, msg):
        ch_model = private_settings.WS4REDIS_CHANNELS.get(msg.channel, None)
        if not ch_model:
            return False
        Model = self.getAppModel(ch_model)
        if not hasattr(Model, "canPublishTo"):
            return False
        return Model.canPublishTo(self.credentials, msg)

    def on_ws_msg(self, raw_data):
        if isinstance(raw_data, bytes):
            raw_data = util.toString(raw_data)
        if raw_data == self._heart_beat:
            # echo the heartbeat
            self.websocket.send(self._heart_beat)
            return
        logger.info("on_ws_msg", repr(raw_data))
        dmsg = UberDict.fromJSON(raw_data, ignore_errors=True)
        if dmsg.action:
            # this is a special message that we want to handle directly
            if dmsg.action == "auth":
                self.on_auth(dmsg)
            elif dmsg.action == "subscribe":
                self.on_subscribe(dmsg)
            elif dmsg.action == "unsubscribe":
                self.on_unsubscribe(dmsg)
            elif dmsg.action == "resubscribe":
                self.on_resubscribe(dmsg)
            elif dmsg.action == "publish":
                self.on_publish(dmsg)
            elif dmsg.channel:
                self.on_channel_msg(dmsg)

    def on_channel_msg(self, msg):
        if not self.canPublishTo(msg):
            logger.warning("on_channel_msg permission denied", msg)
            return None
        ch_model = private_settings.WS4REDIS_CHANNELS.get(msg.channel, None)
        Model = self.getAppModel(ch_model)
        if not hasattr(Model, "onWS4RedisMessage"):
            logger.warning(f"{msg.channel} does not support onWS4RedisMessage")
            return None
        Model.onWS4RedisMessage(self.credentials, msg)

    def on_redis_pending(self):
        sub_resp = self.redis.getSubMessage()
        if sub_resp:
            logger.info("incoming redis msg", sub_resp)
            self.on_redis_msg(sub_resp)

    def sendToWS(self, channel, message, pk=None):
        msg = UberDict(channel=channel)
        if pk is not None:
            msg.pk = pk
        if isinstance(message, (str, bytes)):
            msg.message = UberDict.fromJSON(message, ignore_errors=True)
        if not msg.message:
            msg.message = message
        elif msg.message.name == "logout" and msg.message.pk == self.credentials.pk:
            raise Exception("websocket is being logged out")
        self.websocket.send(msg.toJSON(as_string=True)) 

    def on_redis_msg(self, sub_resp):
        if isinstance(sub_resp, list):
            if sub_resp[0] == b'subscribe':
                # this is succesfull subscriptions
                # notify ws
                channel, pk = self.parseChannel(sub_resp[1].decode())
                msg = UberDict(name="subscribed", channel=channel, status=sub_resp[2])
                if pk is not None:
                    msg.pk = pk
                self.websocket.send(msg.toJSON(as_string=True))
                return
            elif sub_resp[0] == b'unsubscribe':
                # this is succesfull subscriptions
                # notify ws
                channel, pk = self.parseChannel(sub_resp[1].decode())
                msg = UberDict(name="unsubscribed", channel=channel, status=sub_resp[2])
                if pk is not None:
                    msg.pk = pk
                self.websocket.send(msg.toJSON(as_string=True))
                return
            elif sub_resp[0] == b'message':
                channel, pk = self.parseChannel(sub_resp[1].decode())
                self.sendToWS(channel, sub_resp[2].decode(), pk)
                return
        sendmsg = RedisMessage(sub_resp)
        logger.info(sub_resp)
        if sendmsg:
            logger.info("pushing to websocket", sendmsg)
            self.websocket.send(sendmsg)

    def parseChannel(self, channel):
        fields = channel.split(":")
        fields.pop(0)
        fields.pop()
        if len(fields) == 1:
            return fields[0], None
        return fields[0], fields[1]

    def on_ws_pending(self):
        try:
            self.last_msg = self.websocket.receive()
            if bool(self.last_msg):
                self.on_ws_msg(self.last_msg)
        except Exception:
            logger.exception()
            logger.info("unable to recv on ws... flushing")
            self.websocket.flush()

    def checkHeartbeat(self):
        beat_delta = time.time() - self.last_beat
        if beat_delta > 30.0:
            self.last_beat = time.time()
            if private_settings.WS4REDIS_HEARTBEAT and not self.websocket.closed:
                # logger.info("send heartbeat")
                self.websocket.send(private_settings.WS4REDIS_HEARTBEAT)

    def release(self):
        self.redis.release()
        self.listening_fds = None
        if self.websocket:
            self.websocket.close(code=1001, message='Websocket Closed')

    def handleComs(self):
        # check if token is in url
        websocket_fd = self.websocket.get_file_descriptor()
        self.listening_fds = [websocket_fd]

        token = self.request.GET.get("token", None)
        if token is not None and private_settings.URL_AUTHENTICATOR is not None:
            self.on_auth(UberDict(kind=private_settings.URL_AUTHENTICATOR, token=token))

        session_key = self.request.GET.get("session_key", None)
        if session_key is not None:
            self.on_auth(UberDict(kind="session", token=session_key))

        no_cred_count = 0
        
        while self.websocket and not self.websocket.closed:
            ready = self.server.select(self.listening_fds, [], [], 4.0)[0]
            if not ready:
                self.websocket.flush()
            if not self.credentials:
                no_cred_count += 1
                if no_cred_count > 10:
                    logger.error(f"{self.ip} has sent no credentials", self.ua)
                    no_cred_count = 0
                    self.sendToWS("member", dict(error="no credentials received"))
                    
            for fd in ready:
                if fd == websocket_fd:
                    self.on_ws_pending()
                else:
                    self.on_redis_pending()
