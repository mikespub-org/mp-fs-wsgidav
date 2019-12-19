# CHECKME: use IAP, wrapper or middleware to set authenticated header
#
# See also https://github.com/mar10/wsgidav/issues/109
#
from __future__ import absolute_import
from builtins import object
import logging

from . import db
from . import users

import requests
import cachecontrol
import google.auth.transport.requests
import google.oauth2.id_token

# See https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.id_token.html
#firebase_request_adapter = requests.Request()
session = requests.session()
cached_session = cachecontrol.CacheControl(session)
firebase_request_adapter = google.auth.transport.requests.Request(session=cached_session)


# See also session cookies at https://firebase.google.com/docs/auth/admin/manage-cookies
def get_id_token(request, cookie_name='id_token'):
    return request.cookies.get(cookie_name)


def get_user_claims(id_token):
    # Verify Firebase auth.
    error_message = None
    claims = None

    if id_token:
        try:
            # Verify the token against the Firebase Auth API. This example
            # verifies the token on each page load. For improved performance,
            # some applications may wish to cache results in an encrypted
            # session store (see for instance
            # http://flask.pocoo.org/docs/1.0/quickstart/#sessions).
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)

        except ValueError as exc:
            # This will be raised if the token is expired or any other
            # verification checks fail.
            error_message = str(exc)

    return claims, error_message


def check_user_role(claims, role='admin'):
    if not claims:
        return False
    if claims.get('admin'):
        return True
    return role in claims.get('roles', '').split(',')


# Quickly check if an id_token is about a particular sub(ject)
def check_token_subject(id_token, auth):
    import base64
    import json
    if not id_token or not auth:
        return False
    header, payload, signature = id_token.split('.')
    if len(payload) % 4 != 0:
        payload += '=' * (len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload.encode('utf-8'))
        payload = json.loads(decoded)
    except Exception as e:
        logging.warning(e)
        return False
    if not isinstance(payload, dict) or 'sub' not in payload:
        return False
    return payload['sub'] == auth['sub']


class AuthorizedUser(db.Model):
    """Represents authorized users in the datastore."""
    ##user = db.UserProperty()
    #email = db.StringProperty()
    #auth_domain = db.StringProperty()
    #user_id = db.StringProperty()
    #nickname = db.StringProperty()
    #canWrite = db.BooleanProperty(default=True)
    _kind = 'AuthorizedUser'
    _exclude_from_indexes = None
    _auto_now_add = None
    _auto_now = None

    def _init_entity(self, **kwargs):
        super(AuthorizedUser, self)._init_entity(**kwargs)
        template = {
            'email': '',
            'auth_domain': '',
            'user_id': '',
            'nickname': '',
            'user': None,
            'canWrite': False,
            'roles': '',
            'claims': None
        }
        for key in template:
            self._entity.setdefault(key, template[key])

    @classmethod
    def get_by_user(cls, user):
        if not user or not user.email():
            return
        #return cls.gql("where user = :1", user).get()
        query = db.get_client().query(kind=cls._kind)
        query.add_filter('email', '=', user.email())
        #query.add_filter('auth_domain', '=', user.auth_domain())
        entities = list(query.fetch(1))
        if entities and len(entities) > 0:
            return cls.from_entity(entities[0])

    @classmethod
    def get_by_email(cls, email):
        user = users.User(email)
        return cls.get_by_user(user)


def find_auth_user(email):
    """Return AuthorizedUser for `email` or None if not found."""
    auth_user = AuthorizedUser.get_by_email(email)
    logging.debug("find_auth_user(%r) = %s" % (email, auth_user))
    return auth_user

