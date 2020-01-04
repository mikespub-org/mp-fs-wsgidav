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
COLLS_LIST = []


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
            base_url + "/<string:coll>/",
            view_func=authorize_wrap(CollAPI.as_view("coll_api")),
        )
        app.add_url_rule(
            base_url + "/<string:coll>/<path:ref>",
            view_func=authorize_wrap(DocAPI.as_view("doc_api")),
        )
    else:
        app.add_url_rule(base_url + "/", view_func=HomeAPI.as_view("home_api"))
        app.add_url_rule(
            base_url + "/<string:coll>/", view_func=CollAPI.as_view("coll_api")
        )
        app.add_url_rule(
            base_url + "/<string:coll>/<path:ref>", view_func=DocAPI.as_view("doc_api")
        )
    # TODO: check for conflict in existing ruleset
    app.add_url_rule(os.path.dirname(base_url) + "/", view_func=fire_api)
    app.json_encoder = MyJSONEncoder


class MyJSONEncoder(flask.json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, db.DocumentReference):
            return obj.path
        if isinstance(obj, bytes):
            # TODO: we should use base64 encoding here
            return repr(obj)
        return super(MyJSONEncoder, self).default(obj)


def fire_api():
    with open(os.path.join(os.path.dirname(__file__), "openapi.json"), "r") as fp:
        info = flask.json.load(fp)
        return info


class HomeAPI(MethodView):
    def get(self):
        """Get all top-level collections"""
        result = fire_home_get()
        return jsonify(result)

    def post(self):
        """Create (document in) new top-level collection"""
        info = request.get_json()
        result = fire_home_post(info)
        return result

    def delete(self):
        """Delete all top-level collections"""
        result = fire_home_delete()
        return result


def get_colls(reset=False):
    global COLLS_LIST
    if len(COLLS_LIST) > 0 and not reset:
        return COLLS_LIST
    firestore_colls = []
    for coll_ref in db.list_root():
        firestore_colls.append(coll_ref.id)
    COLLS_LIST = sorted(firestore_colls)
    return COLLS_LIST


def fire_home_get():
    """Get all top-level collections"""
    return get_colls()


def fire_home_post(info):
    return "Create (document in) new top-level collection"


def fire_home_delete():
    return "Delete all top-level collections!?"


class CollAPI(MethodView):
    def get(self, coll):
        """Get all documents in collection"""
        # when dealing with subcollections coming from fire_doc_view
        if coll.split("/")[0] not in get_colls():
            return jsonify(fire_home_get())
        page = int(request.args.get("page", 1))
        sort = request.args.get("sort", None)
        fields = request.args.get("fields", None)
        result = fire_coll_get(coll, page, sort, fields)
        return jsonify(result)

    def post(self, coll):
        """Create new document in collection"""
        info = request.get_json()
        result = fire_coll_post(coll, info)
        return result

    def delete(self, coll):
        """Delete collection (and all its documents)"""
        result = fire_coll_delete(coll)
        return result


def doc_to_dict(doc, truncate=False):
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
    # if doc.reference.parent:
    #     info["_parent"] = doc.reference.parent.path
    return info


def fire_coll_get(coll, page=1, sort=None, fields=None, truncate=True):
    return list(
        ifire_coll_get(coll, page=page, sort=sort, fields=fields, truncate=truncate)
    )


def ifire_coll_get(coll, page=1, sort=None, fields=None, truncate=True):
    if page < 1:
        page = 1
    limit = PAGE_SIZE
    offset = (page - 1) * limit
    coll_ref = db.get_coll_ref(coll)
    # for doc in db.ilist_entities(coll, limit, offset, **kwargs):
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
        info = doc_to_dict(doc, truncate=truncate)
        yield info


def fire_coll_post(coll, info):
    return "Create new document in collection"


def fire_coll_delete(coll):
    return "Delete collection (and all its documents)"


class DocAPI(MethodView):
    def get(self, coll, ref):
        if coll not in get_colls():
            return jsonify(fire_home_get())
        # subcollections always end with / - see ref_link and templates/fire_doc.html
        if ref.endswith("/"):
            coll += "/" + ref[:-1]
            page = int(request.args.get("page", 1))
            sort = request.args.get("sort", None)
            fields = request.args.get("fields", None)
            return jsonify(fire_coll_get(coll, page, sort, fields))
        fields = request.args.get("fields", None)
        subcolls = request.args.get("subcolls", False)
        result = fire_doc_get(coll, ref, fields=fields, subcolls=subcolls)
        return jsonify(result)

    def post(self, coll, ref):
        """Create subcollection/document in document (TBD)"""
        info = request.get_json()
        result = fire_doc_post(coll, ref, info)
        return result

    def put(self, coll, ref):
        """Save/replace document"""
        info = request.get_json()
        result = fire_doc_put(coll, ref, info)
        return result

    def patch(self, coll, ref):
        """Update document"""
        info = request.get_json()
        result = fire_doc_patch(coll, ref, info)
        return result

    def delete(self, coll, ref):
        """Delete document (and all its subcollections)"""
        result = fire_doc_delete(coll, ref)
        return result


def fire_doc_get(coll, ref, fields=None, subcolls=False):
    # coll_ref = db.get_coll_ref(coll)
    # doc_ref = coll_ref.document(ref)
    doc_ref = db.get_doc_ref(coll + "/" + ref)
    if fields and not isinstance(fields, list):
        fields = fields.split(",")
    doc = doc_ref.get(fields)
    info = doc_to_dict(doc)
    if subcolls:
        info["_collections"] = []
        # subcollections always end with / - see ref_link and templates/fire_doc.html
        for subcoll_ref in doc_ref.collections():
            info["_collections"].append("%s/%s/" % (doc_ref.path, subcoll_ref.id))
    # if doc.reference.parent:
    #     parent = doc.reference.parent
    return info


def fire_doc_post(coll, ref, info):
    return "Create subcollection/document in document (TBD)"


def fire_doc_put(coll, ref, info):
    return "Save/replace document"


def fire_doc_patch(coll, ref, info):
    return "Update document"


def fire_doc_delete(coll, ref):
    return "Delete document (and all its subcollections)"


if __name__ == "__main__":
    # python3 -m fire.api
    app = create_app()
    app.run(host="0.0.0.0", port=8080, use_reloader=False)
