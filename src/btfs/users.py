#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""The User Python datastore class to be used as a datastore data type."""
import os

# from past.builtins import cmp

# TODO: make configurable
AUTH_URL = "/auth/"
LOGIN_URL = AUTH_URL + "login"
LOGOUT_URL = AUTH_URL + "logout"


class Error(Exception):
    """Base User error type."""


class UserNotFoundError(Error):
    """No email argument was specified, and no user is logged in."""


class User:
    """Provides the email address, nickname, and ID for a user.

    A nickname is a human-readable string that uniquely identifies a Google user,
    akin to a username. For some users, this nickname is an email address, but for
    other users, a different nickname is used.

    A user is a Google Accounts user.
    """

    __user_id = None

    def __init__(self, email=None, _auth_domain=None, _user_id=None, _strict_mode=True):
        """Constructor.

        Args:
          email: An optional string of the user's email address. It defaults to
              the current user's email address.

        Raises:
          UserNotFoundError: If the user is not logged in and `email` is empty
        """

        if _auth_domain is None:
            _auth_domain = os.environ.get("AUTH_DOMAIN")
        if _auth_domain is None:
            _auth_domain = "gmail.com"
        # assert _auth_domain

        if email is None:
            email = os.environ.get("USER_EMAIL", email)
            _user_id = os.environ.get("USER_ID", _user_id)

        if email is None:
            email = ""

        if not email and _strict_mode:
            raise UserNotFoundError

        self.__email = email
        self.__auth_domain = _auth_domain
        self.__user_id = _user_id or None

    def nickname(self):
        """Returns the user's nickname.

        The nickname will be a unique, human readable identifier for this user with
        respect to this application. It will be an email address for some users,
        and part of the email address for some users.

        Returns:
          The nickname of the user as a string.
        """
        if (
            self.__email
            and self.__auth_domain
            and self.__email.endswith("@" + self.__auth_domain)
        ):
            suffix_len = len(self.__auth_domain) + 1
            return self.__email[:-suffix_len]
        else:
            return self.__email

    def email(self):
        """Returns the user's email address."""
        return self.__email

    def user_id(self):
        """Obtains the user ID of the user.

        Returns:
          A permanent unique identifying string or `None`. If the email address was
          set explicitly, this will return `None`.
        """
        return self.__user_id

    def auth_domain(self):
        """Obtains the user's authentication domain.

        Returns:
          A string containing the authentication domain. This method is internal and
          should not be used by client applications.
        """
        return self.__auth_domain

    def to_dict(self):
        return {
            "email": self.email(),
            "auth_domain": self.auth_domain(),
            "user_id": self.user_id(),
            "nickname": self.nickname(),
        }

    def __str__(self):
        return str(self.nickname())

    def __repr__(self):
        values = []
        if self.__email:
            values.append("email='%s'" % self.__email)
        if self.__user_id:
            values.append("_user_id='%s'" % self.__user_id)
        return "users.User(%s)" % ",".join(values)

    def __hash__(self):
        return hash((self.__email, self.__auth_domain))

    def __cmp__(self, other):
        if not isinstance(other, User):
            return NotImplemented
        cmp = lambda x, y: (x > y) - (x < y)
        return cmp(
            (self.__email, self.__auth_domain), (other.__email, other.__auth_domain)
        )


def create_login_url(dest_url=None, _auth_domain=None):
    """Computes the login URL for redirection.

    Args:
      dest_url: String that is the desired final destination URL for the user
          once login is complete. If `dest_url` does not specify a host, the host
          from the current request is used.

    Returns:
         Login URL as a string. The login URL will use Google Accounts.
    """
    if dest_url:
        return LOGIN_URL + "?continue=%s" % dest_url
    return LOGIN_URL


def create_logout_url(dest_url, _auth_domain=None):
    """Computes the logout URL and specified destination URL for the request.

    This function works for Google Accounts applications.

    Args:
      dest_url: String that is the desired final destination URL for the user
          after the user has logged out. If `dest_url` does not specify a host,
          the host from the current request is used.

    Returns:
      Logout URL as a string.
    """
    if dest_url:
        return LOGOUT_URL + "?continue=%s" % dest_url
    return LOGOUT_URL


def get_current_user():
    """Retrieves information associated with the user that is making a request.

    Returns:

    """
    try:
        return User()
    except UserNotFoundError:
        return None


def is_current_user_admin():
    """Specifies whether the user making a request is an application admin.

    Because administrator status is not persisted in the datastore,
    `is_current_user_admin()` is a separate function rather than a member function
    of the `User` class. The status only exists for the user making the current
    request.

    Returns:
      `True` if the user is an administrator; all other user types return `False`.
    """
    return os.environ.get("USER_IS_ADMIN", "0") == "1"
