#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: https://opensource.org/licenses/mit-license.php
#
# CHECKME: use IAP, wrapper or middleware to set authenticated header
#
# See also session cookies at https://firebase.google.com/docs/auth/admin/manage-cookies
#
import datetime
import logging
import os
import uuid
from functools import wraps

from data import db
from .auth import get_user_claims, verify_user_session

# TODO: make configurable
AUTH_URL = "/auth/"
LOGIN_URL = AUTH_URL + "login"
LOGOUT_URL = AUTH_URL + "logout"

COOKIE_NAMES = {}
COOKIE_NAMES["id_token"] = os.environ.get("FIREBASE_ID_TOKEN", "id_token")
COOKIE_NAMES["session_id"] = "_s_" + COOKIE_NAMES["id_token"]

EXPIRE_DAYS = 1


def get_current_session(environ):
    # 1. refuse bots
    agent = "Unidentified bot"
    if environ.get("HTTP_USER_AGENT"):
        agent = environ.get("HTTP_USER_AGENT")
        # agent = str(request.user_agent)
    if agent and "bot" in agent.lower():
        logging.debug("Bot agent: %s" % agent)
        raise ConnectionRefusedError
    # 2. get current session from environ
    if environ.get("CURRENT_SESSION"):
        return environ.get("CURRENT_SESSION")
    # 3. check session_id and id_token cookies
    session_id = None
    id_token = None
    if environ.get("HTTP_COOKIE"):
        cookies = environ.get("HTTP_COOKIE")
        # cookies = dict(request.cookies)
        session_id = get_session_id(cookies)
        id_token = get_id_token(cookies)
    # 4. get/create session based on session_id
    session = None
    if session_id:
        session = AuthSession.get(session_id)
    if not session:
        session = AuthSession()
    session.agent = agent
    # 5. verify trusted auth header (if any - preset from config in clouddav.py)
    # config = environ.get("wsgidav.config", {})
    # auth_conf = config.get("http_authenticator", {})
    # trusted_auth_header = auth_conf.get("trusted_auth_header", None)
    trusted_auth_header = environ.get("TRUSTED_AUTH_HEADER", None)
    if trusted_auth_header and environ.get(trusted_auth_header):
        session.user_id = environ.get(trusted_auth_header)
        session.nickname = session.user_id.split("@")[0]
        logging.debug("Trusted: %s" % session.user_id)
    # 6. update session based on id_token
    if id_token:
        claims, error_message = get_user_claims(id_token)
        if claims and claims.get("email") and claims.get("email_verified"):
            session.user_id = claims.get("email").lower()
            session.nickname = claims.get("name")
            if claims.get("roles"):
                session.roles = claims.get("roles")
            session.claims = dict(claims)
            session.put()
        elif claims:
            """ Example of anonymous claim:
            {
                "provider_id": "anonymous",
                "iss": "https://securetoken.google.com/MY_PROJECT_ID",
                "aud": "MY_PROJECT_ID",
                "auth_time": 1577036411,
                "user_id": "86UkBQY...",
                "sub": "86UkBQY...",
                "iat": 1577036411,
                "exp": 1577040011,
                "firebase": {
                    "identities": {},
                    "sign_in_provider": "anonymous"
                }
            }
            """
            logging.debug("Claims: %r" % claims)
        if error_message:
            logging.info("Token: %s" % error_message)
            environ["ID_TOKEN_ERROR"] = error_message
    # 7. check session against AuthorizedUser database
    verify_user_session(session)
    # 8. save session if needed
    if not session.is_saved():
        # TODO: recognize CalDAV/CardDAV requests and ignore too?
        # if "Microsoft-WebDAV-MiniRedir" not in session.agent:
        if environ.get("REQUEST_METHOD", "") in ("GET", "HEAD"):
            session.put()
    # 9. put current session in environ
    environ["CURRENT_SESSION"] = session
    return session


# called from btfs_dav_provider by wsgidav.request_server for do_GET and do_HEAD methods
# we should also send cookies for 401, but basic auth is handled earlier in wsgidav.http_authenticator
def finalize_headers(environ, response_headers):
    if not environ.get("CURRENT_SESSION"):
        return
    session = environ.get("CURRENT_SESSION")
    if not session.session_id:
        return
    # logging.debug("Headers: %r" % response_headers)
    header = "Set-Cookie"
    value = make_session_id_value(session.session_id)
    response_headers.append((header, value))
    return


def make_session_id_value(session_id):
    key = get_cookie_name("session_id")
    val = session_id
    max_age = (
        EXPIRE_DAYS * 24 * 60 * 60
    )  # set to EXPIRE_DAYS days here (id_token expires in 1 hour)
    path = "/"
    value = "%s=%s; Max-Age=%s; Path=%s" % (key, val, max_age, path)
    return value


def get_cookie_name(cookie_type):
    if cookie_type not in COOKIE_NAMES:
        raise NotImplementedError
    return COOKIE_NAMES[cookie_type]


def get_session_id(cookies):
    return get_cookie(cookies, "session_id")


def get_id_token(cookies):
    return get_cookie(cookies, "id_token")


def get_cookie(cookies, cookie_type):
    if not cookies:
        return
    cookie_name = get_cookie_name(cookie_type)
    # (str) from wsgi environ.get("HTTP_COOKIE") or equivalent from HTTP headers
    if isinstance(cookies, str):
        from werkzeug.http import parse_cookie

        cookies = parse_cookie(cookies)
    # (dict-like) from flask request.cookies or equivalent from other frameworks
    return cookies.get(cookie_name)


class AuthSession(db.CachedModel):
    _kind = "AuthSession"
    _exclude_from_indexes = ["claims"]
    _auto_now_add = ["create_time"]
    _auto_now = ["update_time"]

    def _init_entity(self, **kwargs):
        super(AuthSession, self)._init_entity(**kwargs)
        now = datetime.datetime.now(datetime.timezone.utc)
        template = {
            "session_id": "",
            "agent": "",
            "user_id": "",
            "nickname": "",
            "roles": "",
            "claims": None,
            # available by default for document snapshots with firestore in native mode
            "create_time": now,
            "update_time": now,
        }
        for key in template:
            self._entity.setdefault(key, template[key])

    def set_key(self):
        if not self.session_id:
            self.session_id = uuid.uuid4().hex
        self._entity.key = self._entity.key.completed_key(self.session_id)

    def get_roles(self):
        if self.roles is None:
            return []
        if isinstance(self.roles, str):
            return self.roles.split(",")
        return self.roles

    def is_user(self):
        if self.user_id:
            return True
        return False

    def has_role(self, role):
        return role in self.get_roles()

    def has_access(self, access):
        allowed = {
            "admin": ("admin"),
            "delete": ("admin", "editor"),
            "write": ("admin", "editor"),
            "read": ("admin", "editor", "reader"),
            "browse": ("admin", "editor", "reader", "browser"),
        }
        for role in allowed[access]:
            if self.has_role(role):
                return True
        return False

    @classmethod
    def get_session(cls, environ):
        return get_current_session(environ)

    @classmethod
    def gc(cls, days=EXPIRE_DAYS, limit=1000, offset=0, **kwargs):
        query = cls.query(**kwargs)
        query.keys_only()
        expired = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=days
        )
        query.add_filter("update_time", "<", expired)
        result = []
        for entity in query.fetch(limit, offset):
            result.append(entity.key)
        logging.debug("GC: %s" % len(result))
        if len(result) > 0:
            db.get_client().delete_multi(result)
        return len(result)


def flask_authorize(role, do_redirect=False):
    """ Decorator to authorize access to Flask view functions based on user roles.

    The authorization is based on the highest role the current user has:
        admin > editor > reader > browser > none

    @app.route("/admin/")
    @sessions.flask_authorize("admin")
    def admin_view():
        return "Congratulations, you have the 'admin' role..."

    @app.route("/editor/")
    @sessions.flask_authorize("editor")
    def editor_view():
        return "Congratulations, you have (at least) the 'editor' role..."

    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request, redirect

            session = get_current_session(request.environ)
            # always provide access to admin role
            if session.has_role("admin"):
                return f(*args, **kwargs)
            elif role == "admin":
                if do_redirect:
                    return redirect(LOGIN_URL)
                output = (
                    "You need to login as administrator <a href='%s'>Login</a>"
                    % LOGIN_URL
                )
                return output
            # this will raise an error if the role is unknown (which is a good thing)
            min_access_required = {
                "editor": "write",
                "reader": "read",
                "browser": "browse",
                # "none": "*"
            }
            access = min_access_required[role]
            # any access control requires an authenticated user, at least for view functions
            if role in min_access_required and not session.is_user():
                if do_redirect:
                    return redirect(LOGIN_URL)
                output = "You need to login as user <a href='%s'>Login</a>" % LOGIN_URL
                return output
            # check if the user has the right access or not
            if not session.has_access(access):
                if do_redirect:
                    return redirect(LOGOUT_URL)
                output = (
                    "You need to login as '%s' <a href='%s'>Logout</a>"
                    % role
                    % LOGOUT_URL
                )
                return output
            # run the view function
            return f(*args, **kwargs)

        return decorated_function

    return decorator
