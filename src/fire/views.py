#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

import logging
import time

from flask import Flask, render_template, request

from . import db


FIRE_URL = "/fire"
PAGE_SIZE = 10
COLLS_LIST = []


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
    global FIRE_URL
    FIRE_URL = base_url
    if authorize_wrap:
        app.add_url_rule(base_url + "/", view_func=authorize_wrap(fire_home_view))
        app.add_url_rule(
            base_url + "/<string:coll>/", view_func=authorize_wrap(fire_coll_view)
        )
        app.add_url_rule(
            base_url + "/<string:coll>/<path:ref>",
            view_func=authorize_wrap(fire_doc_view),
        )
    else:
        app.add_url_rule(base_url + "/", view_func=fire_home_view)
        app.add_url_rule(base_url + "/<string:coll>/", view_func=fire_coll_view)
        app.add_url_rule(
            base_url + "/<string:coll>/<path:ref>", view_func=fire_doc_view
        )
    app.add_template_filter(is_ref)
    app.add_template_filter(ref_link)
    app.add_template_filter(show_date)
    app.add_template_global(get_pager)
    # app.add_template_global(get_colls)
    # app.add_template_global(get_stats)


# @app.template_filter()
def is_ref(ref):
    if "Reference" in ref.__class__.__name__:
        return True
    return False


# @app.template_filter()
def ref_link(ref):
    if not is_ref(ref):
        return ref
    # doc_ref
    if hasattr(ref, "path"):
        return ref.path
    # coll_ref - collection urls always end with / here
    if ref.parent:
        return "%s/%s/" % (ref.parent.path, ref.id)
    return "%s/" % ref.id


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
        size = PAGE_SIZE
    if count is not None and count <= size:
        return
    first_url = None
    prev_url = None
    next_url = None
    last_url = None
    url = request.url
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


def get_colls(reset=False):
    global COLLS_LIST
    if len(COLLS_LIST) > 0 and not reset:
        return COLLS_LIST
    firestore_colls = []
    for coll_ref in db.list_root():
        firestore_colls.append(coll_ref.id)
    COLLS_LIST = sorted(firestore_colls)
    return COLLS_LIST


firestore_stats = {}


def get_stats(reset=False):
    global firestore_stats
    if len(firestore_stats) > 0 and not reset:
        return firestore_stats
    firestore_stats = {}
    firestore_stats["Stats"] = {"timestamp": time.time()}
    for coll_ref in db.list_root():
        firestore_stats[coll_ref.id] = get_coll_stats(coll_ref)
    return firestore_stats


def get_coll_stats(coll_ref, limit=1000):
    # count only on demand now
    # count = len(list(coll_ref.list_documents()))
    count = None
    stats = {
        "coll_ref": coll_ref,
        # "properties": {},
        "count": count,
    }
    if stats["count"] == limit:
        stats["count"] = str(limit) + "+"
    return stats


def get_coll_count(coll, reset=False):
    global firestore_stats
    if (
        coll in firestore_stats
        and firestore_stats[coll]["count"] is not None
        and not reset
    ):
        return firestore_stats[coll]["count"]
    if coll not in get_colls():
        return
    if coll not in firestore_stats:
        coll_ref = db.get_coll_ref(coll)
        firestore_stats[coll] = get_coll_stats(coll_ref)
    else:
        coll_ref = firestore_stats[coll]["coll_ref"]
    count = 0
    for doc_ref in coll_ref.list_documents():
        count += 1
    firestore_stats[coll]["count"] = count
    return firestore_stats[coll]["count"]


# @app.route("/fire/")
# @sessions.flask_authorize("admin")
def fire_home_view():
    reset = request.args.get("reset", False)
    stats = get_stats(reset)
    return render_template(
        "fire_view.html", fire_url=FIRE_URL, colls=get_colls(), coll=None, stats=stats,
    )


# @app.route("/fire/<string:coll>/")
# @sessions.flask_authorize("admin")
def fire_coll_view(coll):
    # when dealing with subcollections coming from fire_doc_view
    if coll.split("/")[0] not in get_colls():
        return fire_home_view()
    sort = request.args.get("sort", None)
    page = int(request.args.get("page", 1))
    if page < 1:
        page = 1
    count = get_coll_count(coll)
    limit = PAGE_SIZE
    offset = (page - 1) * limit
    columns = []
    rows = []
    coll_ref = db.get_coll_ref(coll)
    parent = coll_ref.parent
    # for doc in db.ilist_entities(coll, limit, offset, **kwargs):
    query = coll_ref.limit(limit).offset(offset)
    if sort:
        if sort.startswith("-"):
            query = query.order_by(sort[1:], direction="DESCENDING")
        else:
            query = query.order_by(sort)
    for doc in query.stream():
        info = doc.to_dict()
        if hasattr(doc, "create_time") and doc.create_time:
            doc.create_time = doc.create_time.seconds + float(
                doc.create_time.nanos / 1000000000.0
            )
        if hasattr(doc, "update_time") and doc.update_time:
            doc.update_time = doc.update_time.seconds + float(
                doc.update_time.nanos / 1000000000.0
            )
        if hasattr(doc, "read_time") and doc.read_time:
            doc.read_time = doc.read_time.seconds + float(
                doc.read_time.nanos / 1000000000.0
            )
        info.update(doc.__dict__)
        del info["_data"]
        if len(columns) < 1:
            columns = sorted(info.keys())
        if (
            "data" in info
            and isinstance(info["data"], bytes)
            and len(info["data"]) > 20
        ):
            info["data"] = "%s... (%s bytes)" % (info["data"][:20], len(info["data"]))
        rows.append(info)
    return render_template(
        "fire_coll.html",
        fire_url=FIRE_URL,
        colls=get_colls(),
        coll=coll,
        sort=sort,
        page=page,
        count=count,
        columns=columns,
        rows=rows,
        parent=parent,
    )


# @app.route("/fire/<string:coll>/<path:ref>")
# @sessions.flask_authorize("admin")
def fire_doc_view(coll, ref):
    if coll not in get_colls():
        return fire_home_view()
    # subcollections always end with / - see ref_link and templates/fire_doc.html
    if ref.endswith("/"):
        coll += "/" + ref[:-1]
        return fire_coll_view(coll)
    coll_ref = db.get_coll_ref(coll)
    doc_ref = coll_ref.document(ref)
    doc = doc_ref.get()
    subcolls = []
    for subcoll_ref in doc_ref.collections():
        subcolls.append(subcoll_ref.id)
    parent = None
    info = doc.to_dict()
    if hasattr(doc, "create_time") and doc.create_time:
        doc.create_time = doc.create_time.seconds + float(
            doc.create_time.nanos / 1000000000.0
        )
    if hasattr(doc, "update_time") and doc.update_time:
        doc.update_time = doc.update_time.seconds + float(
            doc.update_time.nanos / 1000000000.0
        )
    if hasattr(doc, "read_time") and doc.read_time:
        doc.read_time = doc.read_time.seconds + float(
            doc.read_time.nanos / 1000000000.0
        )
    info.update(doc.__dict__)
    del info["_data"]
    if doc.reference.parent:
        parent = doc.reference.parent
    return render_template(
        "fire_doc.html",
        fire_url=FIRE_URL,
        colls=get_colls(),
        coll=coll,
        ref=doc_ref,
        info=info,
        subcolls=subcolls,
        parent=parent,
    )


if __name__ == "__main__":
    # python3 -m fire.views
    app = create_app()
    app.run(host="0.0.0.0", port=8080, use_reloader=False)
