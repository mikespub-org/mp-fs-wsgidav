#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

import logging
import time
import os.path
import pickle

from flask import Flask, render_template, request, jsonify
from flask.views import MethodView
import flask.json

from . import db
from .config import PAGE_SIZE, KNOWN_MODELS, KIND_CONFIG


def create_app(debug=True, base_url="/api/v1/data"):
    """Create main Flask app if this module is the entrypoint, e.g. python3 -m data.api"""
    app = Flask(__name__)
    app.debug = debug
    configure_app(app, base_url=base_url)
    return app


# app = create_app()


def configure_app(app, base_url="/api/v1/data", authorize_wrap=None):
    """Configure existing Flask app with datastore view functions, template filters and global functions"""
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
    app.add_url_rule(os.path.dirname(base_url) + "/", view_func=data_api)
    app.json_encoder = MyJSONEncoder


class MyJSONEncoder(flask.json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, db.Key):
            return item_to_path(obj)
        if isinstance(obj, bytes):
            # TODO: we should use base64 encoding here
            return repr(obj)
        return super(MyJSONEncoder, self).default(obj)


def data_api():
    with open(os.path.join(os.path.dirname(__file__), "openapi.json"), "r") as fp:
        info = flask.json.load(fp)
        return info


def item_to_path(key):
    if key.kind in ("Path", "Dir", "File"):
        # drop the first / of the id_or_name = path
        return "%s/%s" % (key.kind, key.id_or_name[1:])
    # elif key.kind in ("Chunk") and key.parent:
    elif (
        key.kind in KIND_CONFIG
        and KIND_CONFIG[key.kind].get("parent", None)
        and key.parent
    ):
        # add the :parent:path
        return "%s/%s:%s:%s" % (
            key.kind,
            key.id_or_name,
            key.parent.kind,
            key.parent.id_or_name,
        )
    return "%s/%s" % (key.kind, key.id_or_name)


def item_to_dict(entity, truncate=False):
    info = dict(entity)
    info["_key"] = entity.key
    if entity.kind in KIND_CONFIG and KIND_CONFIG[entity.kind].get("parent", None):
        info["_parent"] = entity.key.parent
    elif entity.key.parent:
        info["_parent"] = entity.key.parent
    if truncate:
        if entity.kind in KIND_CONFIG:
            truncate_list = KIND_CONFIG[entity.kind].get("truncate_list", [])
        else:
            truncate_list = list(info.keys())
        for attr in truncate_list:
            if attr in info and isinstance(info[attr], bytes) and len(info[attr]) > 20:
                info[attr] = "%s... (%s bytes)" % (info[attr][:20], len(info[attr]))
    return info


def instance_to_dict(instance, truncate=False):
    info = instance.to_dict(True)
    # if instance._kind == "Chunk":
    if instance._kind in KIND_CONFIG and KIND_CONFIG[instance._kind].get(
        "parent", None
    ):
        info["_parent"] = instance.key().parent
    # if truncate and instance._kind == "Chunk" and len(info["data"]) > 20:
    if truncate:
        if instance._kind in KIND_CONFIG:
            truncate_list = KIND_CONFIG[instance._kind].get("truncate_list", [])
        else:
            truncate_list = list(info.keys())
        for attr in truncate_list:
            if attr in info and isinstance(info[attr], bytes) and len(info[attr]) > 20:
                info[attr] = "%s... (%s bytes)" % (info[attr][:20], len(info[attr]))
    return info


def get_models():
    models_list = sorted(KNOWN_MODELS.keys())
    models_list.append("Others")
    return models_list


list_names = []
list_stats = {}


def get_lists(reset=False):
    global list_names
    if len(list_names) > 0 and not reset:
        return list_names
    list_names = get_models()
    for kind in sorted(db.list_kinds()):
        if kind not in list_names:
            list_names.append(kind)
    return list_names


def get_stats(reset=False):
    global list_stats
    if len(list_stats) > 0 and not reset:
        return list_stats
    list_stats = {}
    # list_stats['Stats'] = stats.GlobalStat.list_all(1)
    kind = "__Stat_Total__"
    id_or_name = "total_entity_usage"
    key = db.get_key(kind, id_or_name)
    entity = db.get_entity(key)
    if entity:
        info = item_to_dict(entity)
    else:
        info = {"timestamp": time.time()}
    list_stats["Stats"] = {}
    list_stats["Stats"][kind] = info
    kind = "__Stat_Kind__"
    list_stats["Stats"][kind] = {}
    for entity in db.ilist_entities(kind):
        info = item_to_dict(entity)
        list_stats["Stats"][kind][info["kind_name"]] = info
    # for stat in stats.KindPropertyNamePropertyTypeStat.list_all():
    #    list_stats['Stats'].append(stat)
    kind = "__Stat_PropertyType_PropertyName_Kind__"
    for entity in db.ilist_entities(kind):
        info = item_to_dict(entity)
        if info["kind_name"] not in list_stats["Stats"]:
            list_stats["Stats"][info["kind_name"]] = {}
        list_stats["Stats"][info["kind_name"]][info["property_name"]] = info
    for model in KNOWN_MODELS:
        list_stats[model] = get_list_stats(KNOWN_MODELS[model])
    return list_stats


def get_list_stats(model, limit=1000):
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


def get_list_count(model, reset=False):
    global list_stats
    if model in list_stats and list_stats[model]["count"] is not None and not reset:
        return list_stats[model]["count"]
    if model not in KNOWN_MODELS:
        # initialize stats if needed
        stats = get_stats()
        if (
            "Stats" in stats
            and "__Stat_Kind__" in stats["Stats"]
            and model in stats["Stats"]["__Stat_Kind__"]
        ):
            stats_count = stats["Stats"]["__Stat_Kind__"][model]["count"]
            if stats_count > 0:
                return stats_count
        return
    if model not in list_stats:
        list_stats[model] = get_list_stats(KNOWN_MODELS[model])
    list_stats[model]["count"] = KNOWN_MODELS[model].get_count()
    return list_stats[model]["count"]


class HomeAPI(MethodView):
    def get(self):
        """Get all models/kinds"""
        result = home_get()
        return jsonify(result)

    def post(self):
        """Create new kind"""
        info = request.get_json()
        result = home_post(info)
        return result

    def delete(self):
        """Delete all kinds"""
        result = home_delete()
        return result


def home_get(name=None):
    """Get all models/kinds"""
    # when dealing with Others coming from list_get
    if name == "Others":
        kinds_list = get_lists()
    else:
        kinds_list = get_models()
    return kinds_list


def home_post(info):
    """Create new kind"""
    raise NotImplementedError("Create new kind")


def home_delete():
    """Delete all kinds"""
    raise NotImplementedError("Delete all kinds!?")


class ListAPI(MethodView):
    def get(self, name):
        """Get all entities of kind"""
        # by default we only show known models here
        if name not in KNOWN_MODELS:
            if name == "Others":
                return jsonify(home_get(name))
            kinds_list = get_lists()
            if name not in kinds_list:
                raise ValueError("Invalid Kind %r" % name)
        page = int(request.args.get("page", 1))
        sort = request.args.get("sort", None)
        fields = request.args.get("fields", None)
        result = list_get(name, page, sort, fields)
        return jsonify(result)

    def post(self, name):
        """Create new entity of kind"""
        info = request.get_json()
        result = list_post(name, info)
        return result

    def delete(self, name):
        """Delete kind (and all its entities)"""
        result = list_delete(name)
        return result


def list_get(name, page=1, sort=None, fields=None, truncate=True):
    """Get all entities of kind"""
    return list(ilist_get(name, page=page, sort=sort, fields=fields, truncate=truncate))


def ilist_get(name, page=1, sort=None, fields=None, truncate=True):
    if page < 1:
        page = 1
    limit = PAGE_SIZE
    offset = (page - 1) * limit
    kwargs = {}
    if sort:
        if not isinstance(sort, list):
            sort = sort.split(",")
        if len(sort) > 0:
            kwargs["order"] = sort
    if fields:
        if not isinstance(fields, list):
            fields = fields.split(",")
        if len(fields) > 0:
            kwargs["projection"] = fields
    if name not in KNOWN_MODELS:
        for entity in db.ilist_entities(name, limit, offset, **kwargs):
            info = item_to_dict(entity, truncate=truncate)
            yield info
    else:
        for instance in KNOWN_MODELS[name].ilist_all(limit, offset, **kwargs):
            info = instance_to_dict(instance, truncate=truncate)
            yield info


def list_post(name, info):
    """Create new entity of kind"""
    # is item id_or_name in info or not?
    # key = item_get_key(name, item)
    # key = db.get_key(name, int(id_or_name), *path_args)
    # entity = db.make_entity(key, **info)
    # db.put_entity(entity)
    raise NotImplementedError("Create new entity of kind")


def list_delete(name):
    """Delete kind (and all its entities)"""
    raise NotImplementedError("Delete kind (and all its entities)")


class ItemAPI(MethodView):
    def get(self, parent, item):
        """Get entity"""
        if parent not in KNOWN_MODELS:
            if parent == "Others":
                return jsonify(home_get(parent))
            kinds_list = get_lists()
            if parent not in kinds_list:
                raise ValueError("Invalid Kind %r" % parent)
        fields = request.args.get("fields", None)
        children = request.args.get("children", True)
        unpickle = request.args.get("unpickle", True)
        result = item_get(
            parent, item, fields=fields, children=children, unpickle=unpickle
        )
        # return individual property of this item!?
        if fields and isinstance(fields, str) and "," not in fields:
            result = result[fields]
            # TODO: specify content-type if available/known
            if isinstance(result, str):
                return result, 200, {"Content-Type": "text/plain"}
            # https://stackoverflow.com/questions/20508788/do-i-need-content-type-application-octet-stream-for-file-download
            if isinstance(result, bytes):
                if parent in KIND_CONFIG and fields in KIND_CONFIG[parent].get(
                    "image", []
                ):
                    return result, 200, {"Content-Type": "image/png"}
                # return result, 200, {"Content-Type": "application/octet-stream"}
            if parent in KIND_CONFIG and fields in KIND_CONFIG[parent].get(
                "pickled", []
            ):
                return jsonify(result)
        return jsonify(result)

    def post(self, parent, item):
        """Create ? in entity (TBD)"""
        info = request.get_json()
        result = item_post(parent, item, info)
        return result

    def put(self, parent, item):
        """Save/replace entity"""
        info = request.get_json()
        result = item_put(parent, item, info)
        return result

    def patch(self, parent, item):
        """Update entity"""
        info = request.get_json()
        result = item_patch(parent, item, info)
        return result

    def delete(self, parent, item):
        """Delete entity"""
        result = item_delete(parent, item)
        return result


def item_get_key(kind, item):
    if kind in ("Path", "Dir", "File"):
        if not item.startswith("/"):
            id_or_name = "/" + item
        else:
            id_or_name = item
        key = db.get_key(kind, id_or_name)
    # elif kind in ("Chunk") and ":" in item:
    elif kind in KIND_CONFIG and KIND_CONFIG[kind].get("parent", None) and ":" in item:
        id_or_name, parent = item.split(":", 1)
        path_args = parent.split(":")
        key = db.get_key(kind, int(id_or_name), *path_args)
    else:
        if item.isdecimal():
            id_or_name = int(item)
        else:
            id_or_name = item
        key = db.get_key(kind, id_or_name)
    return key


def item_get(parent, item, fields=None, children=False, unpickle=False):
    """Get entity"""
    if fields and not isinstance(fields, list):
        fields = fields.split(",")
    key = item_get_key(parent, item)
    # TODO: retrieve with query + key_filter if fields!?
    entity = db.get_entity(key)
    if not entity:
        raise ValueError("Invalid Entity %r" % key)
    if parent not in KNOWN_MODELS:
        info = item_to_dict(entity)
        parent_key = entity.key
    else:
        instance = db.make_instance(parent, entity)
        info = instance_to_dict(instance)
        parent_key = instance.key()
        # if children and parent == "Path" and hasattr(instance, "size"):
        # if parent == "Path" and hasattr(instance, "size"):
        #     info["_children"] = Chunk.list_keys_by_file(instance)
        #     info["_children"] = db.list_entity_keys("Chunk", limit=PAGE_SIZE, ancestor=instance.key())
    if unpickle:
        if parent in KIND_CONFIG:
            pickled_list = KIND_CONFIG[parent].get("pickled", [])
        else:
            # pickled_list = list(info.keys())
            pickled_list = []
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
        result["_key"] = info["_key"]
        # if len(fields) == 1 and fields[0] in info:
        for attr in fields:
            if attr in info:
                result[attr] = info[attr]
        return result
    # handle ancestor
    if children and parent in KIND_CONFIG and KIND_CONFIG[parent].get("children", None):
        child_list = KIND_CONFIG[parent].get("children")
        info["_children"] = {}
        for child in child_list:
            info["_children"][child] = db.list_entity_keys(
                child, limit=PAGE_SIZE, ancestor=parent_key
            )
    # handle ReferenceProperty
    if (
        children
        and parent in KIND_CONFIG
        and KIND_CONFIG[parent].get("references", None)
    ):
        ref_dict = KIND_CONFIG[parent].get("references")
        info["_references"] = {}
        for ref in ref_dict.keys():
            info["_references"][ref] = db.list_entity_keys(
                ref, limit=PAGE_SIZE, filters=[(ref_dict[ref], "=", parent_key)]
            )
    return info


def item_post(parent, item, info):
    """Create ? in entity (TBD)"""
    key = item_get_key(parent, item)
    entity = db.get_entity(key)
    if not entity:
        raise ValueError("Invalid Entity %r" % key)
    raise NotImplementedError("Create ? in entity (TBD)")


def item_put(parent, item, info):
    """Save/replace entity"""
    key = item_get_key(parent, item)
    entity = db.get_entity(key)
    if not entity:
        raise ValueError("Invalid Entity %r" % key)
    # entity.update(info)
    # db.put_entity(entity)
    raise NotImplementedError("Save/replace entity")


def item_patch(parent, item, info):
    """Update entity"""
    key = item_get_key(parent, item)
    entity = db.get_entity(key)
    if not entity:
        raise ValueError("Invalid Entity %r" % key)
    # entity.update(info)
    # db.put_entity(entity)
    raise NotImplementedError("Update entity")


def item_delete(parent, item):
    """Delete entity"""
    key = item_get_key(parent, item)
    # entity = db.get_entity(key)
    # if not entity:
    #     raise ValueError("Invalid Entity %r" % key)
    # db.delete(key)
    raise NotImplementedError("Delete entity")


# TODO: PropAPI to handle specific properties of entities?


if __name__ == "__main__":
    # python3 -m data.api
    app = create_app()
    app.run(host="0.0.0.0", port=8080, use_reloader=False)
