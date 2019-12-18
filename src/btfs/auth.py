# CHECKME: use IAP, wrapper or middleware to set authenticated header
#
# See also https://github.com/mar10/wsgidav/issues/109
#
"""
Taken from 
  http://appengine-cookbook.appspot.com/recipe/restrict-application-to-an-authorized-set-of-users/
"""
from __future__ import absolute_import
from builtins import object
import logging

from . import db
from . import users


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
            'canWrite': False
        }
        for key in template:
            self._entity.setdefault(key, template[key])

    @classmethod
    def get_by_user(cls, user):
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

