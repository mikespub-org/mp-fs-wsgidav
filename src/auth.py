"""
Taken from 
  http://appengine-cookbook.appspot.com/recipe/restrict-application-to-an-authorized-set-of-users/
"""
import os

from flask import Flask, render_template, request, redirect
from btfs.auth import AuthorizedUser, find_auth_user, users
from functools import wraps
import logging


app = Flask(__name__)
app.debug = True


def authorize(access):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if users.is_current_user_admin():
                return f(*args, **kwargs)
            if access == 'admin':
                output = "You need to login as administrator <a href='%s'>Login</a>" % users.create_login_url(request.url)
                return output
                #return redirect(users.create_login_url(request.url))
            # get this from request.remote_user, request.authorization or request.environ
            # if we already retrieved this in a decorator
            user = users.get_current_user()
            if not user and access in ('user', 'auth', 'read', 'write'):
                output = "You need to login as user <a href='%s'>Login</a>" % users.create_login_url(request.url)
                return output
                #return redirect(users.create_login_url(request.url))
            if access in ('auth', 'read', 'write'):
                auth_user = AuthorizedUser.get_by_user(user)
                if not auth_user:
                    output = "You need to login as authorized user <a href='%s'>Logout</a>" % users.create_logout_url(request.url)
                    return output
                    #return redirect(users.create_logout_url(request.url))
                #request.remote_user = auth_user  # read-only property
                request.environ['AUTH_USER'] = auth_user
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
        'authorized_users': AuthorizedUser.list_all()
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
    auth_user.email = user.email()
    if user.auth_domain():
        auth_user.auth_domain = user.auth_domain()
    if user.user_id():
        auth_user.user_id = user.user_id()
    if user.nickname():
        auth_user.nickname = user.nickname()
    else:
        auth_user.nickname = auth_user.email.split('@')[0]
    #auth_user.user = user.to_dict()
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
    auth_user = AuthorizedUser.get_by_user(user)
    if auth_user and auth_user.email == email:
        auth_user.delete()
    else:
        logging.error('Invalid user to delete: %s' % auth_user)
    return redirect('/auth/users?deleted')


@app.route('/auth/')
@authorize('auth')
def user_home():
    # get this from request.remote_user, request.authorization or request.environ
    # if we already retrieved this in a decorator
    if 'AUTH_USER' not in request.environ:
        user = users.get_current_user()
        request.environ['AUTH_USER'] = AuthorizedUser.get_by_user(user)
    auth_user = request.environ['AUTH_USER']
    access = 'read'
    if auth_user and auth_user.canWrite:
        access = 'write'
    return 'Welcome %s, you are an authenticated user with %s access.' % (auth_user.nickname, access)


@app.route('/auth/login', methods=['GET', 'POST'])
def user_login():
    return '(TODO) Hello'


@app.route('/auth/logout', methods=['GET', 'POST'])
def user_logout():
    return '(TODO) Goodbye'

