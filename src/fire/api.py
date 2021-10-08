#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

import logging
import os.path
import pickle
import time

import flask.json
from flask import Flask, jsonify, request
from flask.views import MethodView

from . import db
from .config import LIST_CONFIG, PAGE_SIZE, get_list_config


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


def pb2epoch(pb):
    # return time.mktime(tm.utctimetuple())
    if hasattr(pb, "timestamp_pb"):
        pb = pb.timestamp_pb()
    return pb.seconds + float(pb.nanos / 1000000000.0)


# def dt2epoch(dt):
#     # return time.mktime(dt.utctimetuple())
#     return (
#         dt - datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
#     ) / datetime.timedelta(seconds=1)


# def epoch2dt(timestamp):
#     return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)


class MyJSONEncoder(flask.json.JSONEncoder):
    def default(self, obj):
        # if isinstance(obj, db.DocumentSnapshot):
        #     return item_to_dict(obj)
        # subcollections always end with / - see item_to_path and templates/fire_item.html
        if isinstance(obj, (db.DocumentReference, db.CollectionReference)):
            return item_to_path(obj)
        # if isinstance(obj, google.api_core.datetime_helpers.DatetimeWithNanoseconds):
        #    return repr(obj)
        # In objects/some-id: from firestore.SERVER_TIMESTAMP
        # In data/one: from datetime.datetime.now()
        # https://github.com/googleapis/google-cloud-python/blob/master/api_core/tests/unit/test_datetime_helpers.py
        # https://github.com/googleapis/google-cloud-python/blob/master/api_core/google/api_core/datetime_helpers.py
        # if type(obj).__name__.endswith("DatetimeWithNanoseconds"):
        # if isinstance(obj, datetime.datetime):
        #     return obj.isoformat(" ")
        #     # return obj.rfc3339()
        if isinstance(obj, bytes):
            # TODO: we should use base64 encoding here
            return repr(obj)
        return super().default(obj)


def fire_api():
    with open(os.path.join(os.path.dirname(__file__), "openapi.json")) as fp:
        info = flask.json.load(fp)
        return info


def item_to_path(ref):
    # doc_ref
    if hasattr(ref, "path"):
        return ref.path
    # coll_ref - collection urls always end with / here
    if ref.parent:
        return f"{ref.parent.path}/{ref.id}/"
    return "%s/" % ref.id


def item_to_dict(doc, truncate=False):
    info = doc.to_dict()
    if (
        hasattr(doc, "create_time")
        and doc.create_time
        and not isinstance(doc.create_time, float)
    ):
        doc.create_time = pb2epoch(doc.create_time)
    if (
        hasattr(doc, "update_time")
        and doc.update_time
        and not isinstance(doc.update_time, float)
    ):
        doc.update_time = pb2epoch(doc.update_time)
    if (
        hasattr(doc, "read_time")
        and doc.read_time
        and not isinstance(doc.read_time, float)
    ):
        doc.read_time = pb2epoch(doc.read_time)
    info.update(doc.__dict__)
    del info["_data"]
    del info["_exists"]
    if truncate:
        coll_ref = doc.reference.parent
        # coll_path = item_to_path(coll_ref)
        coll_id = coll_ref.id
        if coll_id in LIST_CONFIG:
            truncate_list = LIST_CONFIG[coll_id].get("truncate_list", [])
            array_list = LIST_CONFIG[coll_id].get("array", [])
        else:
            truncate_list = list(info.keys())
            array_list = []
        for attr in truncate_list:
            if attr in info and isinstance(info[attr], bytes) and len(info[attr]) > 20:
                info[attr] = f"{info[attr][:20]}... ({len(info[attr])} bytes)"
        for attr in array_list:
            if attr in info and isinstance(info[attr], list) and len(info[attr]) > 1:
                info[attr] = [info[attr][0], "... (%s items)" % len(info[attr])]
    if doc.reference.parent:
        info["_parent"] = doc.reference.parent
    return info


list_names = []
list_stats = {}
list_filters = {}


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
    # TODO: load stats from Firestore + check timestamp
    coll_ref = db.get_coll_ref("_Stat_Coll_")
    for doc in coll_ref.stream():
        info = doc.to_dict()
        info["coll_ref"] = db.get_coll_ref(info["name"])
        list_stats[info["name"]] = info
    for coll_ref in db.list_root():
        if coll_ref.id not in list_stats:
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
        "timestamp": time.time(),
    }
    if stats["count"] == limit:
        stats["count"] = str(limit) + "+"
    return stats


def get_list_count(name, reset=False, limit=1000):
    global list_stats
    if name in list_stats and list_stats[name]["count"] is not None and not reset:
        return list_stats[name]["count"]
    # if name not in get_lists():
    #     return
    if name not in list_stats:
        coll_ref = db.get_coll_ref(name)
        list_stats[name] = get_list_stats(coll_ref)
    else:
        coll_ref = list_stats[name]["coll_ref"]
    # https://github.com/googleapis/google-cloud-python/issues/10186
    # count = None
    count = 0
    # for doc_ref in coll_ref.list_documents():
    # select [] fields to count the documents!? - is equivalent to selecting ["__name__"], see
    # https://github.com/googleapis/google-cloud-python/pull/6735
    # for doc in coll_ref.select([]).limit(limit).stream():
    for doc in coll_ref.select(["__name__"]).limit(limit).stream():
        count += 1
    return set_list_count(name, count)


def set_list_count(name, count):
    global list_stats
    if name not in list_stats:
        coll_ref = db.get_coll_ref(name)
        list_stats[name] = get_list_stats(coll_ref)
    list_stats[name]["count"] = count
    now = time.time()
    list_stats[name]["timestamp"] = now
    # save stats to Firestore
    # doc_id = name.replace("/", ":")
    if "/" not in name:
        coll_ref = db.get_coll_ref("_Stat_Coll_")
        coll_ref.document(name).set({"name": name, "count": count, "timestamp": now})
    return list_stats[name]["count"]


def get_filters(reset=False):
    global list_filters
    if len(list_filters) > 0 and not reset:
        return list_filters
    list_filters = {}
    # TODO: load filters from Firestore + check timestamp
    coll_ref = db.get_coll_ref("_Filter_Coll_")
    for doc in coll_ref.stream():
        info = doc.to_dict()
        list_filters[info["name"]] = info["filters"]
    for name in get_lists():
        if name not in list_filters:
            get_list_filters(name)
    return list_filters


def get_list_filters(name, reset=False):
    global list_filters
    if name not in list_filters or reset:
        list_filters[name] = {}
        filter_list = get_list_config(name, "filters")
        for filter in filter_list:
            list_filters[name][filter] = {}
    return list_filters[name]


def set_list_filters(name, filter_dict):
    global list_filters
    list_filters[name] = filter_dict


def create_list_filters(name, reset=False, limit=1000):
    filter_dict = get_list_filters(name, reset)
    if len(filter_dict) < 1:
        return
    filter_keys = list(filter_dict.keys())
    coll_ref = db.get_coll_ref(name)
    for doc in coll_ref.select(filter_keys).limit(limit).stream():
        for key in filter_keys:
            value = str(doc.get(key))
            if value not in filter_dict[key]:
                # filter_dict[key].append(value)
                filter_dict[key][value] = 0
            filter_dict[key][value] += 1
    set_list_filters(name, filter_dict)
    save_list_filters(name)


def save_list_filters(name=None):
    global list_filters
    if name is None:
        todo = list(list_filters.keys())
    elif name in list_filters:
        todo = [name]
    else:
        return
    coll_ref = db.get_coll_ref("_Filter_Coll_")
    now = time.time()
    for name in todo:
        coll_ref.document(name).set(
            {"name": name, "filters": list_filters[name], "timestamp": now}
        )


def parse_filter_args(args, name):
    filters = None
    # Note: this also supports field_paths, e.g. /cp_media/?filters.identifiers.imdb=tt1470827
    for key, value in list(args.items()):
        if not key.startswith("filters."):
            continue
        if filters is None:
            filters = []
        field_path = key[8:]
        # TODO: look at first char for <, >, etc.
        op_string = "=="
        # CHECKME: assuming this is a doc path here!?
        if "/" in value:
            filters.append((field_path, op_string, db.get_doc_ref(value)))
        # TODO: do something with name, cfr. data kind
        elif value == "None":
            filters.append((field_path, op_string, None))
        elif value == "True":
            filters.append((field_path, op_string, True))
        elif value == "False":
            filters.append((field_path, op_string, False))
        elif value != "":
            if value.isdecimal():
                try:
                    value = int(value)
                except:
                    pass
            filters.append((field_path, op_string, value))
    return filters


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
    """Create (document in) new top-level collection"""
    raise NotImplementedError("Create (document in) new top-level collection")


def home_delete():
    """Delete all top-level collections!?"""
    raise NotImplementedError("Delete all top-level collections!?")


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
        filters = parse_filter_args(request.args, name)
        if filters:
            result = list_get(name, page, sort, fields, filters=filters)
        else:
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


def list_get(name, page=1, sort=None, fields=None, truncate=True, filters=None):
    """Get all documents in collection"""
    return list(
        ilist_get(
            name,
            page=page,
            sort=sort,
            fields=fields,
            truncate=truncate,
            filters=filters,
        )
    )


def ilist_get(name, page=1, sort=None, fields=None, truncate=True, filters=None):
    if page < 1:
        page = 1
    limit = PAGE_SIZE
    offset = (page - 1) * limit
    coll_ref = db.get_coll_ref(name)
    coll_id = coll_ref.id
    if not fields:
        fields = get_list_config(coll_id, "fields")
    if fields:
        if not isinstance(fields, list):
            fields = fields.split(",")
        query = coll_ref.select(fields)
    else:
        query = coll_ref
    if filters:
        # [(field_path, op_string, value)]
        for field_path, op_string, value in filters:
            query = query.where(field_path, op_string, value)
    if sort:
        if sort.startswith("-"):
            query = query.order_by(sort[1:], direction="DESCENDING")
        else:
            query = query.order_by(sort)
    query = query.limit(limit).offset(offset)
    for doc in query.stream():
        info = item_to_dict(doc, truncate=truncate)
        yield info


def list_post(name, info):
    """Create new document in collection"""
    db.get_coll_ref(name)
    raise NotImplementedError("Create new document in collection")


def list_delete(name):
    """Delete collection (and all its documents)"""
    db.get_coll_ref(name)
    raise NotImplementedError("Delete collection (and all its documents)")


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
            filters = parse_filter_args(request.args, parent)
            if filters:
                return jsonify(list_get(parent, page, sort, fields, filters=filters))
            return jsonify(list_get(parent, page, sort, fields))
        fields = request.args.get("fields", None)
        children = request.args.get("children", False)
        unpickle = request.args.get("unpickle", True)
        result = item_get(
            parent, item, fields=fields, children=children, unpickle=unpickle
        )
        # return individual property of this item!?
        if fields and isinstance(fields, str) and "," not in fields:
            if "_parent" in result and result["_parent"]:
                coll_id = result["_parent"].id
            else:
                coll_id = parent
            result = result[fields]
            # TODO: specify content-type if available/known
            if isinstance(result, str):
                return result, 200, {"Content-Type": "text/plain"}
            # https://stackoverflow.com/questions/20508788/do-i-need-content-type-application-octet-stream-for-file-download
            if isinstance(result, bytes):
                if fields in get_list_config(coll_id, "image"):
                    return result, 200, {"Content-Type": "image/png"}
                # return result, 200, {"Content-Type": "application/octet-stream"}

            if fields in get_list_config(coll_id, "pickled"):
                return jsonify(result)
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


def item_get(parent, item, fields=None, children=False, unpickle=False):
    """Get document"""
    if fields and not isinstance(fields, list):
        fields = fields.split(",")
    doc_ref = item_get_ref(parent, item)
    doc = doc_ref.get(fields)
    if not doc.exists:
        raise ValueError("Invalid Document %r" % doc_ref.path)
    info = item_to_dict(doc)
    coll_id = doc_ref.parent.id
    if unpickle:
        pickled_list = get_list_config(coll_id, "pickled")
        # pickled_list = list(info.keys())
        # See https://github.com/python/cpython/blob/master/Lib/pickle.py
        # and https://github.com/python/cpython/blob/master/Lib/pickletools.py
        for attr in pickled_list:
            if attr in info and isinstance(info[attr], bytes) and len(info[attr]) > 0:
                # https://stackoverflow.com/questions/4523505/chr-equivalent-returning-a-bytes-object-in-py3k
                char = b"%c" % info[attr][0]
                # logging.debug("%s %r" % (attr, char))
                # based on use cases for InfoStore
                if char not in (pickle.MARK, pickle.PROTO):
                    continue
                try:
                    info[attr] = pickle.loads(info[attr], encoding="latin1")
                except Exception as e:
                    logging.info(e)
    if fields:
        result = {}
        result["_reference"] = info["_reference"]
        result["_parent"] = info["_parent"]
        # if len(fields) == 1 and fields[0] in info:
        for attr in fields:
            if attr in info:
                result[attr] = info[attr]
        return result
    # handle ancestor
    # child_list = get_list_config(coll_id, "children")
    # if children and child_list:
    #     info["_children"] = {}
    #     for child in child_list:
    #         info["_children"][child] = db.list_entity_keys(
    #             child, limit=PAGE_SIZE, ancestor=parent_key
    #         )
    # handle subcollections
    if children:
        info["_children"] = list(doc_ref.collections())
    # handle references
    ref_dict = get_list_config(coll_id, "references")
    if children and ref_dict:
        info["_references"] = {}
        for ref in ref_dict.keys():
            coll_ref = db.get_coll_ref(ref)
            query = (
                coll_ref.select([ref_dict[ref]])
                .where(ref_dict[ref], "==", doc_ref)
                .limit(PAGE_SIZE)
            )
            child_refs = []
            for child_doc in query.stream():
                # print(item_to_dict(child_doc))
                child_refs.append(child_doc.reference)
            if len(child_refs) > 0:
                # info["_references"][ref] = child_refs
                if ref not in info["_references"]:
                    info["_references"][ref] = {}
                info["_references"][ref][ref_dict[ref]] = child_refs
    return info


def item_post(parent, item, info):
    """Create subcollection/document in document (TBD)"""
    doc_ref = item_get_ref(parent, item)
    fields = info.keys()
    doc = doc_ref.get(fields)
    if not doc.exists:
        raise ValueError("Invalid Document %r" % doc_ref.path)
    raise NotImplementedError("Create subcollection/document in document (TBD)")


def item_put(parent, item, info):
    """Save/replace document"""
    doc_ref = item_get_ref(parent, item)
    fields = info.keys()
    doc = doc_ref.get(fields)
    if not doc.exists:
        raise ValueError("Invalid Document %r" % doc_ref.path)
    raise NotImplementedError("Save/replace document")


def item_patch(parent, item, info):
    """Update document"""
    doc_ref = item_get_ref(parent, item)
    fields = info.keys()
    doc = doc_ref.get(fields)
    if not doc.exists:
        raise ValueError("Invalid Document %r" % doc_ref.path)
    raise NotImplementedError("Update document")


def item_delete(parent, item):
    """Delete document (and all its subcollections)"""
    item_get_ref(parent, item)
    # doc = doc_ref.get(fields)
    # if not doc.exists:
    #     raise ValueError("Invalid Document %r" % doc_ref.path)
    raise NotImplementedError("Delete document (and all its subcollections)")


if __name__ == "__main__":
    # python3 -m fire.api
    app = create_app()
    app.add_url_rule("/", view_func=fire_api)
    app.run(host="0.0.0.0", port=8080, use_reloader=False)
