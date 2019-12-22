# CHECKME: use IAP, wrapper or middleware to set authenticated header
#
# See also session cookies at https://firebase.google.com/docs/auth/admin/manage-cookies
#
import os
import datetime
import uuid
from . import db
from .auth import get_user_claims, verify_user_session
import logging

# TODO: make configurable
AUTH_URL = '/auth/'
LOGIN_URL = AUTH_URL + 'login'
LOGOUT_URL = AUTH_URL + 'logout'

COOKIE_NAMES = {}
COOKIE_NAMES['id_token'] = os.environ.get('FIREBASE_ID_TOKEN', 'id_token')
COOKIE_NAMES['session_id'] = '_s_' + COOKIE_NAMES['id_token']


def get_current_session(environ):
    # 1. refuse bots
    if environ.get('HTTP_USER_AGENT'):
        agent = environ.get('HTTP_USER_AGENT')
    else:
        agent = 'Unidentified bot'
    # agent = str(request.user_agent)
    if agent and 'bot' in agent.lower():
        logging.error('Bot agent: %s' % agent)
        raise ConnectionRefusedError
    # 2. get current session from environ
    if environ.get('CURRENT_SESSION'):
        return environ.get('CURRENT_SESSION')
    # 3. check session_id and id_token cookies
    if environ.get('HTTP_COOKIE'):
        cookies = environ.get('HTTP_COOKIE')
    else:
        cookies = None
    # cookies = dict(request.cookies)
    session_id = get_session_id(cookies)
    id_token = get_id_token(cookies)
    # TODO: check for conflicts + create/update if needed
    if session_id and id_token:
        pass
    # 4. get/create session based on session_id
    session = None
    if session_id:
        session = AuthSession.get(session_id)
    if not session:
        session = AuthSession()
    session.agent = agent
    #config = environ.get("wsgidav.config", {})
    #auth_conf = config.get("http_authenticator", {})
    #trusted_auth_header = auth_conf.get("trusted_auth_header", None)
    #if trusted_auth_header and environ.get(trusted_auth_header):
    #    session.user_id = environ.get(self.trusted_auth_header)
    # 5. update session based on id_token
    if id_token:
        claims, error_message = get_user_claims(id_token)
        if claims and claims.get('email') and claims.get('email_verified'):
            session.user_id = claims.get('email').lower()
            session.nickname = claims.get('name')
            if claims.get('roles'):
                session.roles = claims.get('roles')
            session.claims = dict(claims)
            session.put()
        if error_message:
            logging.warning('Token: %s' % error_message)
            environ['ID_TOKEN_ERROR'] = error_message
    # 6. check session against AuthorizedUser database
    verify_user_session(session)
    # 7. save session if needed
    if not session.is_saved():
        session.put()
    # 8. put current session in environ
    environ['CURRENT_SESSION'] = session
    return session


def get_cookie_name(cookie_type):
    if cookie_type not in COOKIE_NAMES:
        raise NotImplementedError
    return COOKIE_NAMES[cookie_type]


def get_session_id(cookies):
    return get_cookie(cookies, 'session_id')


def get_id_token(cookies):
    return get_cookie(cookies, 'id_token')


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
    _kind = 'AuthSession'
    _exclude_from_indexes = ['claims']
    _auto_now_add = ['create_time']
    _auto_now = ['update_time']

    def _init_entity(self, **kwargs):
        super(AuthSession, self)._init_entity(**kwargs)
        now = datetime.datetime.utcnow()
        template = {
            'session_id': '',
            'agent': '',
            'user_id': '',
            'nickname': '',
            'roles': '',
            'claims': None,
            # available by default for document snapshots with firestore in native mode
            'create_time': now,
            'update_time': now 
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
            return self.roles.split(',')
        return self.roles

    def is_user(self):
        if self.user_id:
            return True
        return False

    def has_role(self, role):
        return role in self.get_roles()

    def has_access(self, access):
        allowed = {
            'admin': ('admin'),
            'write': ('admin', 'editor'),
            'read': ('admin', 'editor', 'reader'),
            'browse': ('admin', 'editor', 'reader', 'browser')
        }
        for role in allowed[access]:
            if self.has_role(role):
                return True
        return False

    @classmethod
    def get_session(cls, environ):
        return get_current_session(environ)

    @classmethod
    def gc(cls, days=10, limit=1000, offset=0, **kwargs):
        query = cls.query(**kwargs)
        query.keys_only()
        expired = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        query.add_filter('update_time', '<', expired)
        result = []
        for entity in query.fetch(limit, offset):
            result.append(entity.key)
        logging.debug('GC: %s' % len(result))
        if len(result) > 0:
            db.get_client().delete_multi(result)

