"""
Taken from 
  http://appengine-cookbook.appspot.com/recipe/restrict-application-to-an-authorized-set-of-users/
"""
import os

from flask import Flask, render_template, request, redirect
from btfs.auth import AuthorizedUser, findAuthUser, users
from functools import wraps
import logging


app = Flask(__name__)
app.debug = True


def authorize(access):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if access == 'admin':
                if not users.is_current_user_admin():
                    output = "You need to login as administrator <a href='%s'>Login</a>" % users.create_login_url(request.url)
                    return output
                    #return redirect(users.create_login_url(request.url))
            elif access in ('auth', 'read', 'write'):
                # get this from request.remote_user, request.authorization or request.environ
                # if we already retrieved this in a decorator
                user = users.get_current_user()
                if not user:
                    return redirect(users.create_login_url(request.url))
                auth_user = AuthorizedUser.gql("where user = :1", user).get()
                if not auth_user:
                    output = "You need to login as authorized user <a href='%s'>Logout</a>" % users.create_logout_url(request.url)
                    return output
                    #return redirect(users.create_logout_url(request.url))
                #request.remote_user = auth_user  # read-only property
                request.environ['AUTH_USER'] = auth_user
            elif access == 'user':
                user = users.get_current_user()
                if not user:
                    return redirect(users.create_login_url(request.url))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.route('/auth/users')
@authorize('admin')
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
@authorize('admin')
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
@authorize('admin')
def user_delete():
    """Delete an authorized user from the datastore."""
    email = request.args['email']
    if not email:
        return redirect('/auth/users?invalid')
    user = users.User(email)
    auth_user = AuthorizedUser.gql("where user = :1", user).get()
    auth_user.delete()
    return redirect('/auth/users?deleted')


@app.route('/auth/')
@authorize('auth')
def user_home():
    # get this from request.remote_user, request.authorization or request.environ
    # if we already retrieved this in a decorator
    if 'AUTH_USER' not in request.environ:
        user = users.get_current_user()
        request.environ['AUTH_USER'] = AuthorizedUser.gql("where user = :1", user).get()
    auth_user = request.environ['AUTH_USER']
    access = 'read'
    if auth_user.canWrite:
        access = 'write'
    return 'Welcome %s, you are an authenticated user with %s access.' % (auth_user.user.nickname(), access)


@app.route('/auth/login', methods=['GET', 'POST'])
def user_login():
    return '(TODO) Hello'


@app.route('/auth/logout', methods=['GET', 'POST'])
def user_logout():
    return '(TODO) Goodbye'

