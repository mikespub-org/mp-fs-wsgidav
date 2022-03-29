#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# (c) 2009-2019 Martin Wendt and contributors; see WsgiDAV https://github.com/mar10/wsgidav
# Original PyFileServer (c) 2005 Ho Chun Wei.
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
"""
Simple example how to a run WsgiDAV in a 3rd-party WSGI server.

See https://wsgidav.readthedocs.io/en/latest/sample_wsgi_server.html
"""
from tempfile import gettempdir

from wsgidav.fs_dav_provider import FilesystemProvider
from wsgidav.wsgidav_app import WsgiDAVApp

__docformat__ = "reStructuredText"


def create_app():
    root_path = gettempdir()
    provider = FilesystemProvider(root_path, readonly=True)

    config = {
        "provider_mapping": {"/tmp": provider},
        "http_authenticator": {
            "domain_controller": None  # None: dc.simple_dc.SimpleDomainController(user_mapping)
        },
        "simple_dc": {"user_mapping": {"*": True}},  # anonymous access
        "verbose": 1,
        # "enable_loggers": [],
        "property_manager": True,  # True: use property_manager.PropertyManager
        "lock_storage": True,  # True: use lock_manager.LockManager
    }
    # app = WsgiDAVApp(config)
    return WsgiDAVApp(config)


def run_wsgi_app(app, port=8080):
    # wsgiref.handlers.CGIHandler().run(app)
    from wsgiref.simple_server import make_server

    # configure_logger()
    with make_server("", port, app) as httpd:
        print("Serving HTTP on port %s..." % port)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Goodbye...")


app = create_app()


def main():
    run_wsgi_app(app)


if __name__ == "__main__":
    main()
