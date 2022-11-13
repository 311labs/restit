from django.conf import settings

DB_READWRITE_APPS = getattr(settings, "DB_READWRITE_APPS", [])
DB_ROUTING_READ = getattr(settings, "DB_ROUTING_READ", {})
DB_ROUTING_WRITE = getattr(settings, "DB_ROUTING_WRITE", {})
DB_ROUTING_RELATIONS = getattr(settings, "DB_ROUTING_RELATIONS", [('default', 'readonly')])
DB_ROUTING_MIGRATIONS = getattr(settings, "DB_ROUTING_MIGRATIONS", {})
DB_ROUTING_MAPS = getattr(settings, "DB_ROUTING_MAPS", None)
DB_ROUTING_READ_DEFAULT = getattr(settings, "DB_ROUTING_READ_DEFAULT", "readonly")


class SimpleRouter:
    """
    A router that can be easily configured to route what database particular apps utilize
    """
    def getMappedDB(self, name):
        if name in DB_ROUTING_MAPS:
            return DB_ROUTING_MAPS[name]
        return name

    def db_for_read(self, model, **hints):
        if "instance" in hints:
            instance = hints.get("instance", None)
            if instance and instance._state.db:
                return self.getMappedDB(instance._state.db)
        # check if this requires read/write dbs
        if model._meta.app_label in DB_READWRITE_APPS:
            return None
        # check if this is priority route
        if hasattr(model, "RestMeta") and getattr(model.RestMeta, "DB_PRIORITY", None):
            return None  
        # check if we have specific route
        for db_name, apps in DB_ROUTING_READ.items():
            if model._meta.app_label in apps:
                return self.getMappedDB(db_name)
        # default to readonly
        return self.getMappedDB(DB_ROUTING_READ_DEFAULT)

    def db_for_write(self, model, **hints):
        # check if we have specific route
        for db_name, apps in DB_ROUTING_WRITE.items():
            if model._meta.app_label in apps:
                return self.getMappedDB(db_name)
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        for rel in DB_ROUTING_RELATIONS:
            if obj1._state.db in rel and obj2._state.db in rel:
                return True
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        apps = DB_ROUTING_MIGRATIONS.get(db, None)
        if apps is None:
            return None  # no preference
        if app_label in apps:
            return True  # allow migrations
        return False  # do not allow migrations
