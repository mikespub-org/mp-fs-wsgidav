#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

import logging
import time
import os.path

from flask import Flask, render_template, request, jsonify
from flask.views import MethodView
import flask.json

from . import db


PAGE_SIZE = 10


def create_app(debug=True, base_url="/api/v1/fire"):
    """Create main Flask app if this module is the entrypoint, e.g. python3 -m fire.api"""
    app = Flask(__name__)
    app.debug = debug
    configure_app(app, base_url=base_url)
    return app


# app = create_app()


def configure_app(app, base_url="/api/v1/fire", authorize_wrap=None):
    """Configure existing Flask app with firestore view functions, template filters and global functions"""
    if authorize_wrap:
        app.add_url_rule(
            base_url + "/", view_func=authorize_wrap(HomeAPI.as_view("home_api"))
        )
        app.add_url_rule(
            base_url + "/<string:name>/",
            view_func=authorize_wrap(ListAPI.as_view("list_api")),
        )
        app.add_url_rule(
            base_url + "/<string:parent>/<path:item>",
            view_func=authorize_wrap(ItemAPI.as_view("item_api")),
        )
    else:
        app.add_url_rule(base_url + "/", view_func=HomeAPI.as_view("home_api"))
        app.add_url_rule(
            base_url + "/<string:name>/", view_func=ListAPI.as_view("list_api")
        )
        app.add_url_rule(
            base_url + "/<string:parent>/<path:item>",
            view_func=ItemAPI.as_view("item_api"),
        )
    # TODO: check for conflict in existing ruleset
    app.add_url_rule(os.path.dirname(base_url) + "/", view_func=fire_api)
    app.json_encoder = MyJSONEncoder


class MyJSONEncoder(flask.json.JSONEncoder):
    def default(self, obj):
        # subcollections always end with / - see item_to_path and templates/fire_item.html
        if isinstance(obj, (db.DocumentReference, db.CollectionReference)):
            return item_to_path(obj)
        if isinstance(obj, bytes):
            # TODO: we should use base64 encoding here
            return repr(obj)
        return super(MyJSONEncoder, self).default(obj)


def fire_api():
    with open(os.path.join(os.path.dirname(__file__), "openapi.json"), "r") as fp:
        info = flask.json.load(fp)
        return info


def item_to_path(ref):
    # doc_ref
    if hasattr(ref, "path"):
        return ref.path
    # coll_ref - collection urls always end with / here
    if ref.parent:
        return "%s/%s/" % (ref.parent.path, ref.id)
    return "%s/" % ref.id


def item_to_dict(doc, truncate=False):
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
    if (
        truncate
        and "data" in info
        and isinstance(info["data"], bytes)
        and len(info["data"]) > 20
    ):
        info["data"] = "%s... (%s bytes)" % (info["data"][:20], len(info["data"]))
    if doc.reference.parent:
        info["_parent"] = doc.reference.parent
    return info


list_names = []
list_stats = {}


def get_lists(reset=False):
    global list_names
    if len(list_names) > 0 and not reset:
        return list_names
    firestore_colls = []
    for coll_ref in db.list_root():
        firestore_colls.append(coll_ref.id)
    list_names = sorted(firestore_colls)
    return list_names


def get_stats(reset=False):
    global list_stats
    if len(list_stats) > 0 and not reset:
        return list_stats
    list_stats = {}
    list_stats["Stats"] = {"timestamp": time.time()}
    for coll_ref in db.list_root():
        list_stats[coll_ref.id] = get_list_stats(coll_ref)
    return list_stats


def get_list_stats(coll_ref, limit=1000):
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


def get_list_count(name, reset=False):
    global list_stats
    if name in list_stats and list_stats[name]["count"] is not None and not reset:
        return list_stats[name]["count"]
    if name not in get_lists():
        return
    if name not in list_stats:
        coll_ref = db.get_coll_ref(name)
        list_stats[name] = get_list_stats(coll_ref)
    else:
        coll_ref = list_stats[name]["coll_ref"]
    count = 0
    for doc_ref in coll_ref.list_documents():
        count += 1
    list_stats[name]["count"] = count
    return list_stats[name]["count"]


class HomeAPI(MethodView):
    def get(self):
        """Get all top-level collections"""
        result = home_get()
        return jsonify(result)

    def post(self):
        """Create (document in) new top-level collection"""
        info = request.get_json()
        result = home_post(info)
        return result

    def delete(self):
        """Delete all top-level collections"""
        result = home_delete()
        return result


def home_get():
    """Get all top-level collections"""
    return get_lists()


def home_post(info):
    return "Create (document in) new top-level collection"


def home_delete():
    return "Delete all top-level collections!?"


class ListAPI(MethodView):
    def get(self, name):
        """Get all documents in collection"""
        # when dealing with subcollections coming from item_get
        if name.split("/")[0] not in get_lists():
            # return jsonify(home_get())
            raise ValueError("Invalid Collection %r" % name)
        page = int(request.args.get("page", 1))
        sort = request.args.get("sort", None)
        fields = request.args.get("fields", None)
        result = list_get(name, page, sort, fields)
        return jsonify(result)

    def post(self, name):
        """Create new document in collection"""
        info = request.get_json()
        result = list_post(name, info)
        return result

    def delete(self, name):
        """Delete collection (and all its documents)"""
        result = list_delete(name)
        return result


def list_get(name, page=1, sort=None, fields=None, truncate=True):
    return list(ilist_get(name, page=page, sort=sort, fields=fields, truncate=truncate))


def ilist_get(name, page=1, sort=None, fields=None, truncate=True):
    if page < 1:
        page = 1
    limit = PAGE_SIZE
    offset = (page - 1) * limit
    coll_ref = db.get_coll_ref(name)
    if fields:
        if not isinstance(fields, list):
            fields = fields.split(",")
        query = coll_ref.select(fields).limit(limit).offset(offset)
    else:
        query = coll_ref.limit(limit).offset(offset)
    if sort:
        if sort.startswith("-"):
            query = query.order_by(sort[1:], direction="DESCENDING")
        else:
            query = query.order_by(sort)
    for doc in query.stream():
        info = item_to_dict(doc, truncate=truncate)
        yield info


def list_post(name, info):
    return "Create new document in collection"


def list_delete(name):
    return "Delete collection (and all its documents)"


class ItemAPI(MethodView):
    def get(self, parent, item):
        """Get document"""
        if parent not in get_lists():
            # return jsonify(home_get())
            raise ValueError("Invalid Collection %r" % parent)
        # subcollections always end with / - see item_to_path and templates/fire_item.html
        if item.endswith("/"):
            parent += "/" + item[:-1]
            page = int(request.args.get("page", 1))
            sort = request.args.get("sort", None)
            fields = request.args.get("fields", None)
            return jsonify(list_get(parent, page, sort, fields))
        fields = request.args.get("fields", None)
        children = request.args.get("children", False)
        result = item_get(parent, item, fields=fields, children=children)
        return jsonify(result)

    def post(self, parent, item):
        """Create subcollection/document in document (TBD)"""
        info = request.get_json()
        result = item_post(parent, item, info)
        return result

    def put(self, parent, item):
        """Save/replace document"""
        info = request.get_json()
        result = item_put(parent, item, info)
        return result

    def patch(self, parent, item):
        """Update document"""
        info = request.get_json()
        result = item_patch(parent, item, info)
        return result

    def delete(self, parent, item):
        """Delete document (and all its subcollections)"""
        result = item_delete(parent, item)
        return result


def item_get_ref(coll, item):
    # coll_ref = db.get_coll_ref(coll)
    # doc_ref = coll_ref.document(item)
    doc_ref = db.get_doc_ref(coll + "/" + item)
    return doc_ref


def item_get(parent, item, fields=None, children=False):
    """Get document"""
    if fields and not isinstance(fields, list):
        fields = fields.split(",")
    doc_ref = item_get_ref(parent, item)
    doc = doc_ref.get(fields)
    if not doc.exists:
        raise ValueError("Invalid Document %r" % doc_ref.path)
    info = item_to_dict(doc)
    if children:
        info["_children"] = list(doc_ref.collections())
    return info


def item_post(parent, item, info):
    return "Create subcollection/document in document (TBD)"


def item_put(parent, item, info):
    return "Save/replace document"


def item_patch(parent, item, info):
    return "Update document"


def item_delete(parent, item):
    return "Delete document (and all its subcollections)"


if __name__ == "__main__":
    # python3 -m fire.api
    app = create_app()
    app.run(host="0.0.0.0", port=8080, use_reloader=False)
