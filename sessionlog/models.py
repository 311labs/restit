from django.db import models
from location.models import GeoIP
from importlib import import_module
from django.conf import settings
from django.http import HttpRequest
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from datetime import datetime, timedelta

def GetSessionByID(session_key):
    """
    Initialize same session as done for ``SessionMiddleware``.
    """
    engine = import_module(settings.SESSION_ENGINE)
    return engine.SessionStore(session_key)

class SessionLog(models.Model):
    """
    Logs session information
    """
    session_id = models.CharField(max_length=127, help_text="Django Session ID", db_index=True)
    user = models.ForeignKey("account.User", null=True, blank=True, related_name="sessions", on_delete=models.CASCADE)

    ip = models.CharField(max_length=127, null=True, blank=True, db_index=True)
    user_agent = models.TextField(help_text="Browser user agent", blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True, editable=False, help_text="When session started", db_index=True)
    old_session = models.ForeignKey("self", help_text="Previous session of same user agent", related_name='next_session', null=True, blank=True, on_delete=models.CASCADE)
    location = models.ForeignKey(GeoIP, related_name="sessions", blank=True, null=True, default=None, on_delete=models.CASCADE)
    is_closed = models.BooleanField(default=False, blank=True, db_index=True)

    @property
    def session(self):
        return GetSessionByID(self.session_id)

    def __str__(self):
        return f"{self.user} - {self.ip} - {self.is_closed}"

    def isActive(self):
        return self.session.exists(self.session_id)

    def logout(self):
        session = self.session
        if session and session.exists(self.session_id):
            try:
                request = HttpRequest()
                request.session = session
                auth_logout(request)
            except:
                pass
            session.delete()
        if not self.is_closed:
            self.is_closed = True
            self.save()

    def getLocation(self):
        if self.location is None and self.ip:
            self.location = GeoIP.get(self.ip)
            self.save()
        return self.location

    @staticmethod
    def GetSession(request):
        s = None
        oldsess = request.session.get('_sessionlog_id', None)
        if oldsess:
            try:
                s = SessionLog.objects.get(pk=oldsess)
            except SessionLog.DoesNotExist:
                pass
        if not (s and s.session_id == request.session.session_key):
            if request.user and request.user.is_authenticated:
                user = request.user
            else:
                user = None
            if not request.session.session_key:
                request.session.save()
            s = SessionLog(session_id=request.session.session_key,
                user=user,
                ip=request.META.get('REMOTE_ADDR', None),
                user_agent=request.META.get('HTTP_USER_AGENT', None),
                old_session=s)
            s.save()
            request.session['_sessionlog_id'] = s.pk
        return s

    @staticmethod
    def GetExpired(days=90):
        stale = datetime.now() - timedelta(days=days)
        return SessionLog.objects.filter(user__isnull=False, is_closed=False, created__lte=stale)

    @staticmethod
    def LogOutExpired(days=90):
        qset = SessionLog.GetExpired(days)
        for slog in qset:
            slog.logout()

    @staticmethod
    def Clean(limit=1000):
        qset = SessionLog.objects.filter(user__isnull=False, is_closed=False)[:limit]
        for slog in qset:
            if not slog.isActive():
                slog.is_closed = True
                slog.save()

    def __unicode__(self):
        return "%s / %s@%s" % (self.session_id, self.user, self.ip)
