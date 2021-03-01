#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# (c) 2010 Martin Wendt; see CloudDAV http://clouddav.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
#
# The original source for this module was taken from gaedav:
# (c) 2009 Haoyu Bai (http://gaedav.google.com/).


import datetime
import hashlib
import logging
import os.path

from . import db
from .tree import get_structure

# from pathlib import PurePath

# from .cache import NamespacedCache

# cached_resource = NamespacedCache("resource")

DO_EXPENSIVE_CHECKS = False
# DO_EXPENSIVE_CHECKS = True


class DocModel:
    _tree = get_structure("flat", db.get_client())
    # _tree = get_structure("hash", db.get_client())

    def __init__(self, _from_doc=False, **kwargs):
        # _from_doc = kwargs.pop('_from_doc', False)
        if _from_doc is not False:
            self._doc = _from_doc
            self._doc_ref = self._doc.reference
            if self._tree.with_path:
                self.path = self._doc.get("path")
            else:
                self.path = self._tree.convert_ref_to_path(self._doc_ref.path)
        else:
            self._init_doc_ref(**kwargs)

    def _init_doc_ref(self, **kwargs):
        self.path = kwargs.pop("path", None)
        self._doc_ref = self._tree.get_doc_ref(self.path)
        self._doc = None

    def get_doc(self):
        if self._doc is None:
            if self._doc_ref is not None:
                self._doc = self._doc_ref.get()
        return self._doc

    def is_saved(self):
        doc = self.get_doc()
        if not doc or not doc.exists:
            return False
        return True

    @classmethod
    def from_doc(cls, doc):
        return cls(_from_doc=doc)

    @classmethod
    def class_name(cls):
        return cls.__name__


# TODO: may apply the technique described here:
# http://code.google.com/appengine/docs/python/datastore/keysandentitygroups.html

# ===============================================================================
# Path
# ===============================================================================
# class Path(db.Model):
# class Path(db.PolyModel):
# class Path(PurePath):
class Path(DocModel):
    """Derived from PolyModel, so we can perform queries on objects of the parent class"""

    # path = db.StringProperty(required=True)
    # size = db.IntegerProperty(required=True, default=0) # cache the size of content, 0 for dir
    # create_time = db.DateTimeProperty(required=True, auto_now_add = True)
    # modify_time = db.DateTimeProperty(required=True, auto_now = True)
    _kind = "Path"
    _exclude_from_indexes = None
    _auto_now_add = ["create_time"]
    _auto_now = ["modify_time"]

    # cache = cached_resource

    def _init_entity(self, **kwargs):
        super()._init_entity(**kwargs)
        now = datetime.datetime.now(datetime.timezone.utc)
        template = {
            "path": "",
            "size": 0,
            "create_time": now,
            "modify_time": now,
        }
        for key in template:
            self._entity.setdefault(key, template[key])

    def set_key(self):
        if len(self.path) > 128:
            self._entity.key = self._entity.key.completed_key(
                hashlib.md5(self.path.encode("utf-8")).hexdigest()
            )
        else:
            self._entity.key = self._entity.key.completed_key(self.path)

    def put(self):
        logging.debug("Path.put(%r)" % (self.path))
        if not self.is_saved():
            self.set_key()
        db.Model.put(self)
        # self.cache.set(self.path, self)
        # self.cache.del_list(os.path.dirname(self.path))
        return

    def delete(self):
        logging.debug("Path.delete(%r)" % (self.path))
        if self.path == "/":
            raise RuntimeError("Though shalt not delete root")
        # self.cache.delete(self.path)
        # self.cache.del_list(os.path.dirname(self.path))
        # return db.Model.delete(self)
        if self._doc_ref is not None:
            return self._doc_ref.delete()
        raise RuntimeError("Invalid doc_ref to delete for path: %r" % self.path)
        return

    def __repr__(self):
        return "{}('{}')".format(type(self).class_name(), self.path)

    def isdir(self):
        return type(self) is Dir

    def isfile(self):
        return type(self) is File

    @classmethod
    def normalize(cls, p):
        """
        /foo/bar/ -> /foo/bar
        / -> /
        // -> /
        """
        # if not isinstance(p, unicode):
        #     logging.debug("Path.normalize: encoding str %s to unicode.", repr(p))
        #     p = str.decode(p, 'utf-8')
        if not isinstance(p, str):
            p = p.decode("utf-8")
        result = os.path.normpath(p)
        # mw: added for Windows:
        result = result.replace("\\", "/")
        result = result.replace("//", "/")
        # if not isinstance(result, unicode):
        #     result = result.decode('utf-8')
        if p != result:
            logging.debug(f"Path.normalize({p!r}): {result!r}.")
        return result

    @classmethod
    def basename(cls, p):
        return os.path.basename(p)

    @classmethod
    def get_parent_path(cls, p):
        """
        /foo/bar -> /foo
        """
        return os.path.dirname(cls.normalize(p))

    # @classmethod
    # def check_existence(cls, path):
    #     """Checking for a path existence.
    #
    #     Querying for the key should be faster than SELECET *.
    #     This also
    #     """
    #     path = cls.normalize(path)
    #     result = cls.cache.get(path)
    #     if result:
    #         return result
    #     logging.debug("check_existence(%r)" % path)
    #     result = db.GqlQuery("SELECT __key__ WHERE path = :1", path)
    #     return result is not None

    @classmethod
    def retrieve(cls, path):
        logging.debug(f"Path.retrieve({cls.__name__}, {path!r})")
        assert cls is Path
        path = cls.normalize(path)
        assert path.startswith("/")
        # result = cls.cache.get(path)
        # if result:
        #     # logging.debug('Cached result: %s' % result)
        #     return result
        doc_ref = cls._tree.get_doc_ref(path)
        if doc_ref is None:
            if path == "/":
                return Dir(path=path)
            return None
        print(doc_ref.path)
        doc = doc_ref.get()
        if doc.exists:
            info = doc.to_dict()
            if "size" in info:
                return File.from_doc(doc)
            return Dir.from_doc(doc)
            # cls.cache.set(path, result)
            # logging.debug('New result: %s' % result)
        # TODO: cache 'Not found' also
        # logging.debug('No result')
        return

    @classmethod
    def new(cls, path):
        # Make sure, we don't instantiate <Path> objects
        assert cls in (Dir, File)
        logging.debug(f"{cls.__name__}.new({path!r})")
        path = cls.normalize(path)
        if cls == Dir:
            doc = cls._tree.make_dir(path)
            return Dir.from_doc(doc)
        doc = cls._tree.make_file(path)
        return File.from_doc(doc)

    @staticmethod
    def _getresource(path):
        """Return a model.Dir or model.File object for `path`.

        `path` may be an existing Dir/File entity.
        Since _getresource is called by most other functions in the `data.fs` module,
        this allows the DAV provider to pass a cached resource, thus implementing
        a simple per-request caching, like in::

            statresults = data.fs.stat(self.pathEntity)

        Return None, if path does not exist.
        """
        if type(path) in (Dir, File):
            logging.debug("_getresource(%r): request cache HIT" % path.path)
            return path
        # logging.info("_getresource(%r)" % path)
        p = Path.retrieve(path)
        assert p is None or type(p) in (Dir, File)
        return p

    @staticmethod
    def mkdir(path):
        p = Dir.new(path)
        return p

    @staticmethod
    def mkfile(path):
        p = File.new(path)
        return p

    # @staticmethod
    # def btopen(path, mode="r"):
    #     """Open the file (eg. return a BtIO object)"""
    #     from .fs import BtIO
    #
    #     f = Path._getresource(path)
    #     assert f is None or type(f) is File
    #     if f is None:
    #         # Create targtet file, but only in write mode
    #         if "w" not in mode and "a" not in mode and "x" not in mode:
    #             raise ValueError("source not found %r" % path)
    #         f = File.new(path=path)
    #     io = BtIO(f, mode)
    #     return io

    @staticmethod
    def copyfile(s, d):
        # raise, if not exists:
        src = Path._getresource(s)
        if src is None:
            raise ValueError("Source not found %r" % s)
        if not src.isfile():
            raise ValueError("Source not a File %r" % s)
        dst = Path._getresource(d)
        if dst is None:
            dst = File.new(path=d)
        if not dst.isfile():
            raise ValueError("Destination not a File %r" % d)
        # TODO: copyfile2 without downloading/uploading chunk data at all?
        dst.iput_content(src.iget_content())
        return

    # @staticmethod
    # def stop_cache(stop=False):
    #     Path.cache.stop_cache = stop


# ===============================================================================
# Dir
# ===============================================================================
class Dir(Path):
    # parent_path = db.ReferenceProperty(Path)
    # _kind = 'Dir'
    # _exclude_from_indexes = None
    # _auto_now_add = ['create_time']
    # _auto_now = ['modify_time']
    # cache = cached_dir

    def _init_entity(self, **kwargs):
        super()._init_entity(**kwargs)
        self._entity.setdefault("parent_path", None)

    def _init_doc_ref(self, **kwargs):
        self.path = kwargs.pop("path", None)
        self._doc_ref = self._tree.get_dir_ref(self.path)
        self._doc = None

    def get_content(self):
        # result = list(self.dir_set) + list(self.file_set)
        # logging.debug("Dir.get_content: %r" % result)
        # TODO: ORDER BY
        # result = list(Path.gql("WHERE parent_path=:1", self))
        # result = self.cache.get_list(self.path)
        # if result:
        #     logging.debug("Dir.get_content: HIT %r" % result)
        #     return result
        # result = Path.list_by_parent_path(self)
        result = []
        for doc in self._tree.ilist_dir_docs(self.path):
            # CHECKME: do we need to differentiate between File and Dir here?
            info = doc.to_dict()
            if "size" in info:
                instance = File.from_doc(doc)
            else:
                instance = Dir.from_doc(doc)
            # instance = Path.from_doc(doc)
            result.append(instance)
        # logging.debug("Dir.get_content: MISS %r" % result)
        # self.cache.set_list(self.path, result)
        # preset items in cache since we will probably need them right after this
        # if isinstance(result, list) and len(result) > 0 and isinstance(result[0], Path):
        #     for item in result:
        #         self.cache.set(item.path, item)
        return result

    # https://stackoverflow.com/questions/4566769/can-i-memoize-a-python-generator/10726355
    def iget_content(self):
        # result = list(self.dir_set) + list(self.file_set)
        # logging.debug("Dir.get_content: %r" % result)
        # TODO: ORDER BY
        # result = list(Path.gql("WHERE parent_path=:1", self))
        # result = self.cache.get_list(self.path)
        # if result:
        #     logging.debug("Dir.iget_content: HIT %r" % result)
        #     for item in result:
        #         yield item
        #     return
        # result = []
        # for item in Path.ilist_by_parent_path(self):
        #     # result.append(item)
        #     yield item
        for doc in self._tree.ilist_dir_docs(self.path):
            # CHECKME: do we need to differentiate between File and Dir here?
            info = doc.to_dict()
            if "size" in info:
                instance = File.from_doc(doc)
            else:
                instance = Dir.from_doc(doc)
            # instance = Path.from_doc(doc)
            yield instance
        # logging.debug("Dir.iget_content: MISS %r" % result)
        # self.cache.set_list(self.path, result)
        # preset items in cache since we will probably need them right after this
        # if isinstance(result, list) and len(result) > 0 and isinstance(result[0], Path):
        #     for item in result:
        #         self.cache.set(item.path, item)
        return

    def listdir(self):
        return [c.basename(c.path) for c in self.get_content()]

    def ilistdir(self):
        for c in self.iget_content():
            yield c.basename(c.path)

    def delete(self, recursive=False):
        logging.debug(f"Dir.delete({recursive}): {self.path!r}")
        if not recursive:
            # TODO: faster lookup (for __key__)
            for p in self.iget_content():
                raise RuntimeError("Dir must be empty")
        else:
            for p in self.get_content():
                logging.debug(f"Dir.delete({recursive}): {self.path!r}, p={p!r}")
                if type(p) is Dir:
                    p.delete(recursive)
                elif type(p) is File:
                    p.delete()
                else:
                    RuntimeError("invalid child type")
        # for d in self.dir_set:
        #     logging.debug("Dir.delete(%s): %r, d=%r" % (recursive, self.path, d))
        #     d.delete(recursive)
        # for f in self.file_set:
        #     logging.debug("Dir.delete(%s): %r, f=%r" % (recursive, self.path, f))
        #     f.delete()
        Path.delete(self)
        return

    def rmdir(self):
        self.delete(recursive=False)

    def rmtree(self):
        self.delete(recursive=True)


# ===============================================================================
# File
# ===============================================================================
class File(Path):
    ChunkSize = 800 * 1024  # split file to chunks at most 800K

    # parent_path = db.ReferenceProperty(Path)
    # content = db.BlobProperty(default='')
    # content = db.ListProperty(db.Blob)
    # _kind = 'File'
    # _exclude_from_indexes = None
    # _auto_now_add = ['create_time']
    # _auto_now = ['modify_time']

    # cache = cached_file

    def _init_entity(self, **kwargs):
        super()._init_entity(**kwargs)
        self._entity.setdefault("parent_path", None)

    def _init_doc_ref(self, **kwargs):
        self.path = kwargs.pop("path", None)
        self._doc_ref = self._tree.get_file_ref(self.path)
        self._doc = None

    def put(self):
        if self.is_saved():
            pass
            # CHECKME: this doesn't return the chunks yet
            # if self.size == 0:
            #     self.size = sum(
            #         len(chunk["data"]) for chunk in Chunk.fetch_entities_by_file(self)
            #     )  # use ancestor instead?
        else:
            self.size = 0
        Path.put(self)
        return

    def get_content(self):
        """
        Join chunks together.
        """
        if self.is_saved():
            # chunks = Chunk.gql("WHERE file=:1 ORDER BY offset ASC", self)
            # chunks = Chunk.fetch_entities_by_file(self)
            chunks = Chunk.iget_chunks_data(self)
        else:
            chunks = []
        # result = b"".join(chunk["data"] for chunk in chunks)
        result = b"".join(data for data in chunks)
        # logging.debug('Content: %s' % repr(result))
        return result

    def iget_content(self):
        """
        Return chunks via iterable.
        """
        if self.is_saved():
            # chunks = Chunk.gql("WHERE file=:1 ORDER BY offset ASC", self)
            # chunks = Chunk.fetch_entities_by_file(self)
            chunks = Chunk.iget_chunks_data(self)
        else:
            chunks = []
        yield from chunks

    def put_content(self, s):
        """
        Split the DB transaction to serveral small chunks,
        to keep we don't exceed appengine's limit.
        """
        size = len(s)
        # self.content = []
        if not self.is_saved():
            logging.debug("No complete key available yet")
            self.set_key()
            # raise Exception
        else:
            # clear old chunks
            # self.truncate()
            self.size = size
            return self._tree.update_file(self._doc_ref, s)

        # put new datas
        for i in range(0, size, self.ChunkSize):
            logging.debug("File.put_content putting the chunk with offset = %d" % i)
            data = s[i : i + self.ChunkSize]
            # ck = Chunk(file=self.key(), offset=i, data=data, parent=self.key())  # use parent here?
            ck = Chunk(offset=i, data=data, parent=self.key())
            ck.put()
        self.size = size
        self.put()
        return

    def iput_content(self, iterable):
        """
        Split the DB transaction to serveral small chunks,
        to keep we don't exceed appengine's limit.
        """
        # size = len(s)
        # self.content = []
        if not self.is_saved():
            logging.debug("No complete key available yet")
            self.set_key()
            # raise Exception
        else:
            # clear old chunks
            # self.truncate()
            self.size = self._tree.append_file(self._doc_ref, iterable, True)
            return self.size

        # put new datas
        i = 0
        for data in iterable:
            logging.debug("File.iput_content putting the chunk with offset = %d" % i)
            length = len(data)
            if length > self.ChunkSize:
                # TODO: split data into chunks as above
                raise ValueError("Too much data received: %s" % length)
            # ck = Chunk(file=self.key(), offset=i, data=data, parent=self.key())  # use parent here?
            ck = Chunk(offset=i, data=data, parent=self.key())
            ck.put()
            i += length
        self.size = i
        self.put()
        return

    def download(self, file):
        # Note: we always write in chunks here, regardless of the chunk_size
        for data in self.iget_content():
            file.write(data)

    def truncate(self, size=None):
        # Note: we always truncate to 0 here, regardless of the size
        if not self.is_saved():
            self.size = 0
            return 0
        if size is not None and size > 0:
            raise NotImplementedError
        # clear old chunks
        # for chunk in self.chunk_set:  # use ancestor instead?
        #    chunk.delete()
        chunk_refs = Chunk.list_refs_by_file(self)
        if chunk_refs and len(chunk_refs) > 0:
            for doc_ref in chunk_refs:
                logging.debug("Chunk.delete %s" % repr(doc_ref.path))
                doc_ref.delete()
        self.size = 0
        # self.cache.delete(self.path)
        return 0

    def upload(self, file):
        # See fs.tools.copy_file_data at https://github.com/PyFilesystem/pyfilesystem2/blob/master/fs/tools.py
        # Note: we always read in chunks here, regardless of the chunk_size
        read_iter = iter(lambda: file.read(self.ChunkSize) or None, None)
        self.iput_content(read_iter)
        return

    def delete(self):
        """
        Also delete chunks.
        """
        logging.debug("File.delete %s" % repr(self.path))
        # for chunk in self.chunk_set:  # use ancestor instead?
        #    chunk.delete()
        chunk_refs = Chunk.list_refs_by_file(self)
        if chunk_refs and len(chunk_refs) > 0:
            for doc_ref in chunk_refs:
                logging.debug("Chunk.delete %s" % repr(doc_ref.path))
                doc_ref.delete()
        Path.delete(self)
        return

    def unlink(self):
        self.delete()


# ===============================================================================
# Chunk
# ===============================================================================
# class Chunk(db.Model):
class Chunk(DocModel):
    # file = db.ReferenceProperty(File)
    # offset = db.IntegerProperty(required=True)
    # data = db.BlobProperty(default=b'')
    _kind = "Chunk"
    _exclude_from_indexes = ["data"]
    _auto_now_add = None
    _auto_now = None

    def _init_entity(self, **kwargs):
        super()._init_entity(**kwargs)
        template = {
            #'file': None,
            "offset": 0,
            "data": b"",
        }
        for key in template:
            self._entity.setdefault(key, template[key])

    def _init_doc_ref(self, **kwargs):
        self.offset = kwargs.pop("offset", 0)
        self.data = kwargs.pop("data", b"")
        self.parent = kwargs.pop("parent", None)
        # self.path = assigned by Firestore
        # self._doc_ref = self._tree.get_chunk_ref(self.path)
        self._doc = None

    def __len__(self):
        return len(self.data)

    @classmethod
    def fetch_entities_by_file(cls, file):
        # chunks = Chunk.gql("WHERE file=:1 ORDER BY offset ASC", self)
        # query = db.get_client().query(kind=cls._kind)  # use ancestor instead?
        query = db.get_client().query(kind=cls._kind, ancestor=file.key())
        # query.add_filter('file', '=', file.key())
        query.order = ["offset"]
        return query.fetch()

    @classmethod
    def iget_chunks_data(cls, file):
        return cls._tree.iget_chunks_data(file._doc_ref)

    @classmethod
    def list_refs_by_file(cls, file):
        result = []
        for doc in cls._tree.ilist_file_chunks(file.path):
            result.append(doc.reference)
        return result
