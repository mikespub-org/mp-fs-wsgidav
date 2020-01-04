#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
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
from fire import db

# from fire.cache import memcache3
# from fire.model import Chunk, Dir, File, Path


def db_get_stats(coll_ref, limit=1000):
    count = len(list(coll_ref.list_documents()))
    stats = {
        "coll_ref": coll_ref,
        # "properties": {},
        "count": count,
    }
    # for name in stats["properties"]:
    #     proptype = type(stats["properties"][name]).__name__
    #     stats["properties"][name] = proptype.replace("google.appengine.ext.", "")
    if stats["count"] == limit:
        stats["count"] = str(limit) + "+"
    return stats


"""
def find_orphans(limit=1000):
    dir_refs = {}
    for item in Dir.ilist_all(1000):
        dir_refs[item.ref()] = item
    output = "Orphan Dirs:\n"
    dir_orphans = []
    for item in dir_refs.values():
        if not item.parent_path:
            if item.path != "/":
                output += "No Parent Path: %s\n" % item.path
                dir_orphans.append(item.ref())
            continue
        try:
            ref = item.parent_path
        except Exception as e:
            output += "Invalid Reference: %s\n" % item.path
            dir_orphans.append(item.ref())
            continue
        if ref not in dir_refs:
            output += "Unknown Parent: %s\n" % item.path
            dir_orphans.append(item.ref())
    output += "Orphan Files:\n"
    file_refs = {}
    file_orphans = []
    for item in File.ilist_all(1000):
        file_refs[item.ref()] = item
        try:
            ref = item.parent_path
        except Exception as e:
            output += "Invalid Reference: %s\n" % item.path
            file_orphans.append(item.ref())
            continue
        if ref not in dir_refs:
            output += "Unknown Parent: %s\n" % item.path
            file_orphans.append(item.ref())
            continue
        if ref in dir_orphans:
            output += "Orphan Dir: %s\n" % item.path
            file_orphans.append(item.ref())
            continue
        file_refs[item.ref()] = item
    output += "Orphan Chunks:\n"
    # chunk_refs = {}
    chunk_orphans = []
    for item in Chunk.ilist_all(1000, projection=["offset"]):
        try:
            ref = item.ref().parent
        except Exception as e:
            output += "Invalid Reference: %s\n" % item.ref()
            chunk_orphans.append(item.ref())
            continue
        if ref not in file_refs:
            output += "Unknown File: %s %s\n" % (item.ref().parent, item.offset)
            chunk_orphans.append(item.ref())
            continue
        if ref in file_orphans:
            output += "Orphan File: %s %s\n" % (item.ref().parent, item.offset)
            chunk_orphans.append(item.ref())
            continue
        # chunk_refs[item.ref()] = item
    # TODO: resize files & dirs based on chunk_refs?
    return output, dir_orphans, file_orphans, chunk_orphans
"""

app = Flask(__name__)
app.debug = True

firestore_stats = {}


def get_firestore_stats(reset=False):
    global firestore_stats
    if len(firestore_stats) > 0 and not reset:
        return firestore_stats
    firestore_stats = {}
    # firestore_stats['Stats'] = stats.GlobalStat.list_all(1)
    firestore_stats["Stats"] = {"timestamp": time.time()}
    # for stat in stats.collPropertyNamePropertyTypeStat.list_all():
    #    firestore_stats['Stats'].append(stat)
    # firestore_stats["Path"] = db_get_stats(Path)
    # firestore_stats["Dir"] = db_get_stats(Dir)
    # firestore_stats["File"] = db_get_stats(File)
    # firestore_stats["Chunk"] = db_get_stats(Chunk)
    # firestore_stats["AuthorizedUser"] = db_get_stats(AuthorizedUser)
    # firestore_stats["AuthSession"] = db_get_stats(sessions.AuthSession)
    for coll_ref in db.list_root():
        firestore_stats[coll_ref.id] = db_get_stats(coll_ref)
    return firestore_stats


"""
firestore_samples = {}


def get_firestore_samples(cls, reset=False, limit=5):
    global firestore_samples
    if cls is None and reset:
        firestore_samples = {}
        return
    coll = cls._coll
    if coll in firestore_samples and not reset:
        return firestore_samples[coll]
    firestore_samples[coll] = []
    for instance in cls.ilist_all(limit):
        info = instance.to_dict(True)
        if "data" in info and len(info["data"]) > 100:
            info["data"] = "%s... (%s bytes)" % (info["data"][:100], len(info["data"]))
        firestore_samples[coll].append(info)
    return firestore_samples[coll]
"""


@app.route("/_admin/")
# @sessions.flask_authorize("admin")
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
        "clear_firestore": clear_firestore,
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
    stats = get_firestore_stats()
    # paths = get_firestore_samples(Path)
    # chunks = get_firestore_samples(Chunk)
    # userlist = get_firestore_samples(AuthorizedUser)
    # sessionlist = get_firestore_samples(sessions.AuthSession)
    nickname = "stranger"
    if session.is_user():
        nickname = session.nickname
    template_values = {
        "nickname": nickname,
        "url": url,
        "url_linktext": url_linktext,
        # "memcache_stats": pformat(memcache3.get_stats()),
        "firestore_stats": pformat(stats),
        # "path_samples": pformat(paths),
        # "chunk_samples": pformat(chunks),
        # "user_samples": pformat(userlist),
        # "session_samples": pformat(sessionlist),
        "environment_dump": "\n".join(env),
        "request_env_dump": pformat(request.environ),
    }

    return render_template("admin_fire.html", **template_values)


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
    logging.warning("reset_stats: get_firestore_stats(True)")
    get_firestore_stats(True)
    output = "Stats reset! <a href='?'>Back</a>"
    return output


def clear_firestore():
    logging.warning("clear_firestore: fire_fs.rmtree('/')")
    from fire import fs as fire_fs

    # cannot use rmtree("/"), because it prohibits '/'
    try:
        fire_fs.rmtree("/")
    except Exception as e:
        logging.warning(e)
    # fire_fs.getdir("/").delete(recursive=True)
    memcache3.reset()
    fire_fs.initfs()
    get_firestore_stats(True)
    # get_firestore_samples(None, True)
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
        get_firestore_stats(True)
        # get_firestore_samples(sessions.AuthSession, True)
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
        get_firestore_stats(True)
    # if len(dir_orphans) > 0 or len(file_orphans) > 0:
    #     get_firestore_samples(Path, True)
    # if len(chunk_orphans) > 0:
    #     get_firestore_samples(Chunk, True)
    output = "Deleted %s orphans. <a href='?'>Back</a>" % total
    return output


@app.template_filter()
def is_ref(ref):
    if "Reference" in ref.__class__.__name__:
        return True
    return False


@app.template_filter()
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


@app.template_filter()
def show_date(timestamp, fmt="%Y-%m-%d %H:%M:%S"):
    if not timestamp:
        return
    return time.strftime(fmt, time.gmtime(timestamp))


FIRE_URL = "/_admin/fire"
PAGE_SIZE = 10
COLLS_LIST = []


@app.template_global()
def coll_pager(coll=None, page=1):
    output = ""
    if coll is None:
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
    stats = get_firestore_stats()
    if coll not in stats:
        output += ' - <a href="%s">Next Page?</a>' % (page_url + str(page + 1))
        return output
    count = stats[coll]["count"]
    max_page = int(count / PAGE_SIZE) + 1
    if page < max_page:
        output += ' - <a href="%s">Next Page</a>' % (page_url + str(page + 1))
        output += ' - <a href="%s">Last Page</a>' % (page_url + str(max_page))
    else:
        output += " - Last Page"
    return output


def get_colls(reset=False):
    global COLLS_LIST
    if len(COLLS_LIST) > 0 and not reset:
        return COLLS_LIST
    firestore_colls = []
    for coll_ref in db.list_root():
        firestore_colls.append(coll_ref.id)
    COLLS_LIST = sorted(firestore_colls)
    return COLLS_LIST


@app.route("/_admin/fire/")
@app.route("/_admin/fire/<string:coll>/")
@app.route("/_admin/fire/<string:coll>/<path:ref>")
# @sessions.flask_authorize("admin")
def fire_view(coll=None, ref=None):
    known_colls = get_colls()
    colls_list = sorted(known_colls)
    # colls_list.append("Others")
    if coll is not None and coll not in known_colls:
        # other_colls = []
        # for coll_ref in db.list_root():
        #     other_colls.append(coll_ref.id)
        # for item in other_colls:
        #     if item not in colls_list:
        #         colls_list.append(item)
        # if coll not in other_colls:
        #     coll = None
        coll = None

    if not coll and not ref:
        reset = request.args.get("reset", False)
        stats = get_firestore_stats(reset)
        return render_template(
            "fire_view.html",
            fire_url=FIRE_URL,
            colls=COLLS_LIST,
            coll=None,
            stats=stats,
        )

    # subcollections always end with / - see ref_link and templates/fire_doc.html
    if ref is not None and ref.endswith("/"):
        coll += "/" + ref[:-1]
        ref = None

    if coll and not ref:
        return fire_coll_view(coll)

    return fire_doc_view(coll, ref)


def fire_coll_view(coll):
    sort = request.args.get("sort", None)
    page = int(request.args.get("page", 1))
    if page < 1:
        page = 1
    limit = PAGE_SIZE
    offset = (page - 1) * limit
    columns = []
    rows = []
    parent = None
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
            info["data"] = "%s... (%s bytes)" % (
                info["data"][:20],
                len(info["data"]),
            )
        rows.append(info)
    return render_template(
        "fire_coll.html",
        fire_url=FIRE_URL,
        colls=COLLS_LIST,
        coll=coll,
        sort=sort,
        page=page,
        columns=columns,
        rows=rows,
        parent=parent,
    )


def fire_doc_view(coll, ref):
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
        colls=COLLS_LIST,
        coll=coll,
        ref=doc_ref,
        info=info,
        subcolls=subcolls,
        parent=parent,
    )
