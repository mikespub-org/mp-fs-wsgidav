#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

import logging
import time

from flask import Flask, render_template, request

from btfs import sessions
from btfs.auth import AuthorizedUser
from . import db
from .model import Chunk, Dir, File, Path


DATA_URL = "/data"
PAGE_SIZE = 10
KNOWN_MODELS = {
    "Path": Path,
    "Dir": Dir,
    "File": File,
    "Chunk": Chunk,
    "AuthorizedUser": AuthorizedUser,
    "AuthSession": sessions.AuthSession,
}
KINDS_LIST = []


def create_app(debug=True, base_url="/data", templates="../templates"):
    """Create main Flask app if this module is the entrypoint, e.g. python3 -m data.views"""
    app = Flask(__name__)
    app.debug = debug
    app.template_folder = templates
    configure_app(app, base_url=base_url)
    return app


# app = create_app()


def configure_app(app, base_url="/data", authorize_wrap=None):
    """Configure existing Flask app with datastore view functions, template filters and global functions"""
    global DATA_URL
    DATA_URL = base_url
    if authorize_wrap:
        app.add_url_rule(base_url + "/", view_func=authorize_wrap(data_home_view))
        app.add_url_rule(
            base_url + "/<string:kind>/", view_func=authorize_wrap(data_kind_view)
        )
        app.add_url_rule(
            base_url + "/<string:kind>/<path:key>",
            view_func=authorize_wrap(data_key_view),
        )
    else:
        app.add_url_rule(base_url + "/", view_func=data_home_view)
        app.add_url_rule(base_url + "/<string:kind>/", view_func=data_kind_view)
        app.add_url_rule(
            base_url + "/<string:kind>/<path:key>", view_func=data_key_view
        )
    app.add_template_filter(is_key)
    app.add_template_filter(key_link)
    app.add_template_filter(show_date)
    app.add_template_global(get_pager)
    # app.add_template_global(get_kinds)
    # app.add_template_global(get_stats)


# @app.template_filter()
def is_key(key):
    if "Key" in key.__class__.__name__:
        return True
    return False


# @app.template_filter()
def key_link(key):
    if not is_key(key):
        return key
    if key.kind in ("Path", "Dir", "File"):
        # drop the first / of the id_or_name = path
        return "%s/%s" % (key.kind, key.id_or_name[1:])
    elif key.kind in ("Chunk") and key.parent:
        # add the :parent:path
        return "%s/%s:%s:%s" % (
            key.kind,
            key.id_or_name,
            key.parent.kind,
            key.parent.id_or_name,
        )
    return "%s/%s" % (key.kind, key.id_or_name)


# @app.template_filter()
def show_date(timestamp, fmt="%Y-%m-%d %H:%M:%S"):
    if not timestamp:
        return
    return time.strftime(fmt, time.gmtime(timestamp))


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


def get_models():
    models_list = sorted(KNOWN_MODELS.keys())
    models_list.append("Others")
    return models_list


def get_kinds(reset=False):
    global KINDS_LIST
    if len(KINDS_LIST) > 0 and not reset:
        return KINDS_LIST
    KINDS_LIST = get_models()
    for kind in sorted(db.list_kinds()):
        if kind not in KINDS_LIST:
            KINDS_LIST.append(kind)
    return KINDS_LIST


datastore_stats = {}


def get_stats(reset=False):
    global datastore_stats
    if len(datastore_stats) > 0 and not reset:
        return datastore_stats
    datastore_stats = {}
    # datastore_stats['Stats'] = stats.GlobalStat.list_all(1)
    kind = "__Stat_Total__"
    id_or_name = "total_entity_usage"
    key = db.get_key(kind, id_or_name)
    entity = db.get_entity(key)
    if entity:
        info = dict(entity)
        info["__key__"] = entity.key
    else:
        info = {"timestamp": time.time()}
    datastore_stats["Stats"] = {}
    datastore_stats["Stats"]["Total"] = info
    # for stat in stats.KindPropertyNamePropertyTypeStat.list_all():
    #    datastore_stats['Stats'].append(stat)
    kind = "__Stat_PropertyType_PropertyName_Kind__"
    for entity in db.ilist_entities(kind):
        info = dict(entity)
        info["__key__"] = entity.key
        if info["kind_name"] not in datastore_stats["Stats"]:
            datastore_stats["Stats"][info["kind_name"]] = {}
        datastore_stats["Stats"][info["kind_name"]][info["property_name"]] = info
    for model in KNOWN_MODELS:
        datastore_stats[model] = get_model_stats(KNOWN_MODELS[model])
    return datastore_stats


def get_model_stats(model, limit=1000):
    # count only on demand now
    stats = {
        "kind": model.kind(),
        "properties": model.properties(),
        # "count": model.get_count(limit),
        "count": None,
    }
    if stats["count"] == limit:
        stats["count"] = str(limit) + "+"
    return stats


def get_model_count(model, reset=False):
    global datastore_stats
    if (
        model in datastore_stats
        and datastore_stats[model]["count"] is not None
        and not reset
    ):
        return datastore_stats[model]["count"]
    if model not in KNOWN_MODELS:
        return
    if model not in datastore_stats:
        datastore_stats[model] = get_model_stats(KNOWN_MODELS[model])
    datastore_stats[model]["count"] = KNOWN_MODELS[model].get_count()
    return datastore_stats[model]["count"]


# @app.route("/data/")
# @sessions.flask_authorize("admin")
def data_home_view(kind=None):
    # when dealing with Others coming from data_kind_view
    if kind == "Others":
        kinds_list = get_kinds()
    else:
        kinds_list = get_models()
    reset = request.args.get("reset", False)
    stats = get_stats(reset)
    return render_template(
        "data_view.html", data_url=DATA_URL, kinds=kinds_list, kind=kind, stats=stats,
    )


# @app.route("/data/<string:kind>/")
# @sessions.flask_authorize("admin")
def data_kind_view(kind):
    kinds_list = get_models()
    if kind not in KNOWN_MODELS:
        kinds_list = get_kinds()
        if kind not in kinds_list or kind == "Others":
            return data_home_view(kind)
    sort = request.args.get("sort", None)
    page = int(request.args.get("page", 1))
    if page < 1:
        page = 1
    count = get_model_count(kind)
    limit = PAGE_SIZE
    offset = (page - 1) * limit
    columns = []
    rows = []
    kwargs = {}
    if sort:
        kwargs["order"] = [sort]
    if kind not in KNOWN_MODELS:
        for entity in db.ilist_entities(kind, limit, offset, **kwargs):
            info = dict(entity)
            info["__key__"] = entity.key
            if entity.key.parent:
                info["parent"] = entity.key.parent
            if len(columns) < 1:
                columns = sorted(info.keys())
            rows.append(info)
    else:
        for instance in KNOWN_MODELS[kind].ilist_all(limit, offset, **kwargs):
            info = instance.to_dict(True)
            if kind == "Chunk":
                info["parent"] = instance.key().parent
            if len(columns) < 1:
                columns = sorted(info.keys())
            if kind == "Chunk" and len(info["data"]) > 20:
                info["data"] = "%s... (%s bytes)" % (
                    info["data"][:20],
                    len(info["data"]),
                )
            rows.append(info)
    return render_template(
        "data_kind.html",
        data_url=DATA_URL,
        kinds=kinds_list,
        kind=kind,
        sort=sort,
        page=page,
        count=count,
        columns=columns,
        rows=rows,
    )


# @app.route("/data/<string:kind>/<path:key>")
# @sessions.flask_authorize("admin")
def data_key_view(kind, key):
    kinds_list = get_models()
    if kind not in KNOWN_MODELS:
        kinds_list = get_kinds()
        if kind not in kinds_list or kind == "Others":
            return data_home_view(kind)
    if kind in ("Path", "Dir", "File"):
        if not key.startswith("/"):
            id_or_name = "/" + key
        else:
            id_or_name = key
        key = db.get_key(kind, id_or_name)
    elif kind in ("Chunk") and ":" in key:
        id_or_name, parent = key.split(":", 1)
        path_args = parent.split(":")
        key = db.get_key(kind, int(id_or_name), *path_args)
    else:
        if key.isdecimal():
            id_or_name = int(key)
        else:
            id_or_name = key
        key = db.get_key(kind, id_or_name)
    entity = db.get_entity(key)
    parent = None
    chunks = []
    if kind not in KNOWN_MODELS:
        info = dict(entity)
        info["__key__"] = entity.key
        if entity.key.parent:
            parent = entity.key.parent
    else:
        instance = db.make_instance(kind, entity)
        info = instance.to_dict(True)
        if kind == "Chunk":
            parent = instance.key().parent
        if kind == "Path" and hasattr(instance, "size"):
            chunks = Chunk.list_keys_by_file(instance)
    return render_template(
        "data_key.html",
        data_url=DATA_URL,
        kinds=kinds_list,
        kind=kind,
        key=key,
        info=info,
        chunks=chunks,
        parent=parent,
    )


if __name__ == "__main__":
    # python3 -m data.views
    app = create_app()
    app.run(host="0.0.0.0", port=8080, use_reloader=False)
