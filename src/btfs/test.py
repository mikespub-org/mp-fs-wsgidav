# -*- coding: iso-8859-1 -*-
# (c) 2010 Martin Wendt; see CloudDAV http://clouddav.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
"""
Implementation of a WsgiDAV provider that implements a virtual file system based
on Googles datastore (Bigtable).
"""
from __future__ import print_function

import logging
import os

from future import standard_library
from wsgidav.lock_manager import LockManager, lock_string

from btfs import bt_fs
from btfs.btfs_dav_provider import BTFSResourceProvider
from btfs.memcache_lock_storage import LockStorageMemcache

standard_library.install_aliases()

count = 0


def make_tree(parent, depth):
    global count
    dirname = os.path.basename(parent).replace("test", "dir")
    filename = dirname.replace("dir", "file")
    data = b"x" * 1024
    for i in range(1, 10):
        name = "%s.%s.txt" % (filename, i)
        path = os.path.join(parent, name)
        print("  " * depth, path)
        f1 = bt_fs.btopen(path, "w")
        f1.write(data)
        f1.close()
        assert bt_fs.isfile(path)
        count += 1
    if depth > 1:
        return
    for i in range(1, 10):
        name = "%s.%s" % (dirname, i)
        path = os.path.join(parent, name)
        print("  " * depth, path)
        bt_fs.mkdir(path)
        assert bt_fs.isdir(path)
        make_tree(path, depth + 1)


def test():
    logging.info("test.test()")

    logging.getLogger().setLevel(logging.DEBUG)

    # Test bt_fs.py
    bt_fs.initfs()
    assert bt_fs.isdir("/")

    rootpath = "/test"
    if bt_fs.exists(rootpath):
        logging.info("removing " + rootpath)
        bt_fs.rmtree(rootpath)
    assert not bt_fs.exists(rootpath)

    bt_fs.mkdir(rootpath)
    assert bt_fs.isdir(rootpath)

    data = b"file content"
    bt_fs.mkdir(rootpath + "/dir1")
    assert bt_fs.isdir(rootpath + "/dir1")
    f1 = bt_fs.btopen(rootpath + "/dir1/file1.txt", "w")
    f1.write(data)
    f1.close()
    assert bt_fs.isfile(rootpath + "/dir1/file1.txt")

    # bt_fs.unlink(rootpath+"/dir1/file1.txt")
    # assert not bt_fs.isfile(rootpath+"/dir1/file1.txt")

    print("*** bt_fs tests passed ***")

    make_tree("/test", 0)
    print(count)

    # Test providers
    provider = BTFSResourceProvider()
    lockman = LockManager(LockStorageMemcache())
    provider.set_lock_manager(lockman)
    environ = {"wsgidav.provider": provider}

    resRoot = provider.get_resource_inst(rootpath + "/", environ)
    resRoot.create_collection("folder1")
    assert bt_fs.isdir(rootpath + "/folder1")
    assert not bt_fs.isfile(rootpath + "/folder1")
    resChild = provider.get_resource_inst(rootpath + "/folder1", environ)
    assert resChild
    resFile = resChild.create_empty_resource("file_empty.txt")
    assert resFile
    assert not bt_fs.isdir(rootpath + "/folder1/file_empty.txt")
    assert bt_fs.isfile(rootpath + "/folder1/file_empty.txt")
    # write
    data = b"x" * 1024
    res = resChild.create_empty_resource("file2.txt")
    f = res.begin_write()
    f.write(data)
    f.close()
    # copy
    res = provider.get_resource_inst(rootpath + "/folder1/file2.txt", environ)
    res.copy_move_single(rootpath + "/folder1/file2_copy.txt", False)

    res = provider.get_resource_inst(rootpath + "/folder1/file2_copy.txt", environ)
    f = res.get_content()
    assert data == f.read()
    f.close()

    print("*** provider tests passed ***")

    lock = provider.lock_manager.acquire(
        rootpath + "/folder1",
        "write",
        "exclusive",
        "infinity",
        b"test_owner",
        timeout=100,
        principal="martin",
        token_list=[],
    )
    assert lock["root"] == rootpath + "/folder1"
    lock = provider.lock_manager.get_lock(lock["token"])
    print(lock_string(lock))
    assert lock["root"] == rootpath + "/folder1"

    locklist = provider.lock_manager.get_indirect_url_lock_list(
        rootpath + "/folder1/file2.txt"
    )
    print(locklist)
    assert len(locklist) == 1

    print("*** lock tests passed ***")


def profile_test():
    # This is the main function for profiling
    import cProfile, pstats, io

    prof = cProfile.Profile()
    prof = prof.runctx("test()", globals(), locals())
    stream = io.StringIO()
    stats = pstats.Stats(prof, stream=stream)
    # stats.sort_stats("time")  # Or cumulative
    stats.sort_stats("cumulative")  # Or time
    stats.print_stats(80)  # 80 = how many to print
    # The rest is optional.
    # stats.print_callees()
    # stats.print_callers()
    logging.info("Profile data:\n%s", stream.getvalue())
    print("*** See log for profiling info ***")


if __name__ == "__main__":
    # test()
    profile_test()
