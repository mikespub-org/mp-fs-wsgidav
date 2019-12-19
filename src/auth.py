"""
Taken from 
  http://appengine-cookbook.appspot.com/recipe/restrict-application-to-an-authorized-set-of-users/
"""
import os

from flask import Flask, render_template, request, redirect
from btfs.auth import AuthorizedUser, find_auth_user, users
from btfs.auth import get_id_token, get_user_claims
from functools import wraps
import logging


app = Flask(__name__)
app.debug = True


def check_auth_user():
    # get this from request.remote_user, request.authorization or request.environ
    # if we already retrieved this in users or a decorator
    if 'AUTH_USER' not in request.environ:
        user = users.get_current_user()
        auth_user = AuthorizedUser.get_by_user(user)
        if auth_user:
            request.environ['AUTH_USER'] = auth_user.to_dict()
        else:
            request.environ['AUTH_USER'] = {}
        if request.environ['AUTH_USER'].get('claims'):
            request.environ['USER_CLAIMS'] = request.environ['AUTH_USER'].get('claims')
        #request.remote_user = auth_user  # read-only property
    auth_user = request.environ.get('AUTH_USER')
    if 'USER_CLAIMS' not in request.environ:
        id_token = get_id_token(request)
        claims, error_message = get_user_claims(id_token)
        request.environ['USER_CLAIMS'] = claims
        request.environ['USER_ERROR'] = error_message
        #if auth_user and claims:
        # TODO: update auth_user
    user_claims = request.environ.get('USER_CLAIMS')
    return auth_user, user_claims


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
            # if we already retrieved this in a decorator
            user = users.get_current_user()
            if not user and access in ('user', 'reader', 'editor'):
                output = "You need to login as user <a href='%s'>Login</a>" % users.create_login_url(request.url)
                return output
                #return redirect(users.create_login_url(request.url))
            if access in ('reader', 'editor'):
                auth_user, user_claims = check_auth_user()
                if not auth_user:
                    output = "You need to login as authorized user <a href='%s'>Logout</a>" % users.create_logout_url(request.url)
                    return output
                    #return redirect(users.create_logout_url(request.url))
                if access == 'editor' and 'editor' not in auth_user.get('roles', '').split(','):
                    output = "You need to login as editor <a href='%s'>Logout</a>" % users.create_logout_url(request.url)
                    return output
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
    return render_template('auth_users.html', **template_values)


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
    if request.form.get('roles'):
        auth_user.roles = request.form.get('roles')
        if 'admin' in auth_user.roles.split(',') or 'editor' in auth_user.roles.split(','):
            auth_user.canWrite = True
        else:
            auth_user.canWrite = False
    elif request.form.get('write'):
        auth_user.roles = 'editor'
        auth_user.canWrite = True
    else:
        auth_user.roles = 'reader'
        auth_user.canWrite = False
    auth_user.claims = None
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


# See also session cookies at https://firebase.google.com/docs/auth/admin/manage-cookies
@app.route('/auth/')
@authorize('reader')
def user_home():
    # if we already retrieved this in users or a decorator
    auth_user, user_claims = check_auth_user()
    access = 'read'
    if auth_user and auth_user.get('canWrite'):
        access = 'write'
    return render_template(
        'auth_home.html',
        auth_user=auth_user,
        user_claims=user_claims,
        access=access)


@app.route('/auth/login', methods=['GET', 'POST'])
def user_login():
    return '(TODO) Hello'


@app.route('/auth/logout', methods=['GET', 'POST'])
def user_logout():
    return '(TODO) Goodbye'


@app.route('/auth/token', methods=['GET', 'POST'])
def user_token():
    # if we already retrieved this in users or a decorator
    auth_user, user_claims = check_auth_user()
    error_message = request.environ.get('USER_ERROR')

    return render_template(
        'auth_token.html',
        user_claims=user_claims, error_message=error_message,
        FIREBASE_PROJECT_ID=request.environ['FIREBASE_PROJECT_ID'],
        FIREBASE_API_KEY=request.environ['FIREBASE_API_KEY'])

