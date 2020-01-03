# -*- coding: iso-8859-1 -*-

# (c) 2010 Martin Wendt; see CloudDAV http://clouddav.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

import logging
import os
import time
from builtins import str
from pprint import pformat

from flask import Flask, render_template, request

from btfs import sessions
from btfs.auth import AuthorizedUser
from data import db
from data.cache import memcache3
from data.model import Chunk, Dir, File, Path


def db_get_stats(model, limit=1000):
    stats = {
        "kind": model.kind(),
        "properties": model.properties(),
        "count": model.get_count(limit),
    }
    # for name in stats["properties"]:
    #     proptype = type(stats["properties"][name]).__name__
    #     stats["properties"][name] = proptype.replace("google.appengine.ext.", "")
    if stats["count"] == limit:
        stats["count"] = str(limit) + "+"
    return stats


def find_orphans(limit=1000):
    dir_keys = {}
    for item in Dir.ilist_all(1000):
        dir_keys[item.key()] = item
    output = "Orphan Dirs:\n"
    dir_orphans = []
    for item in dir_keys.values():
        if not item.parent_path:
            if item.path != "/":
                output += "No Parent Path: %s\n" % item.path
                dir_orphans.append(item.key())
            continue
        try:
            key = item.parent_path
        except Exception as e:
            output += "Invalid Reference: %s\n" % item.path
            dir_orphans.append(item.key())
            continue
        if key not in dir_keys:
            output += "Unknown Parent: %s\n" % item.path
            dir_orphans.append(item.key())
    output += "Orphan Files:\n"
    file_keys = {}
    file_orphans = []
    for item in File.ilist_all(1000):
        file_keys[item.key()] = item
        try:
            key = item.parent_path
        except Exception as e:
            output += "Invalid Reference: %s\n" % item.path
            file_orphans.append(item.key())
            continue
        if key not in dir_keys:
            output += "Unknown Parent: %s\n" % item.path
            file_orphans.append(item.key())
            continue
        if key in dir_orphans:
            output += "Orphan Dir: %s\n" % item.path
            file_orphans.append(item.key())
            continue
        file_keys[item.key()] = item
    output += "Orphan Chunks:\n"
    # chunk_keys = {}
    chunk_orphans = []
    for item in Chunk.ilist_all(1000, projection=["offset"]):
        try:
            key = item.key().parent
        except Exception as e:
            output += "Invalid Reference: %s\n" % item.key()
            chunk_orphans.append(item.key())
            continue
        if key not in file_keys:
            output += "Unknown File: %s %s\n" % (item.key().parent, item.offset)
            chunk_orphans.append(item.key())
            continue
        if key in file_orphans:
            output += "Orphan File: %s %s\n" % (item.key().parent, item.offset)
            chunk_orphans.append(item.key())
            continue
        # chunk_keys[item.key()] = item
    # TODO: resize files & dirs based on chunk_keys?
    return output, dir_orphans, file_orphans, chunk_orphans


app = Flask(__name__)
app.debug = True

datastore_stats = {}


def get_datastore_stats(reset=False):
    global datastore_stats
    if len(datastore_stats) > 0 and not reset:
        return datastore_stats
    datastore_stats = {}
    # datastore_stats['Stats'] = stats.GlobalStat.list_all(1)
    datastore_stats["Stats"] = {"timestamp": time.time()}
    # for stat in stats.KindPropertyNamePropertyTypeStat.list_all():
    #    datastore_stats['Stats'].append(stat)
    datastore_stats["Path"] = db_get_stats(Path)
    datastore_stats["Dir"] = db_get_stats(Dir)
    datastore_stats["File"] = db_get_stats(File)
    datastore_stats["Chunk"] = db_get_stats(Chunk)
    datastore_stats["AuthorizedUser"] = db_get_stats(AuthorizedUser)
    datastore_stats["AuthSession"] = db_get_stats(sessions.AuthSession)
    return datastore_stats


datastore_samples = {}


def get_datastore_samples(cls, reset=False, limit=5):
    global datastore_samples
    if cls is None and reset:
        datastore_samples = {}
        return
    kind = cls._kind
    if kind in datastore_samples and not reset:
        return datastore_samples[kind]
    datastore_samples[kind] = []
    for instance in cls.ilist_all(limit):
        info = instance.to_dict(True)
        if "data" in info and len(info["data"]) > 100:
            info["data"] = "%s... (%s bytes)" % (info["data"][:100], len(info["data"]))
        datastore_samples[kind].append(info)
    return datastore_samples[kind]


@app.route("/_admin/")
@sessions.flask_authorize("admin")
def admin_view():
    session = sessions.get_current_session(request.environ)
    # if not session.has_role("admin"):
    #     output = (
    #         "You need to login as administrator <a href='%s'>Login</a>"
    #         % sessions.LOGIN_URL
    #     )
    #     return output
    qs = request.query_string
    if not isinstance(qs, str):
        qs = qs.decode("utf-8")
    logging.warning("AdminHandler.get: %s" % qs)
    actions = {
        "run_tests": run_tests,
        "clear_cache": clear_cache,
        "reset_stats": reset_stats,
        "clear_datastore": clear_datastore,
        "expired_sessions": expired_sessions,
        "check_orphans": check_orphans,
        "delete_orphans": delete_orphans,
    }
    # Handle admin commands
    if qs in actions:
        return actions[qs]()
    elif qs != "":
        raise NotImplementedError("Invalid command: %s" % qs)
    # Show admin page
    if session.is_user():
        url = sessions.LOGOUT_URL
        url_linktext = "Logout"
    else:
        url = sessions.LOGIN_URL
        url_linktext = "Login"
    env = []
    for k, v in list(os.environ.items()):
        env.append("%s: '%s'" % (k, v))
    stats = get_datastore_stats()
    paths = get_datastore_samples(Path)
    chunks = get_datastore_samples(Chunk)
    userlist = get_datastore_samples(AuthorizedUser)
    sessionlist = get_datastore_samples(sessions.AuthSession)
    nickname = "stranger"
    if session.is_user():
        nickname = session.nickname
    template_values = {
        "nickname": nickname,
        "url": url,
        "url_linktext": url_linktext,
        "memcache_stats": pformat(memcache3.get_stats()),
        "datastore_stats": pformat(stats),
        "path_samples": pformat(paths),
        "chunk_samples": pformat(chunks),
        "user_samples": pformat(userlist),
        "session_samples": pformat(sessionlist),
        "environment_dump": "\n".join(env),
        "request_env_dump": pformat(request.environ),
    }

    return render_template("admin.html", **template_values)


def run_tests():
    from btfs.test import test

    test()
    output = "Tests run! <a href='?'>Back</a>"
    return output


def clear_cache():
    logging.warning("clear_cache: memcache3.reset()")
    memcache3.reset()
    output = "Memcache deleted! <a href='?'>Back</a>"
    return output


def reset_stats():
    logging.warning("reset_stats: get_datastore_stats(True)")
    get_datastore_stats(True)
    output = "Stats reset! <a href='?'>Back</a>"
    return output


def clear_datastore():
    logging.warning("clear_datastore: data_fs.rmtree('/')")
    from data import fs as data_fs

    # cannot use rmtree("/"), because it prohibits '/'
    try:
        data_fs.rmtree("/")
    except Exception as e:
        logging.warning(e)
    # data_fs.getdir("/").delete(recursive=True)
    memcache3.reset()
    data_fs.initfs()
    get_datastore_stats(True)
    get_datastore_samples(None, True)
    output = "Removed '/'. <a href='?'>Back</a>"
    return output


def expired_sessions():
    logging.warning("expired_sessions: AuthSession.gc()")
    result = sessions.AuthSession.gc()
    output = (
        "Found %s expired sessions to clear (more than %s day old). <a href='?'>Back</a>"
        % (result, sessions.EXPIRE_DAYS)
    )
    if result > 0:
        get_datastore_stats(True)
        get_datastore_samples(sessions.AuthSession, True)
    return output


def check_orphans():
    output = "Checking orphans. <a href='?'>Back</a><pre>"
    result, dir_orphans, file_orphans, chunk_orphans = find_orphans()
    output += result
    output += "</pre>Total orphans: %s dirs, %s files, %s chunks" % (
        len(dir_orphans),
        len(file_orphans),
        len(chunk_orphans),
    )
    if len(dir_orphans) + len(file_orphans) + len(chunk_orphans) > 0:
        output += " - <a href='?delete_orphans'>Delete orphans?</a>"
    return output


def delete_orphans():
    output, dir_orphans, file_orphans, chunk_orphans = find_orphans()
    total = 0
    if len(dir_orphans) > 0:
        total += len(dir_orphans)
        db.delete(dir_orphans)
    if len(file_orphans) > 0:
        total += len(file_orphans)
        db.delete(file_orphans)
    if len(chunk_orphans) > 0:
        total += len(chunk_orphans)
        db.delete(chunk_orphans)
    if total > 0:
        get_datastore_stats(True)
    if len(dir_orphans) > 0 or len(file_orphans) > 0:
        get_datastore_samples(Path, True)
    if len(chunk_orphans) > 0:
        get_datastore_samples(Chunk, True)
    output = "Deleted %s orphans. <a href='?'>Back</a>" % total
    return output


@app.template_filter()
def is_key(key):
    if "Key" in key.__class__.__name__:
        return True
    return False


@app.template_filter()
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


PAGE_SIZE = 10


@app.template_global()
def kind_pager(kind=None, page=1):
    output = ""
    if kind is None:
        return output
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
        output += '<a href="%s">First Page</a>' % base_url
    else:
        output += "First Page"
    if page > 2:
        output += ' - <a href="%s">Previous Page</a>' % (page_url + str(page - 1))
    elif page > 1:
        output += ' - <a href="%s">Previous Page</a>' % base_url
    else:
        output += " - Previous Page"
    stats = get_datastore_stats()
    if kind not in stats:
        output += ' - <a href="%s">Next Page?</a>' % (page_url + str(page + 1))
        return output
    count = stats[kind]["count"]
    max_page = int(count / PAGE_SIZE) + 1
    if page < max_page:
        output += ' - <a href="%s">Next Page</a>' % (page_url + str(page + 1))
        output += ' - <a href="%s">Last Page</a>' % (page_url + str(max_page))
    else:
        output += " - Last Page"
    return output


@app.route("/_admin/data/")
@app.route("/_admin/data/<string:kind>/")
@app.route("/_admin/data/<string:kind>/<path:key>")
@sessions.flask_authorize("admin")
def data_view(kind=None, key=None):
    known_kinds = {
        "Path": Path,
        "Dir": Dir,
        "File": File,
        "Chunk": Chunk,
        "AuthorizedUser": AuthorizedUser,
        "AuthSession": sessions.AuthSession,
    }
    kinds_list = sorted(known_kinds.keys())
    kinds_list.append("Others")
    if kind is not None and kind not in known_kinds:
        other_kinds = sorted(db.list_kinds())
        for item in other_kinds:
            if item not in kinds_list:
                kinds_list.append(item)
        if kind not in other_kinds:
            kind = None
    data_url = "/_admin/data"

    if not kind and not key:
        reset = request.args.get("reset", False)
        stats = get_datastore_stats(reset)
        return render_template(
            "data_view.html",
            data_url=data_url,
            kinds=kinds_list,
            kind=kind,
            stats=stats,
        )

    if kind and not key:
        sort = request.args.get("sort", None)
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
        limit = PAGE_SIZE
        offset = (page - 1) * limit
        columns = []
        rows = []
        kwargs = {}
        if sort:
            kwargs["order"] = [sort]
        if kind not in known_kinds:
            for entity in db.ilist_entities(kind, limit, offset, **kwargs):
                info = dict(entity)
                info["__key__"] = entity.key
                if entity.key.parent:
                    info["parent"] = entity.key.parent
                if len(columns) < 1:
                    columns = sorted(info.keys())
                rows.append(info)
        else:
            for instance in known_kinds[kind].ilist_all(limit, offset, **kwargs):
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
            data_url=data_url,
            kinds=kinds_list,
            kind=kind,
            sort=sort,
            page=page,
            columns=columns,
            rows=rows,
        )

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
    if kind not in known_kinds:
        info = dict(entity)
        info["__key__"] = entity.key
        if entity.key.parent:
            info["parent"] = entity.key.parent
    else:
        instance = db.make_instance(kind, entity)
        info = instance.to_dict(True)
    return render_template(
        "data_key.html",
        data_url=data_url,
        kinds=kinds_list,
        kind=kind,
        key=key,
        info=info,
    )
