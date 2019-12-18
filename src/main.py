#!/usr/bin/env python3
#
# Central dispatcher for flask & webapp2 apps
#
# Application Dispatching - https://flask.palletsprojects.com/en/1.1.x/patterns/appdispatch/
from builtins import object
from threading import RLock
from werkzeug.wsgi import pop_path_info, peek_path_info, get_path_info
# Lazy Loading - https://flask.palletsprojects.com/en/1.1.x/patterns/lazyloading/
from werkzeug.utils import import_string, cached_property
import json
import re
# Import for local testing
import set_env
# Import default app here
from clouddav import app as default_app


class PathDispatcher(object):

    def __init__(self, default_app, handlers=None, root='/'):
        self.default_app = default_app
        self.handlers = handlers
        self.root = root
        self.lock = RLock()
        self.instances = {}

    def find_handler(self, path):
        if self.handlers is None:
            return
        # let static_app handle static files
        #if path.startswith('/static/'):
        #    return 'static_app'
        for handler in self.handlers:
            if 'script' not in handler:
                continue
            m = re.match(handler['url'], path)
            if not m:
                continue
            return handler['script']

    def import_app(self, handler):
        if handler is not None:
            return import_string(handler)

    def get_application(self, handler):
        if not handler:
            return
        with self.lock:
            app = self.instances.get(handler)
            if app is None:
                app = self.import_app(handler)
                if app is not None:
                    self.instances[handler] = app
            return app

    def __call__(self, environ, start_response):
        #prefix = peek_path_info(environ)
        # [/root]/prefix[/more] -> /prefix[/more]
        path = get_path_info(environ).replace(self.root, '/')
        handler = self.find_handler(path)
        app = self.get_application(handler)
        #print(handler, app, path)
        #pop_path_info(environ)
        if app is not None and self.root != '/':
            environ['PATH_INFO'] = environ['PATH_INFO'].replace(self.root, '/')
            if 'REQUEST_URI' in environ:
                environ['REQUEST_URI'] = environ['REQUEST_URI'].replace(self.root, '/')
            #environ['SCRIPT_NAME'] = environ['SCRIPT_NAME'] + self.root[:-1]
        if app is None:
            app = self.default_app
        return app(environ, start_response)


def make_handlers():
    import yaml
    with open('app.yaml.template', 'r') as fp:
        info = yaml.unsafe_load(fp)
    with open('app.handlers.json', 'w') as fp:
        json.dump(info['handlers'], fp, indent=2)


def get_handlers(script_only=True):
    handlers = []
    with open('app.handlers.json', 'r') as fp:
        info = json.load(fp)
        for handler in info:
            if script_only and 'script' not in handler:
                continue
            if 'script' in handler and handler['script'].startswith('google.appengine.'):
                continue
            handlers.append(handler)
    return handlers

handlers = get_handlers()
app = PathDispatcher(default_app, handlers, '/')
# CHECKME: with profile per request
#from werkzeug.middleware.profiler import ProfilerMiddleware
#app = ProfilerMiddleware(app)


def run_wsgi_app(app, port=8080):
    from wsgiref.simple_server import make_server
    with make_server('', port, app) as httpd:
        print("Serving HTTP on port %s..." % port)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt as e:
            print("Goodbye...")


def main():
    #import logging
    #logging.basicConfig(format='%(levelname)s:%(module)s.%(funcName)s:%(message)s', level=logging.DEBUG)
    run_wsgi_app(app)


if __name__ == '__main__':
    main()

