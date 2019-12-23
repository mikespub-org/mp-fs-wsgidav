# -*- coding: iso-8859-1 -*-

# (c) 2010 Martin Wendt; see CloudDAV http://clouddav.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

import logging
import os

from future import standard_library
from wsgidav.wsgidav_app import DEFAULT_CONFIG, WsgiDAVApp

from btfs.btfs_dav_provider import BTFSResourceProvider

# from btfs.google_dc import GoogleDomainController
from btfs.firebase_dc import FirebaseDomainController
from btfs.memcache_lock_storage import LockStorageMemcache

standard_library.install_aliases()
logging.getLogger().setLevel(logging.DEBUG)

__version__ = "0.3.0a1"


def get_config():
    provider = BTFSResourceProvider()
    # provider = BTFSResourceProvider(backend='datastore', readonly=False)
    lockstorage = LockStorageMemcache()
    # domainController = GoogleDomainController()

    config = DEFAULT_CONFIG.copy()
    config.update(
        {
            "provider_mapping": {"/": provider},
            "verbose": 3,
            "enable_loggers": ["http_authenticator"],
            "property_manager": False,
            "lock_manager": lockstorage,
            # Use Basic Authentication and don't fall back to Digest Authentication,
            # because our domain controller doesn't have no access to the user's
            # passwords.
            "http_authenticator": {
                # None: dc.simple_dc.SimpleDomainController(user_mapping)
                # "domain_controller": None,
                # "domain_controller": GoogleDomainController,
                "domain_controller": FirebaseDomainController,
                "accept_basic": True,  # Allow basic authentication, True or False
                "accept_digest": False,  # Allow digest authentication, True or False
                "default_to_digest": False,  # True (default digest) or False (default basic)
                # Name of a header field that will be accepted as authorized user - set by App Engine for Google Login
                # "trusted_auth_header": "USER_EMAIL",
                "trusted_auth_header": None,
            },
            # "google_dc": {},
            "firebase_dc": {
                # set in app.yaml
                "project_id": os.environ.get("FIREBASE_PROJECT_ID", "MY_PROJECT_ID"),
                # set in app.yaml
                "api_key": os.environ.get("FIREBASE_API_KEY", "MY_API_KEY"),
                # set in app.yaml (optional)
                "id_token": os.environ.get("FIREBASE_ID_TOKEN", "id_token"),
                # default role for authenticated users, unless overridden in /auth/users
                "user_role": os.environ.get("FIREBASE_USER_ROLE", "editor"),
                # default role for anonymous visitors ("none", "browser" or "reader" typically)
                "anon_role": os.environ.get("FIREBASE_ANON_ROLE", "browser"),
            },
            "dir_browser": {
                "enable": True,  # Render HTML listing for GET requests on collections
                "response_trailer": "<a href='https://github.com/mikespub-org/mar10-clouddav'>CloudDAV/%s</a> ${version} - ${time}"
                % __version__,
                "davmount": True,  # Send <dm:mount> response if request URL contains '?davmount'
                "msmount": True,  # Add an 'open as webfolder' link (requires Windows)
            },
        }
    )
    return config


def create_app():
    logging.debug("real_main")
    logger = logging.getLogger("wsgidav")
    logger.propagate = True
    logger.setLevel(logging.DEBUG)

    config = get_config()
    # Preset trusted_auth_header in environ for non-wsgidav applications too
    auth_conf = config.get("http_authenticator", {})
    trusted_auth_header = auth_conf.get("trusted_auth_header", None)
    if trusted_auth_header:
        os.environ["TRUSTED_AUTH_HEADER"] = trusted_auth_header

    return WsgiDAVApp(config)


# Using WSGI - https://cloud.google.com/appengine/docs/standard/python/migrate27#wsgi
app = create_app()
