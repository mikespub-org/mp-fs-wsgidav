# CHECKME: use IAP, wrapper or middleware to set authenticated header
#
# See also https://github.com/mar10/wsgidav/issues/109
#
from __future__ import absolute_import
from builtins import object
#import pickle
import logging

from . import db

import requests
import cachecontrol
import google.auth.transport.requests
import google.oauth2.id_token

# See https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.id_token.html
#firebase_request_adapter = requests.Request()
session = requests.session()
cached_session = cachecontrol.CacheControl(session)
firebase_request_adapter = google.auth.transport.requests.Request(session=cached_session)


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


def verify_user_session(session):
    if not session.user_id:
        return
    #logging.debug('Session: %r' % session.to_dict())
    auth_user = find_auth_user(session.user_id)
    if not auth_user:
        logging.debug('Create AuthorizedUser(%s)' % session.user_id)
        auth_user = AuthorizedUser()
        auth_user.email = session.user_id
        auth_user.nickname = session.nickname
        auth_user.roles = session.roles
        # CHECKME: assign admin rights to first created user!?
        if AuthorizedUser.get_count() < 1:
            logging.debug('Assign admin rights to first AuthorizedUser(%s)' % auth_user.email)
            auth_user.roles = 'admin'
            auth_user.canWrite = True
        #auth_user.put()
    if session.claims and not auth_user.claims:
        logging.debug('Update AuthorizedUser(%s).claims' % auth_user.email)
        if 'user_id' in session.claims:
            auth_user.user_id = session.claims['user_id']
        if 'firebase' in session.claims and 'sign_in_provider' in session.claims['firebase']:
            auth_user.auth_domain = 'Firebase(%s)' % session.claims['firebase']['sign_in_provider']
        else:
            auth_user.auth_domain = 'Firebase()'
        auth_user.claims = session.claims
        auth_user.put()
    if not auth_user.is_saved():
        logging.debug('Save AuthorizedUser(%s)' % auth_user.email)
        auth_user.put()
    if auth_user.roles and not session.roles:
        logging.debug('Update AuthSession(%s).roles: %s' % (session.session_id, auth_user.roles))
        session.roles = auth_user.roles
        session.put()
    #logging.debug('Auth: %r' % auth_user.to_dict())
    return


def check_user_role(claims, role='admin'):
    if not claims:
        return False
    if claims.get('admin'):
        return True
    return role in claims.get('roles', '').split(',')


# Quickly check if an id_token is about a particular sub(ject)
def check_token_subject(id_token, claims):
    import base64
    import json
    if not id_token or not claims:
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
    return payload['sub'] == claims['sub']


class AuthorizedUser(db.CachedModel):
    """Represents authorized users in the datastore."""
    ##user = db.UserProperty()
    #email = db.StringProperty()
    #auth_domain = db.StringProperty()
    #user_id = db.StringProperty()
    #nickname = db.StringProperty()
    #canWrite = db.BooleanProperty(default=True)
    _kind = 'AuthorizedUser'
    _exclude_from_indexes = ['claims']
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

    def set_key(self):
        #if not self.user_id:
        #    self.user_id = uuid.uuid4().hex
        #self._entity.key = self._entity.key.completed_key(self.user_id)
        pass

    #def to_dict(self):
    #    result = super(AuthorizedUser, self).to_dict()
    #    if 'claims' in result and result['claims']:
    #        try:
    #            result['claims'] = pickle.loads(result['claims'])
    #        except Exception as e:
    #            logging.debug('Claims: %r' % result['claims'])
    #            logging.error(e)
    #    return result

    @classmethod
    def get_by_user(cls, user):
        if not user:
            return
        #return cls.gql("where user = :1", user).get()
        return cls.get_by_property('email', user.email().lower())


def find_auth_user(email):
    """Return AuthorizedUser for `email` or None if not found."""
    auth_user = AuthorizedUser.get_by_property('email', email.lower())
    #logging.debug("find_auth_user(%r) = %s" % (email, auth_user))
    return auth_user

