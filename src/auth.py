import logging
import os
from functools import wraps

from flask import Flask, make_response, redirect, render_template, request

from btfs import sessions
from btfs.auth import AuthorizedUser, find_auth_user

app = Flask(__name__)
app.debug = True


def authorize(access):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            session = sessions.get_current_session(request.environ)
            if session.has_role("admin"):
                return f(*args, **kwargs)
            if access == "admin":
                output = (
                    "You need to login as administrator <a href='%s'>Login</a>"
                    % sessions.LOGIN_URL
                )
                return output
                # return redirect(users.create_login_url(request.url))
            # if we already retrieved this in a decorator
            if not session.is_user() and access in ("browser", "reader", "editor"):
                output = (
                    "You need to login as user <a href='%s'>Login</a>"
                    % sessions.LOGIN_URL
                )
                return output
                # return redirect(users.create_login_url(request.url))
            if access in ("reader", "editor"):
                if access == "editor" and "editor" not in session.get_roles():
                    output = (
                        "You need to login as editor <a href='%s'>Logout</a>"
                        % sessions.LOGOUT_URL
                    )
                    return output
            return f(*args, **kwargs)

        return decorated_function

    return decorator


@app.route("/auth/users")
@authorize("admin")
def auth_users():
    """Manage list of authorized users through web page.

    The GET method shows page with current list of users and allows
    deleting user or adding a new user by email address.
    """
    template_values = {"authorized_users": AuthorizedUser.list_all()}
    return render_template("auth_users.html", **template_values)


@app.route("/auth/useradd", methods=["POST"])
@authorize("admin")
def user_add():
    """Manage list of authorized users through web page.

    The POST method handles adding a new user.
    """
    email = request.form["email"]
    if not email:
        return redirect("/auth/users?invalid")
    auth_user = AuthorizedUser()
    auth_user.email = email.lower()
    auth_user.nickname = email.split("@")[0]
    # auth_user.user = user.to_dict()
    if request.form.get("roles"):
        auth_user.roles = request.form.get("roles")
        if "admin" in auth_user.roles.split(",") or "editor" in auth_user.roles.split(
            ","
        ):
            auth_user.canWrite = True
        else:
            auth_user.canWrite = False
    elif request.form.get("write"):
        auth_user.roles = "editor"
        auth_user.canWrite = True
    else:
        auth_user.roles = "reader"
        auth_user.canWrite = False
    auth_user.claims = None
    auth_user.put()
    return redirect("/auth/users?updated")


@app.route("/auth/userdelete", methods=["GET"])
@authorize("admin")
def user_delete():
    """Delete an authorized user from the datastore."""
    email = request.args["email"]
    if not email:
        return redirect("/auth/users?invalid")
    auth_user = find_auth_user(email)
    if auth_user and auth_user.email == email.lower():
        auth_user.delete()
    else:
        logging.error("Invalid user to delete: %s" % auth_user)
    return redirect("/auth/users?deleted")


# See also session cookies at https://firebase.google.com/docs/auth/admin/manage-cookies
@app.route("/auth/")
def user_home():
    # if we already retrieved this in users or a decorator
    session = sessions.get_current_session(request.environ)
    access = "read"
    if session.has_access("write"):
        access = "write"
    resp = make_response(
        render_template(
            "auth_home.html",
            auth_user=session,
            user_claims=session.claims,
            login_url=sessions.LOGIN_URL,
            logout_url=sessions.LOGOUT_URL,
            access=access,
        )
    )
    # set persistent session cookie corresponding to the id_token
    key = sessions.get_cookie_name("session_id")
    value = session.session_id
    max_age = (
        sessions.EXPIRE_DAYS * 24 * 60 * 60
    )  # set to EXPIRE_DAYS days here (id_token expires in 1 hour)
    resp.set_cookie(key, value, max_age=max_age, path="/")
    key = sessions.get_cookie_name("id_token")
    resp.set_cookie(key, "", max_age=None, path="/")
    return resp


@app.route("/auth/nologin", methods=["GET", "POST"])
def user_login():
    return redirect(sessions.AUTH_URL + "?hello")


@app.route("/auth/logout", methods=["GET", "POST"])
def user_logout():
    session = sessions.get_current_session(request.environ)
    if session.is_user():
        session.delete()
    return redirect(sessions.AUTH_URL + "?goodbye")


@app.route("/auth/login", methods=["GET", "POST"])
@app.route("/auth/token", methods=["GET", "POST"])
def user_token():
    # if we already retrieved this in users or a decorator
    session = sessions.get_current_session(request.environ)
    error_message = request.environ.get("ID_TOKEN_ERROR")

    return render_template(
        "auth_token.html",
        user_claims=session.claims,
        error_message=error_message,
        auth_url=sessions.AUTH_URL,
        logout_url=sessions.LOGOUT_URL,
        FIREBASE_PROJECT_ID=os.environ.get("FIREBASE_PROJECT_ID", "MY_PROJECT_ID"),
        FIREBASE_API_KEY=os.environ.get("FIREBASE_API_KEY", "MY_API_KEY"),
        FIREBASE_ID_TOKEN=sessions.get_cookie_name("id_token"),
    )
