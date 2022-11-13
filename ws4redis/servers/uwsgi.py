# -*- coding: utf-8 -*-
import uwsgi
import gevent.select

import django
django.setup()

from ws4redis.exceptions import WebSocketError, SSLRequiredError
from ws4redis.servers.base import WebsocketServerBase


class uWSGIWebsocket(object):
    def __init__(self):
        self._closed = False

    def get_file_descriptor(self):
        """Return the file descriptor for the given websocket"""
        try:
            return uwsgi.connection_fd()
        except IOError as e:
            self.close()
            raise WebSocketError(e)

    @property
    def closed(self):
        return self._closed

    def receive(self):
        if self._closed:
            raise WebSocketError("Connection is already closed")
        try:
            return uwsgi.websocket_recv_nb()
        except IOError as e:
            self.close()
            raise WebSocketError(e)

    def flush(self):
        try:
            uwsgi.websocket_recv_nb()
        except IOError:
            self.close()

    def send(self, message, binary=None):
        try:
            uwsgi.websocket_send(message)
        except IOError as e:
            self.close()
            raise WebSocketError(e)

    def close(self, code=1000, message=''):
        self._closed = True


class uWSGIWebsocketServer(WebsocketServerBase):
    def upgrade_websocket(self, environ, start_response):
        try:
            uwsgi.websocket_handshake(environ['HTTP_SEC_WEBSOCKET_KEY'], environ.get('HTTP_ORIGIN', ''))
        except Exception:
            raise SSLRequiredError("UWSGI REQUIRES SSL SUPPORT!")
        return uWSGIWebsocket()

    def select(self, rlist, wlist, xlist, timeout=None):
        return gevent.select.select(rlist, wlist, xlist, timeout)
