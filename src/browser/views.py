#!/usr/bin/env python3
import os.path
import time
from flask import Flask, render_template, request, redirect, send_file, abort
from . import DispatchPath, guess_mime_type

BASE_URL = ""


def create_app(debug=True, base_url="", templates="../templates"):
    """Create main Flask app if this module is the entrypoint, e.g. python3 -m browser.views"""
    app = Flask(__name__)
    app.debug = debug
    app.template_folder = templates
    # configure app with generic /zip_files URLs by default here!?
    if not base_url:
        base_url = BASE_URL
    configure_app(app, base_url=base_url)
    # authorize_wrap = flask_authorize("admin")  # if one role for all view_funcs
    # configure_app(app, base_url=base_url, authorize_wrap=authorize_wrap)
    return app


def configure_app(app, base_url="", authorize_wrap=None):
    """Configure existing Flask app with zip_files view functions, template filters and global functions"""
    global BASE_URL
    BASE_URL = base_url
    if authorize_wrap:
        # app.add_url_rule(base_url + "/", view_func=home)
        app.add_url_rule(
            base_url + "/", view_func=authorize_wrap(home)
        )  # if one role for all view_funcs
        # app.add_url_rule(base_url + "/", view_func=authorize_role("user", home))
        app.add_url_rule(
            base_url + "/<string:fstype>/",
            "fstype_content",
            view_func=authorize_wrap(content)
            # base_url + "/<string:fstype>/", view_func=authorize_role("admin", content)
        )
        app.add_url_rule(
            base_url + "/<string:fstype>/<path:more>",
            "more_content",
            view_func=authorize_wrap(content),
            # view_func=authorize_role("admin", content),
        )
    else:
        app.add_url_rule(base_url + "/", view_func=home)
        app.add_url_rule(base_url + "/<string:fstype>/", view_func=content)
        app.add_url_rule(base_url + "/<string:fstype>/<path:more>", view_func=content)
    app.add_template_filter(show_date)
    # app.add_template_global(get_pager)


# @app.template_filter()
def show_date(timestamp, fmt="%Y-%m-%d %H:%M:%S"):
    if not timestamp:
        return
    if isinstance(timestamp, (int, float)):
        return time.strftime(fmt, time.gmtime(timestamp))
    return timestamp.strftime(fmt)


# app = Flask(__name__)
dispatch = DispatchPath()


# @app.route("/")
def home():
    files = dispatch.roots()
    label = "User"
    link = "/user"
    return render_template(
        "browser.html",
        base_url=BASE_URL,
        files=files,
        label=label,
        link=link,
        path=None,
    )


# @app.route("/<string:fstype>/")
# @app.route("/<string:fstype>/<path:more>")
# @flask_authorize("admin")  # CHECKME: different user access for different routes? See above in configure_app
def content(fstype, more=None):
    # if more:
    #     return send_content(zipname, more)
    if fstype == "favicon.ico":
        abort(404)
        return
    sortkey = request.args.get("sort", "name")
    path = fstype + "/"
    if more:
        path += more
    start_time = time.time()
    files = dispatch.list_files(path, sortkey)
    stop_time = time.time()
    if not files:
        abort(404)
        return
    label = "Logout"
    link = "/user"
    if more is not None:
        path = "%s/%s" % (fstype, more)
    else:
        path = fstype
    if path.endswith("/"):
        path = path[:-1]
    return render_template(
        "browser.html",
        base_url=BASE_URL,
        files=files,
        label=label,
        link=link,
        path=path,
        elapsed="%.3f" % (stop_time - start_time),
        filesystem=repr(dispatch.filesystem()),
    )


def send_content(zipname, more, filepath=None):
    # flask.send_file(filename_or_fp, mimetype=None, as_attachment=False, attachment_filename=None, add_etags=True, cache_timeout=None, conditional=False, last_modified=None)
    fp = get_zip_fp(zipname, more, filepath)
    if fp:
        # import mimetypes

        filename = os.path.basename(more)
        # (mimetype, encoding) = mimetypes.guess_type(filename)
        mimetype = guess_mime_type(filename)
        if mimetype is not None and mimetype[0:5] == "image":
            return send_file(fp, mimetype=mimetype)
        mimetype = "text/plain"
        return send_file(fp, mimetype=mimetype)
        # return send_file(fp, attachment_filename=filename)
    abort(404)
    return


app = create_app()


def profiler(app):
    from werkzeug.contrib.profiler import ProfilerMiddleware

    app.config["PROFILE"] = True
    # app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30])
    app.wsgi_app = ProfilerMiddleware(
        app.wsgi_app, sort_by=["cumtime", "calls"], restrictions=[30]
    )


def lineprof(app):
    from wsgi_lineprof.middleware import LineProfilerMiddleware
    from wsgi_lineprof.filters import FilenameFilter, TotalTimeSorter, TopItemsFilter

    filters = [
        # Results which filename contains "mikeswebdav"
        FilenameFilter("mikeswebdav"),
        # Sort by total time of results
        TotalTimeSorter(),
        # Get first n stats
        TopItemsFilter(),
    ]
    app.wsgi_app = LineProfilerMiddleware(app.wsgi_app, filters=filters)


if __name__ == "__main__":
    # python3 -m browser.views
    # app = create_app()
    # profiler(app)
    # lineprof(app)
    app.run(host="0.0.0.0", port=8080, use_reloader=False)
