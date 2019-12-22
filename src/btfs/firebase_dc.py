# -*- coding: utf-8 -*-
# (c) 2009-2019 Martin Wendt and contributors; see WsgiDAV https://github.com/mar10/wsgidav
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
"""
Implementation of a domain controller that allows users to authenticate via the
Google Identity Platform - based on Firebase Authentication.

Used by HTTPAuthenticator. Only for web-based access or behind an identity-aware proxy.

See https://wsgidav.readthedocs.io/en/latest/user_guide_configure.html
"""
from __future__ import print_function

from wsgidav import util
from wsgidav.dc.base_dc import BaseDomainController

from .sessions import get_current_session

__docformat__ = "reStructuredText"
_logger = util.get_module_logger(__name__)


class FirebaseDomainController(BaseDomainController):
    known_roles = ("admin", "editor", "reader", "browser", "none")

    def __init__(self, wsgidav_app, config):
        super(FirebaseDomainController, self).__init__(wsgidav_app, config)

        # auth_conf = config["http_authenticator"]
        dc_conf = config.get("firebase_dc", {})
        self.project_id = dc_conf.get("project_id", None)
        self.api_key = dc_conf.get("api_key", None)
        self.id_token = dc_conf.get("id_token", "id_token")
        self.user_role = dc_conf.get("user_role", "reader")
        self.anon_role = dc_conf.get("anon_role", "browser")

    def __str__(self):
        return "{}('{}')".format(self.__class__.__name__, self.project_id)

    def get_domain_realm(self, path_info, environ):
        return "Firebase({})".format(self.project_id)

    def require_authentication(self, realm, environ):
        # TODO: check id_token or trusted_auth_header
        # environ["wsgidav.auth.user_name"] = ""
        # The domain controller MAY set those values depending on user's
        # authorization:
        # environ["wsgidav.auth.roles"] = None
        # environ["wsgidav.auth.permissions"] = None
        # "wsgidav.auth.realm": "Firebase(...)"
        if not environ:
            return True
        _logger.debug("Realm: %s" % realm)
        # "wsgidav.auth.user_name": "",
        if environ.get("wsgidav.auth.user_name"):
            _logger.debug("User: %s" % environ.get("wsgidav.auth.user_name"))
            return False
        # "wsgidav.config": {...}
        config = environ.get("wsgidav.config", {})
        auth_conf = config.get("http_authenticator", {})
        trusted_auth_header = auth_conf.get("trusted_auth_header", None)
        if trusted_auth_header and environ.get(trusted_auth_header):
            environ["wsgidav.auth.user_name"] = environ.get(trusted_auth_header)
            if not environ.get("wsgidav.auth.roles"):
                environ["wsgidav.auth.roles"] = [self.user_role]
            _logger.debug("Trusted: %s" % environ.get("wsgidav.auth.user_name"))
            return False
        # "HTTP_COOKIE": "..."
        session = get_current_session(environ)
        if session.is_user():
            environ["wsgidav.auth.user_name"] = session.user_id
            if not environ.get("wsgidav.auth.roles"):
                environ["wsgidav.auth.roles"] = []
            for role in session.get_roles():
                if (
                    role in self.known_roles
                    and role not in environ["wsgidav.auth.roles"]
                ):
                    environ["wsgidav.auth.roles"].append(role)
            if len(environ["wsgidav.auth.roles"]) < 1:
                environ["wsgidav.auth.roles"].append(self.user_role)
            return False
        # "wsgidav.auth.roles": null
        # "wsgidav.auth.permissions": null
        if not environ.get("wsgidav.auth.roles"):
            environ["wsgidav.auth.roles"] = [self.anon_role]
            if self.anon_role in ("browser", "reader", "editor"):
                return False
        # "HTTP_USER_AGENT": "Microsoft-WebDAV-MiniRedir/10.0.17134"
        if "Microsoft-WebDAV-MiniRedir" in environ.get("HTTP_USER_AGENT", ""):
            # TODO: tell users to login via browser at /auth/token first, and then use persistent cookie
            # or basic auth with e-mail & access token here?
            return True
        return True

    def basic_auth_user(self, realm, user_name, password, environ):
        if environ and environ.get("wsgidav.auth.user_name"):
            return True
        # We don't have access to a plaintext password (or stored hash)
        _logger.debug("Realm: %s" % realm)
        _logger.debug("User: %s" % user_name)
        # _logger.debug("Pass: %s" % password)
        # import json
        # _logger.debug("Environ: %s" % json.dumps(environ, indent=2, default=lambda o: repr(o)))
        if "Microsoft-WebDAV-MiniRedir" in environ.get("HTTP_USER_AGENT", ""):
            # TODO: verify persistent cookie or use basic auth with e-mail & access token?
            return True
        return False

    def supports_http_digest_auth(self):
        # We don't have access to a plaintext password (or stored hash)
        return False
