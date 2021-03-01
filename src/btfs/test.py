# (c) 2010 Martin Wendt; see CloudDAV http://clouddav.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
"""
Implementation of a WsgiDAV provider that implements a virtual file system based
on Googles datastore (Bigtable).
"""

import logging

from future import standard_library
from wsgidav.lock_manager import LockManager, lock_string

from btfs.btfs_dav_provider import BTFSResourceProvider
from btfs.memcache_lock_storage import LockStorageMemcache
from data import fs as data_fs

standard_library.install_aliases()


def test():
    logging.info("test.test()")

    logging.getLogger().setLevel(logging.DEBUG)

    # Test data_fs.py
    data_fs.initfs()
    assert data_fs.isdir("/")

    rootpath = "/run_test"
    if data_fs.exists(rootpath):
        logging.info("removing " + rootpath)
        data_fs.rmtree(rootpath)
    assert not data_fs.exists(rootpath)

    data_fs.mkdir(rootpath)
    assert data_fs.isdir(rootpath)

    data = b"file content"
    data_fs.mkdir(rootpath + "/dir1")
    assert data_fs.isdir(rootpath + "/dir1")
    f1 = data_fs.btopen(rootpath + "/dir1/file1.txt", "w")
    f1.write(data)
    f1.close()
    assert data_fs.isfile(rootpath + "/dir1/file1.txt")

    # data_fs.unlink(rootpath+"/dir1/file1.txt")
    # assert not data_fs.isfile(rootpath+"/dir1/file1.txt")

    print("*** data_fs tests passed ***")

    # Test providers
    provider = BTFSResourceProvider()
    lockman = LockManager(LockStorageMemcache())
    provider.set_lock_manager(lockman)
    environ = {"wsgidav.provider": provider}
    environ["wsgidav.auth.user_name"] = "test"
    environ["wsgidav.auth.roles"] = ["editor"]

    resRoot = provider.get_resource_inst(rootpath + "/", environ)
    resRoot.create_collection("folder1")
    assert data_fs.isdir(rootpath + "/folder1")
    assert not data_fs.isfile(rootpath + "/folder1")
    resChild = provider.get_resource_inst(rootpath + "/folder1", environ)
    assert resChild
    resFile = resChild.create_empty_resource("file_empty.txt")
    assert resFile
    assert not data_fs.isdir(rootpath + "/folder1/file_empty.txt")
    assert data_fs.isfile(rootpath + "/folder1/file_empty.txt")
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
    import cProfile
    import io
    import pstats

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
