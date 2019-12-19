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


__docformat__ = "reStructuredText"
_logger = util.get_module_logger(__name__)


class FirebaseDomainController(BaseDomainController):
    def __init__(self, wsgidav_app, config):
        super(FirebaseDomainController, self).__init__(wsgidav_app, config)

        # auth_conf = config["http_authenticator"]
        dc_conf = config.get("firebase_dc", {})
        self.project_id = dc_conf.get("project_id", None)

    def __str__(self):
        return "{}('{}')".format(self.__class__.__name__, self.project_id)

    def get_domain_realm(self, path_info, environ):
        return "Firebase({})".format(self.project_id)

    def require_authentication(self, realm, environ):
        # TODO: check id_token or trusted_auth_header
        #return False
        return True

    def basic_auth_user(self, realm, user_name, password, environ):
        # We don't have access to a plaintext password (or stored hash)
        return False

    def supports_http_digest_auth(self):
        # We don't have access to a plaintext password (or stored hash)
        return False

