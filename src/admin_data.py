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
from data import db, views, api
from data.cache import memcache3
from data.model import Chunk, Dir, File, Path


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
# add datastore view functions, template filters and global functions
authorize_wrap = sessions.flask_authorize("admin")
views.configure_app(app, "/_admin/data", authorize_wrap)


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
    stats = api.get_stats()
    nickname = "stranger"
    if session.is_user():
        nickname = session.nickname
    template_values = {
        "nickname": nickname,
        "url": url,
        "url_linktext": url_linktext,
        "memcache_stats": pformat(memcache3.get_stats()),
        "datastore_stats": pformat(stats),
        "environment_dump": "\n".join(env),
        "request_env_dump": pformat(request.environ),
    }

    return render_template("admin_data.html", **template_values)


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
    logging.warning("reset_stats: api.get_stats(True)")
    api.get_stats(True)
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
    api.get_stats(True)
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
        if result == 500:
            output += " <a href='?expired_sessions'>Delete more...</a>"
        api.get_stats(True)
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
        api.get_stats(True)
    output = "Deleted %s orphans. <a href='?'>Back</a>" % total
    return output
