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

try:
    from google.appengine.ext import db
except:
    from . import db

try:
    from google.appengine.api import users
except:
    from . import users

    # TODO: make configurable
    users.AUTH_URL = '/auth/'


class AuthorizedUser(db.Model):
    """Represents authorized users in the datastore."""
    user = db.UserProperty()
    canWrite = db.BooleanProperty(default=True)


def findAuthUser(email):
    """Return AuthorizedUser for `email` or None if not found."""
    user = users.User(email)
    auth_user =  AuthorizedUser.gql("where user = :1", user).get()
    logging.debug("findAuthUser(%r) = %s" % (email, auth_user))
    return auth_user
    
