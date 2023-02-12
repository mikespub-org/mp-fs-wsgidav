#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# (c) 2010 Martin Wendt; see CloudDAV http://clouddav.googlecode.com/
#
# The original source for this module was taken from gaedav:
# (c) 2009 Haoyu Bai (http://gaedav.google.com/).
"""
File system operations.
"""

import io
import logging
import time

from .model import Dir, File, Path

# from btfs import memcash


def initfs(backend="firestore", readonly=False):
    """
    Make sure fire.fs already inited.
    (e.g. there's a '/' and '/dav' collection in db).
    """
    logging.debug("fire.fs.initfs")
    if backend not in ("firestore"):
        raise NotImplementedError("Backend '%s' is not supported." % backend)
    if not isdir("/"):
        logging.info("fire.fs.initfs: mkdir '/'")
        mkdir("/")
    if not isdir("/dav"):
        logging.info("fire.fs.initfs: mkdir '/dav'")
        mkdir("/dav")
    return


# @memcash.cache(ttl=10)  # cache function result for 10 seconds
def _getresource(path):
    """Return a model.Dir or model.File object for `path`.

    `path` may be an existing Dir/File entity.
    Since _getresource is called by most other functions in the `fire.fs` module,
    this allows the DAV provider to pass a cached resource, thus implementing
    a simple per-request caching, like in::

        statresults = fire.fs.stat(self.pathEntity)

    Return None, if path does not exist.
    """
    if type(path) in (Dir, File):
        logging.debug("_getresource(%r): request cache HIT" % path.path)
        return path
    # logging.info("_getresource(%r)" % path)
    p = Path.retrieve(path)
    assert p is None or type(p) in (Dir, File)
    return p


def getdir(s):
    p = _getresource(s)
    if type(p) is Dir:
        return p
    return None


def getfile(s):
    p = _getresource(s)
    if type(p) is File:
        return p
    return None


def isdir(s):
    p = getdir(s)
    return p is not None


def isfile(s):
    p = getfile(s)
    return p is not None


def exists(s):
    return _getresource(s) is not None


def stat(s):
    def epoch(pb):
        # return time.mktime(tm.utctimetuple())
        if hasattr(pb, "timestamp_pb"):
            pb = pb.timestamp_pb()
        return pb.seconds + float(pb.nanos / 1000000000.0)

    p = _getresource(s)
    doc = p.get_doc()
    if doc and doc.exists:
        size = doc.to_dict().get("size", 0)
        mtime = epoch(doc.update_time)
        ctime = epoch(doc.create_time)
    else:
        now = time.time()
        size = 0
        mtime = now
        ctime = now
    atime = mtime

    def itemgetter(n):
        return lambda self: self[n]

    # run
    #   collections.namedtuple('stat_result', 'st_size st_atime st_mtime st_ctime', verbose=True)
    # to get the following class
    class stat_result(tuple):
        "stat_result(st_size, st_atime, st_mtime, st_ctime)"

        __slots__ = ()

        _fields = ("st_size", "st_atime", "st_mtime", "st_ctime")

        def __new__(cls, st_size, st_atime, st_mtime, st_ctime):
            return tuple.__new__(cls, (st_size, st_atime, st_mtime, st_ctime))

        @classmethod
        def _make(cls, iterable, new=tuple.__new__, len=len):
            "Make a new stat_result object from a sequence or iterable"
            result = new(cls, iterable)
            if len(result) != 4:
                raise TypeError("Expected 4 arguments, got %d" % len(result))
            return result

        def __repr__(self):
            return (
                "stat_result(st_size=%r, st_atime=%r, st_mtime=%r, st_ctime=%r)" % self
            )

        # def _asdict(t):
        #     'Return a new dict which maps field names to their values'
        #     return {'st_size': t[0], 'st_atime': t[1], 'st_mtime': t[2], 'st_ctime': t[3]}

        def _replace(self, **kwds):
            "Return a new stat_result object replacing specified fields with new values"
            result = self._make(
                list(
                    map(kwds.pop, ("st_size", "st_atime", "st_mtime", "st_ctime"), self)
                )
            )
            if kwds:
                raise ValueError("Got unexpected field names: %r" % list(kwds.keys()))
            return result

        def __getnewargs__(self):
            return tuple(self)

        st_size = property(itemgetter(0))
        st_atime = property(itemgetter(1))
        st_mtime = property(itemgetter(2))
        st_ctime = property(itemgetter(3))

    return stat_result(size, atime, mtime, ctime)


def mkdir(s):
    p = Dir.new(s)
    return p


def rmdir(s):
    p = getdir(s)
    p.delete(recursive=False)
    return


def rmtree(s):
    p = getdir(s)
    p.delete(recursive=True)
    return


def mkfile(s):
    p = File.new(s)
    return p


def copyfile(s, d):
    # Path.copyfile(s, d)
    src = Path._getresource(s)
    if src is None:
        raise ValueError("source not found %r" % s)
    if not src.isfile():
        raise ValueError("source not a File %r" % s)
    dst = Path._getresource(d)
    if dst is None:
        dst = File.new(path=d)
    if not dst.isfile():
        raise ValueError("destination not a File %r" % d)
    # TODO: copyfile2 without downloading/uploading chunk data at all?
    size = dst.iput_content(src.iget_content())
    # raise, if not exists:
    # sio = btopen(s, "rb")
    # overwrite destination, if exists:
    # dio = btopen(d, "wb")
    # while True:
    #     buf = sio.read(8 * 1024)
    #     if not buf:
    #         break
    #     dio.write(buf)
    # dio.close()
    # sio.close()
    return size


def unlink(s):
    f = getfile(s)
    f.delete()
    return


def btopen(s, mode="r"):
    """Open the file (eg. return a BtIO object)"""
    f = getfile(s)
    if f is None:
        # Create targtet file, but only in write mode
        if "w" not in mode and "a" not in mode and "x" not in mode:
            raise ValueError("source not found %r" % s)
        f = File.new(path=s)
    io = BtIO(f, mode)
    return io


def listdir(s):
    p = getdir(s)
    # path_str = [c.basename(c.path).encode('utf-8') for c in p.get_content()]
    path_str = [c.basename(c.path) for c in p.get_content()]
    return path_str


def scandir(s):
    p = getdir(s)
    return p.get_content()


def stop_cache(stop=False):
    Path.cache.stop_cache = stop


# ===============================================================================
# BtIO
# ===============================================================================
class BtIO(io.BytesIO):
    """
    Bigtable file IO object
    """

    def __init__(self, btfile, mode):
        self.btfile = btfile
        self.mode = mode
        io.BytesIO.__init__(self, btfile.get_content())
        return

    def is_readonly(self):
        return (
            "w" not in self.mode
            and "a" not in self.mode
            and "x" not in self.mode
            and "+" not in self.mode
        )

    def flush(self):
        io.BytesIO.flush(self)
        if not self.is_readonly():
            self.btfile.put_content(self.getvalue())
        return

    def close(self):
        self.flush()
        io.BytesIO.close(self)
        return

    def __del__(self):
        try:
            if not self.closed:
                self.close()
        except AttributeError:
            pass
