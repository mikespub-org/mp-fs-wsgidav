"""
Taken from 
  http://appengine-cookbook.appspot.com/recipe/restrict-application-to-an-authorized-set-of-users/
"""
import os

from flask import Flask, render_template, request, redirect
from google.appengine.ext import db
from google.appengine.api import users
import logging

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
    

app = Flask(__name__)
app.debug = True


class AuthorizedRequestHandler(object):
    """Authenticate users against a stored list of authorized users. - TO BE ADAPTED

    Base your request handler on this class and check the authorize() method
    for a True response before processing in get(), post(), etc. methods.

    For example:

    class Test(AuthorizedRequestHandler):
        def get(self):
            if self.authorize():
                return 'You are an authenticated user.'
    """

    def authorize(self):
        """Return True if user is authenticated."""
        user = users.get_current_user()
        if not user:
            self.not_logged_in()
        else:
            auth_user = AuthorizedUser.gql("where user = :1", user).get()
            if not auth_user:
                self.unauthorized_user()
            else:
                return True

    def not_logged_in(self):
        """Action taken when user is not logged in (default: go to login screen)."""
        return redirect(users.create_login_url(request.url))

    def unauthorized_user(self):
        """Action taken for unauthenticated  user (default: go to error page)."""
        return """
            <html>
              <body>
                <div>Unauthorized User</div>
                <div><a href="%s">Logout</a>
              </body>
            </html>""" % users.create_logout_url(request.url)


@app.route('/auth/users')
def auth_users():
    """Manage list of authorized users through web page.

    The GET method shows page with current list of users and allows
    deleting user or adding a new user by email address.
    """
    template_values = {
        'authorized_users': AuthorizedUser.all()
    }
    return render_template('auth.html', **template_values)


@app.route('/auth/useradd', methods=['POST'])
def user_add():
    """Manage list of authorized users through web page.

    The POST method handles adding a new user.
    """
    email = request.form['email']
    if not email:
        return redirect('/auth/users?invalid')
    user = users.User(email)
    auth_user = AuthorizedUser()
    auth_user.user = user
    if request.form.get('write'):
        auth_user.canWrite = True
    else:
        auth_user.canWrite = False
    auth_user.put()
    return redirect('/auth/users?updated')


@app.route('/auth/userdelete', methods=['GET'])
def user_delete():
    """Delete an authorized user from the datastore."""
    email = request.args['email']
    if not email:
        return redirect('/auth/users?invalid')
    user = users.User(email)
    auth_user = AuthorizedUser.gql("where user = :1", user).get()
    auth_user.delete()
    return redirect('/auth/users?deleted')

