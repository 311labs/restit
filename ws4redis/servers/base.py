# -*- coding: utf-8 -*-
import sys
from redis import StrictRedis
from http import client as http_client
from ws4redis import settings as private_settings
from ws4redis.exceptions import WebSocketError, HandshakeError, UpgradeRequiredError, SSLRequiredError
from ws4redis.connection import WebsocketConnection

from django.core.exceptions import PermissionDenied
from django.utils.encoding import force_str
from django import http

from rest.log import getLogger
logger = getLogger("async", filename="async.log")


class WebsocketServerBase(object):
    def __init__(self, redis_connection=None):
        """
        redis_connection can be overriden by a mock object.
        """
        self._websockets = set()  # a list of currently active websockets
        self._redis_connection = redis_connection
        if redis_connection is None:
            self._redis_connection = StrictRedis(**private_settings.WS4REDIS_CONNECTION)

        # clear out all online user connections from redis
        self._redis_connection.delete("users:online:connections")
        self._redis_connection.delete("users:online")
        
    def assure_protocol_requirements(self, environ):
        if environ.get('REQUEST_METHOD') != 'GET':
            raise HandshakeError('HTTP method must be a GET')

        if environ.get('SERVER_PROTOCOL') != 'HTTP/1.1':
            raise HandshakeError('HTTP server protocol must be 1.1')

        if environ.get('HTTP_UPGRADE', '').lower() != 'websocket':
            raise HandshakeError('Client does not wish to upgrade to a websocket')

    @property
    def websockets(self):
        return self._websockets

    def __call__(self, environ, start_response):
        """ Hijack the main loop from the original thread and listen on events on Redis and Websockets"""
        connection = None
        try:
            self.assure_protocol_requirements(environ)
            connection = WebsocketConnection(self, environ, start_response)
            connection.handleComs()
        except WebSocketError:
            logger.exception()
            response = http.HttpResponse(status=1001, content='Websocket Closed')
        except UpgradeRequiredError as excpt:
            logger.exception()
            response = http.HttpResponseBadRequest(status=426, content=excpt)
        except HandshakeError as excpt:
            logger.exception()
            response = http.HttpResponseBadRequest(content=excpt)
        except PermissionDenied as excpt:
            logger.exception("PermissionDenied")
            logger.warning('PermissionDenied: {}'.format(excpt), exc_info=sys.exc_info())
            response = http.HttpResponseForbidden(content=excpt)
        except SSLRequiredError as excpt:
            logger.exception("SSLRequiredError")
            response = http.HttpResponseServerError(content=excpt)
        except Exception as excpt:
            logger.exception()
            response = http.HttpResponseServerError(content=excpt)
        else:
            response = http.HttpResponse()
        finally:
            logger.info("closing websocket")
            if connection:
                connection.release()
            else:
                logger.warning('Starting late response on websocket')
                status_text = http_client.responses.get(response.status_code, 'UNKNOWN STATUS CODE')
                status = '{0} {1}'.format(response.status_code, status_text)
                headers = list(response._headers.values())
                # if six.PY3:
                #     headers = list(headers)
                start_response(force_str(status), headers)
                logger.info('Finish non-websocket response with status code: {}'.format(response.status_code))
        return response

