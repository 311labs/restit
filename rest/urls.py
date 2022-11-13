# from django.conf.urls import *
from django.conf import settings
from django.urls import path, include, re_path
import pkgutil
import importlib
import sys
import traceback
from . import views


def loadModule(mod):
    if pkgutil.find_loader(mod) is not None:
        return importlib.import_module(mod)
    return None


urlpatterns = [
    re_path(r'^docs$', views.showDocs),
    re_path(r'^upload$', views.chunkUploadView),
]


def load_app(app, root_module=None):
    module = None
    try:
        module = loadModule(app + '.rpc')
    except ImportError as err:
        print("**** failed to load {0}.rpc! ****".format(app))
        print("**** missing dependencies ****")
        print("**** {0} ****".format(err))
    except SyntaxError:
        print("\t{0}: fail".format(app))
        print("Exception in user code:")
        print('-' * 60)
        traceback.print_exc(file=sys.stdout)
        print('-' * 60)
    except Exception:
        print("\t{0}: fail".format(app))
        print("Exception in user code:")
        print('-' * 60)
        traceback.print_exc(file=sys.stdout)
        print('-' * 60)
    if module:
        if not root_module:
            root_module = module
        prefix = getattr(module, 'URL_PREFIX', app.split('.')[-1])
        if len(prefix) > 1:
            prefix += "/"
        urls = path(prefix, include(root_module))
        urlpatterns.append(urls)
    return module


for app in settings.INSTALLED_APPS:
    module = load_app(app)
    if module:
        if hasattr(module, "RPC_MODULES"):
            sub_modules = getattr(module, "RPC_MODULES")
            for m in sub_modules:
                load_app(m, module)




