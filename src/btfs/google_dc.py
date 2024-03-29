# (c) 2010 Martin Wendt; see CloudDAV http://clouddav.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
"""
Implementation of a domain controller that uses the Users Service of
Google App Engine.

Credentials are verified by applying this rules:

1. If '*' is in the list of configured users allow anonymous access.
2. If the current request was made by an authenticated user with
   admin permissions for this GAE application: grant write access.
   Note: this is not reliable, since a WebDAV client may not be recognized.
3. If the user name that is passed with the request is not configured in the
   'User Administration' page of this CloudDAV application: deny access.
4. Use Google's ClientLogin API to verify the the password.
5. TODO: Grant read or read/write access, depending on user configuration.

Example:
    >net use M: https://myapp.appspot.com/ /user:user@gmail.com
    >dir m:
  or pass a password
    >net use M: https://myapp.appspot.com/ /user:user@gmail.com mypassword

  When using XP:
  - we cannot use https:// in the URL (but will be redirected)
  - we must connect to a sub-folder
    >net use M: http://myapp.appspot.com/dav /user:user@gmail.com


See http://code.google.com/appengine/docs/python/users/
    http://code.google.com/apis/accounts/docs/AuthForInstalledApps.html

See `Developers info`_ for more information about the WsgiDAV architecture.

.. _`Developers info`: http://docs.wsgidav.googlecode.com/hg/html/develop.html
"""

# import http.cookiejar
import logging

# import sys
import urllib.error
import urllib.parse
import urllib.request

from wsgidav.dc.base_dc import BaseDomainController

from . import users
from .auth import find_auth_user

__docformat__ = "reStructuredText"


# ===============================================================================
# xAppAuth
# ===============================================================================
class xAppAuth:
    """
    Author: Dale Lane; Modified by 'youngfe' on this page:
    http://dalelane.co.uk/blog/?p=303
    """

    def __init__(self, user, password, appName):
        self.user = user
        self.password = password
        self.appName = appName
        self.authtoken = None
        self.lastError = (None, None, None)
        # TODO: should be a lastAccess tag, so we can force a refresh after 1 hour or so

    def getAuthtoken(self, refresh=False):
        if self.authtoken is None or refresh:
            self.lastError = (None, None, None)
            # cookiejar = http.cookiejar.LWPCookieJar()
            # opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))
            # urllib.request.install_opener(opener)
            auth_uri = "https://www.google.com/accounts/ClientLogin"
            authreq_data = urllib.parse.urlencode(
                {
                    "Email": self.user,
                    "Passwd": self.password,
                    "service": "ah",
                    "source": self.appName,
                    "accountType": "HOSTED_OR_GOOGLE",
                }
            )
            auth_req = urllib.request.Request(
                auth_uri, data=authreq_data.encode("utf-8")
            )
            try:
                auth_resp = urllib.request.urlopen(auth_req)
            except urllib.error.HTTPError as e:
                self.lastError = (e.code, e.msg, None)
                if e.code == 403:
                    # '403 Forbidden': unknown user or wrong password
                    # We still can get error details from the response body
                    logging.error(f"HTTPError {e}: {e.message!r}, {e.strerror!r}")
                    self.lastError = (e.code, e.msg, f"{e.message}/{e.strerror}")
                raise e
            auth_resp_body = auth_resp.read()
            # auth response includes several fields - we're interested in
            # the bit after Auth=
            auth_resp_dict = dict(x.split("=") for x in auth_resp_body.split("\n") if x)
            self.authtoken = auth_resp_dict["Auth"]
        return self.authtoken

    get_auth_token = getAuthtoken

    def getAuthUrl(self, Uri, AppName):
        serv_uri = Uri
        serv_args = {}
        serv_args["continue"] = serv_uri
        serv_args["auth"] = self.getAuthtoken()
        return (
            "http://"
            + AppName
            + ".appspot.com/_ah/login?%s" % urllib.parse.urlencode(serv_args)
        )

    get_auth_url = getAuthUrl

    def getAuthRequest(self, Uri, AppName):
        return urllib.request.Request(self.getAuthUrl(Uri, AppName))

    get_auth_request = getAuthRequest

    def getAuthResponse(self, Uri, AppName):
        return urllib.request.urlopen(self.getAuthRequest(Uri, AppName))

    get_auth_response = getAuthResponse

    def getAuthRead(self, Uri, AppName):
        return self.getAuthResponse(Uri, AppName).read()

    get_auth_read = getAuthRead


# ===============================================================================
# GoogleDomainController
# ===============================================================================
class GoogleDomainController(BaseDomainController):

    # def __init__(self, userMap=None):
    def __init__(self, wsgidav_app, config):
        super().__init__(wsgidav_app, config)
        # dc_conf = config.get("google_dc", {})

        # self.appName = appName
        # self.userMap = userMap

    def __repr__(self):
        return self.__class__.__name__

    def getDomainRealm(self, path_info, environ):
        """Resolve a relative url to the  appropriate realm name."""
        # we don't get the realm here, its already been resolved in request_resolver
        realm = self._calc_realm_from_path_provider(path_info, environ)
        return realm
        """
        if environ is None:
            return "/"
        davProvider = environ["wsgidav.provider"]
        if not davProvider:
            if environ["wsgidav.verbose"] >= 2:
                print("getDomainRealm(%s): '%s'" %(path_info, None), file=sys.stderr)
            return None
        realm = davProvider.sharePath
        if realm == "":
            realm = "/"
        return realm
        """

    get_domain_realm = getDomainRealm

    def requireAuthentication(self, realmname, environ):
        """Return True if this realm requires authentication or False if it is
        available for general access."""
        logging.debug(f"requireAuthentication({realmname!r})")
        # If '*' is in the list of allowed accounts, allow anonymous access
        if find_auth_user("*"):
            logging.debug("Granting access to everyone (*)")
            return False
        return True

    require_authentication = requireAuthentication

    def isRealmUser(self, realmname, username, environ):
        """Returns True if this username is valid for the realm, False otherwise.

        Used for digest authentication.
        """
        raise NotImplementedError(
            "We cannot query users without knowing the password for a Google account. Digest authentication must be disabled."
        )

    is_realm_user = isRealmUser

    def getRealmUserPassword(self, realmname, username, environ):
        """Return the password for the given username for the realm.

        Used for digest authentication.
        """
        raise NotImplementedError(
            "We cannot query the password for a Google account. Digest authentication must be disabled."
        )

    _get_realm_user_password = getRealmUserPassword

    def authDomainUser(self, realmname, username, password, environ):
        """Returns True if this username/password pair is valid for the realm,
        False otherwise.

        Used for basic authentication.
        """
        logging.debug(
            "authDomainUser({!r}, {!r}, {!r})".format(realmname, username, "***")
        )
        # headers = [ "%s: %r" % e for e in environ.items() ]
        # logging.debug("headers:\n\t" + "\n\t".join(headers))

        # If current user is logged in to Google Apps and has 'admin'
        # permission, allow access
        # Note: this is not reliable, since a WebDAV client may not be recognized.
        google_user = users.get_current_user()
        logging.debug(f"User {username} is googleapp user {google_user}")
        if users.is_current_user_admin():
            logging.debug(
                "User %s is authorized as GAE admin %s for %s"
                % (username, google_user.nickname(), environ.get("APPLICATION_ID"))
            )
            return True

        # Check if user name that was passed with the request is in the list
        # of allowed accounts
        auth_user = find_auth_user(username)
        if not auth_user:
            logging.info(f"User {username} is not configured to have access")
            return False
        logging.debug(f"User {username} is configured (canWrite: {auth_user.canWrite})")

        # Check if user name / password that was passed with the request is a
        # (globally) registered, valid account.

        # TODO: pass self.appName and check, if user has 'admin' permissions on <appName>
        # TODO: cache this info for at least 10 minutes
        user = xAppAuth(username, password, appName=environ.get("APPLICATION_ID"))
        try:
            authToken = user.getAuthtoken()
            logging.debug(f"User {username} is authorized: {authToken}")
        except urllib.error.HTTPError as _:
            logging.info(f"User {username} is not authorized: {user.lastError}")
            authToken = None
        return bool(authToken)

    auth_domain_user = authDomainUser
    basic_auth_user = authDomainUser

    def supports_http_digest_auth(self):
        # We don't have access to a plaintext password (or stored hash)
        return False
