#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

import logging
import time

from flask import Flask, render_template, request

from . import db
from . import api


BASE_URL = "/fire"


def create_app(debug=True, base_url="/fire", templates="../templates"):
    """Create main Flask app if this module is the entrypoint, e.g. python3 -m fire.views"""
    app = Flask(__name__)
    app.debug = debug
    app.template_folder = templates
    configure_app(app, base_url=base_url)
    return app


# app = create_app()


def configure_app(app, base_url="/fire", authorize_wrap=None):
    """Configure existing Flask app with firestore view functions, template filters and global functions"""
    global BASE_URL
    BASE_URL = base_url
    if authorize_wrap:
        app.add_url_rule(base_url + "/", view_func=authorize_wrap(home_view))
        app.add_url_rule(
            base_url + "/<string:name>/", view_func=authorize_wrap(list_view)
        )
        app.add_url_rule(
            base_url + "/<string:parent>/<path:item>",
            view_func=authorize_wrap(item_view),
        )
    else:
        app.add_url_rule(base_url + "/", view_func=home_view)
        app.add_url_rule(base_url + "/<string:name>/", view_func=list_view)
        app.add_url_rule(base_url + "/<string:parent>/<path:item>", view_func=item_view)
    app.add_template_filter(is_item)
    app.add_template_filter(item_link)
    app.add_template_filter(show_date)
    app.add_template_global(get_pager)
    # app.add_template_global(get_lists)
    # app.add_template_global(get_stats)


# @app.template_filter()
def is_item(ref):
    if "Reference" in ref.__class__.__name__:
        return True
    return False


# @app.template_filter()
def item_link(ref):
    if not is_item(ref):
        return ref
    # subcollections always end with / - see item_to_path and templates/fire_item.html
    return api.item_to_path(ref)


# @app.template_filter()
def show_date(timestamp, fmt="%Y-%m-%d %H:%M:%S"):
    if not timestamp:
        return
    if isinstance(timestamp, (int, float)):
        return time.strftime(fmt, time.gmtime(timestamp))
    return timestamp.strftime(fmt)


# @app.template_global()
def get_pager(count=None, page=1, size=None):
    if size is None:
        size = api.PAGE_SIZE
    if count is not None and count <= size:
        return
    first_url = None
    prev_url = None
    next_url = None
    last_url = None
    url = request.url
    # undo URL encoding for filter params, mainly for cosmetic reasons
    if "filters" in url:
        url = url.replace("%5B", "[").replace("%5D", "]").replace("%2F", "/")
    if "page=" in url:
        page_url = url.replace("page=%s" % page, "page=")
        if "&page=" in page_url:
            base_url = page_url.replace("&page=", "")
        else:
            base_url = page_url.replace("?page=", "")
    elif "?" in url:
        base_url = url
        page_url = url + "&page="
    else:
        base_url = url
        page_url = url + "?page="
    if page > 1:
        first_url = base_url
    if page > 2:
        prev_url = page_url + str(page - 1)
    elif page > 1:
        prev_url = base_url
    if count is None:
        next_url = page_url + str(page + 1)
        return (first_url, prev_url, next_url, last_url)
    max_page = int(count / size) + 1
    if page < max_page:
        next_url = page_url + str(page + 1)
        last_url = page_url + str(max_page)
    return (first_url, prev_url, next_url, last_url)


# @app.route("/fire/")
# @sessions.flask_authorize("admin")
def home_view():
    reset = request.args.get("reset", False)
    stats = api.get_stats(reset)
    return render_template(
        "fire_home.html",
        base_url=BASE_URL,
        lists=api.get_lists(),
        name=None,
        stats=stats,
    )


# @app.route("/fire/<string:name>/")
# @sessions.flask_authorize("admin")
def list_view(name):
    # when dealing with subcollections coming from item_view
    if name.split("/")[0] not in api.get_lists():
        return home_view()
    sort = request.args.get("sort", None)
    page = int(request.args.get("page", 1))
    fields = request.args.get("fields", None)
    # filters = request.args.get("filters", None)
    filters = api.parse_filter_args(request.args, name)
    if page < 1:
        page = 1
    count = api.get_list_count(name)
    columns = []
    if filters is not None:
        rows = api.list_get(name, page, sort, fields, filters=filters)
    else:
        rows = api.list_get(name, page, sort, fields)
    if len(rows) > 0:
        columns = sorted(rows[0].keys())
        if len(rows) < api.PAGE_SIZE:
            count = len(rows) + (page - 1) * api.PAGE_SIZE
            if count is None and filters is None:
                api.set_list_count(name, count)
        elif filters is not None:
            count = None
    # TODO: can we get rid of this too?
    coll_ref = db.get_coll_ref(name)
    parent = coll_ref.parent
    return render_template(
        "fire_list.html",
        base_url=BASE_URL,
        lists=api.get_lists(),
        name=name,
        sort=sort,
        page=page,
        count=count,
        columns=columns,
        rows=rows,
        parent=parent,
        filters=filters,
    )


# @app.route("/fire/<string:parent>/<path:item>")
# @sessions.flask_authorize("admin")
def item_view(parent, item):
    if parent not in api.get_lists():
        return home_view()
    # subcollections always end with / - see item_to_path and templates/fire_item.html
    if item.endswith("/"):
        parent += "/" + item[:-1]
        return list_view(parent)
    image_list = []
    # extract coll_id from item if needed: parent main_doc/sub_coll/sub_doc -> sub_coll
    if "/" in item:
        coll_id = item.split("/")[-2]
    else:
        coll_id = parent
    if coll_id in api.COLL_CONFIG and api.COLL_CONFIG[coll_id].get("image", None):
        image_list = api.COLL_CONFIG[coll_id].get("image", [])
    # if we only select an image field, show the image
    fields = request.args.get("fields", None)
    if fields and fields in image_list:
        return image_view(parent, item, fields)
    # if ";" in item:
    #     for attr in image_list:
    #         if item.endswith(";%s" % attr):
    #             return image_view(parent, item.replace(";%s" % attr), attr)
    children = request.args.get("children", True)
    unpickle = request.args.get("unpickle", True)
    info = api.item_get(
        parent, item, fields=fields, children=children, unpickle=unpickle
    )
    for attr in image_list:
        info[attr] = "?fields=%s" % attr
    return render_template(
        "fire_item.html",
        base_url=BASE_URL,
        lists=api.get_lists(),
        name=parent,
        info=info,
    )


def image_view(parent, item, attr):
    fields = [attr]
    children = False
    unpickle = False
    info = api.item_get(
        parent, item, fields=fields, children=children, unpickle=unpickle
    )
    return info[attr], 200, {"Content-Type": "image/png"}


if __name__ == "__main__":
    # python3 -m fire.views
    app = create_app()
    app.run(host="0.0.0.0", port=8080, use_reloader=False)
