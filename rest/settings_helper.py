from django.conf import settings as django_settings
import importlib

UNKNOWN = object()


class SettingsHelper():
    def __init__(self, root_settings, defaults=None):
        self.root = root_settings
        self.defaults = defaults
        self._app_cache = dict()

    def getAppSettings(self, app_name):
        # this will wrap a settings helper around app settings and defaults
        key = "{}_SETTINGS".format(app_name.upper())
        if key in self._app_cache:
            return self._app_cache[key]
        try:
            defaults = importlib.import_module(f"{app_name}.settings")
        except Exception:
            defaults = dict()
        self._app_cache[key] = SettingsHelper(self.get(key, dict()), defaults)
        return self._app_cache[key]

    def get(self, name, default=UNKNOWN):
        if isinstance(self.root, dict):
            res = self.root.get(name, UNKNOWN)
        else:
            res = getattr(self.root, name, UNKNOWN)
        if res == UNKNOWN:
            return self.getDefault(name, default)
        return res

    def getDefault(self, name, default=None):
        if isinstance(self.defaults, dict):
            return self.defaults.get(name, default)
        return getattr(self.defaults, name, default)

    def __getattr__(self, name):
        """Access settings as an attribute."""
        return self.get(name, None)

    def __getitem__(self, key):
        """Access settings as a dictionary key."""
        return self.get(key)


settings = SettingsHelper(django_settings)
