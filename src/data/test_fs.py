#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: https://opensource.org/licenses/mit-license.php
#
import logging
import os

from . import fs as data_fs

count = 0


def make_tree(parent, depth=0):
    global count
    dirname = os.path.basename(parent).replace("test", "dir")
    filename = dirname.replace("dir", "file")
    data = b"x" * 1024
    for i in range(1, 10):
        name = f"{filename}.{i}.txt"
        path = os.path.join(parent, name)
        print("  " * depth, path)
        f1 = data_fs.btopen(path, "w")
        f1.write(data)
        f1.close()
        assert data_fs.isfile(path)
        count += 1
    if depth > 1:
        return
    for i in range(1, 10):
        name = f"{dirname}.{i}"
        path = os.path.join(parent, name)
        print("  " * depth, path)
        data_fs.mkdir(path)
        assert data_fs.isdir(path)
        make_tree(path, depth + 1)
    return count


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

    # make_tree("/test", 0)
    # print(count)


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
    # print(make_tree('/test'))
    test()
    # profile_test()
