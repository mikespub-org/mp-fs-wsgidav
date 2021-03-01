#!/usr/bin/env python3
#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: https://opensource.org/licenses/mit-license.php
#
"""Basic support for a read-only database explorer of Google Cloud Firestore with PyFilesystem2

Example opening directly with FirestoreDB():
    >>> from firestore_db import FirestoreDB
    >>> fire_db = FirestoreDB()
    >>> fire_db.listdir("/")

Example opening via a FS URL "firestore_db://"
    >>> import fs
    >>> import firestore_db  # not registered by default, so we need to import first
    >>> fire_db = fs.open_fs("firestore_db://")
    >>> fire_db.listdir("/")

For more information on PyFilesystem2, see https://docs.pyfilesystem.org/
"""
import io
import itertools
import json
import logging
import time
from functools import partial

from fs import errors
from fs.base import FS
from fs.info import Info
from fs.iotools import make_stream

# for opener
from fs.opener import Opener, open_fs, registry
from fs.path import dirname
from fs.wrapfs import WrapFS

# use the db module here
from . import db

#
# Specify location of your service account credentials in environment variable before you start:
#
# $ export GOOGLE_APPLICATION_CREDENTIALS="~/firestore-user.cred.json"
#
# See https://cloud.google.com/docs/authentication/getting-started for details...
#
# Or specify in startup script or .env file elsewere:
# import os
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "~/firestore-user.cred.json"
#

__all__ = ["FirestoreDB", "WrapFirestoreDB"]


log = logging.getLogger(__name__)


class FirestoreDB(FS):
    _has_colls = {}

    def __init__(self, root_path=None, limit=1000):
        # self._meta = {}
        super().__init__()
        self._root_path = root_path
        self._limit = limit
        # Initialize Firestore database if needed
        # db.initdb(self)
        self._root_ref = None

    # https://docs.pyfilesystem.org/en/latest/implementers.html#essential-methods
    # From https://github.com/PyFilesystem/pyfilesystem2/blob/master/fs/base.py

    # ---------------------------------------------------------------- #
    # Required methods                                                 #
    # Filesystems must implement these methods.                        #
    # ---------------------------------------------------------------- #

    def getinfo(self, path, namespaces=None):
        # type: (Text, Optional[Collection[Text]]) -> Info
        """Get information about a resource on a filesystem.

        Arguments:
            path (str): A path to a resource on the filesystem.
            namespaces (list, optional): Info namespaces to query
                (defaults to *[basic]*).

        Returns:
            ~fs.info.Info: resource information object.

        For more information regarding resource information, see :ref:`info`.

        """
        namespaces = namespaces or ()
        if path in ("/", "") or path is None:
            return self._make_info_from_root(namespaces)

        _res = self._getresource(path)
        if _res is None:
            raise errors.ResourceNotFound(path)

        return self._make_info_from_resource(_res, namespaces)

    def listdir(self, path, limit=None, offset=0):
        # type: (Text) -> List[Text]
        """Get a list of the resource names in a directory.

        This method will return a list of the resources in a directory.
        A *resource* is a file, directory, or one of the other types
        defined in `~fs.enums.ResourceType`.

        Arguments:
            path (str): A path to a directory on the filesystem

        Returns:
            list: list of names, relative to ``path``.

        Raises:
            fs.errors.DirectoryExpected: If ``path`` is not a directory.
            fs.errors.ResourceNotFound: If ``path`` does not exist.

        """
        log.info(path)
        if path in ("/", "") or path is None:
            result = []
            for coll_ref in db.list_root():
                result.append(coll_ref.id)
            return result

        _res = self._getresource(path)
        if _res is None:
            raise errors.ResourceNotFound(path)

        log.info("%r" % _res)
        if isinstance(_res, db.DocumentReference):
            # we should return this error here, but we could also make it easier to navigate...
            # raise errors.DirectoryExpected(path)
            result = []
            for coll_ref in _res.collections():
                result.append(coll_ref.id)
            return result

        # TODO: apply limit, offset etc.
        if limit is None:
            limit = self._limit
        # return [str(ref.id) for ref in db.list_doc_refs(coll, limit, offset)]
        iter_info = _res.list_documents()
        if limit:
            iter_info = itertools.islice(iter_info, offset, offset + limit)
        result = []
        for doc_ref in iter_info:
            result.append(doc_ref.id)
        return result

    def makedir(
        self,
        path,  # type: Text
        permissions=None,  # type: Optional[Permissions]
        recreate=False,  # type: bool
    ):
        # type: (...) -> SubFS[FS]
        """Make a directory.

        Arguments:
            path (str): Path to directory from root.
            permissions (~fs.permissions.Permissions, optional): a
                `Permissions` instance, or `None` to use default.
            recreate (bool): Set to `True` to avoid raising an error if
                the directory already exists (defaults to `False`).

        Returns:
            ~fs.subfs.SubFS: a filesystem whose root is the new directory.

        Raises:
            fs.errors.DirectoryExists: If the path already exists.
            fs.errors.ResourceNotFound: If the path is not found.

        """
        raise errors.ResourceReadOnly(path)

    def openbin(
        self,
        path,  # type: Text
        mode="r",  # type: Text
        buffering=-1,  # type: int
        **options,  # type: Any
    ):
        # type: (...) -> BinaryIO
        """Open a binary file-like object.

        Arguments:
            path (str): A path on the filesystem.
            mode (str): Mode to open file (must be a valid non-text mode,
                defaults to *r*). Since this method only opens binary files,
                the ``b`` in the mode string is implied.
            buffering (int): Buffering policy (-1 to use default buffering,
                0 to disable buffering, or any positive integer to indicate
                a buffer size).
            **options: keyword arguments for any additional information
                required by the filesystem (if any).

        Returns:
            io.IOBase: a *file-like* object.

        Raises:
            fs.errors.FileExpected: If the path is not a file.
            fs.errors.FileExists: If the file exists, and *exclusive mode*
                is specified (``x`` in the mode).
            fs.errors.ResourceNotFound: If the path does not exist.

        """
        # TODO: handle BLOB properties here
        if mode not in ("r", "rb"):
            raise errors.ResourceReadOnly(path)

        _res = self._getresource(path)
        if not _res:
            raise errors.ResourceNotFound(path)

        if not isinstance(_res, io.RawIOBase):
            if not isinstance(_res, db.DocumentReference) and not isinstance(
                _res, db.DocumentSnapshot
            ):
                raise TypeError("io stream expected")

            # CHECKME: someone wants to read the whole document, so let's give it to them as a json dump
            if isinstance(_res, db.DocumentReference):
                doc = _res.get()
            else:
                doc = _res
            info = doc.to_dict()
            # add other doc properties too?
            info.update(doc.__dict__)
            data = json.dumps(info, indent=2, default=lambda o: repr(o))
            stream = io.BytesIO(data.encode("utf-8"))
            name = str(doc.id) + ".json"
            return make_stream(name, stream, "rb")

        return _res

    def remove(self, path):
        # type: (Text) -> None
        """Remove a file from the filesystem.

        Arguments:
            path (str): Path of the file to remove.

        Raises:
            fs.errors.FileExpected: If the path is a directory.
            fs.errors.ResourceNotFound: If the path does not exist.

        """
        raise errors.ResourceReadOnly(path)

    def removedir(self, path):
        # type: (Text) -> None
        """Remove a directory from the filesystem.

        Arguments:
            path (str): Path of the directory to remove.

        Raises:
            fs.errors.DirectoryNotEmpty: If the directory is not empty (
                see `~fs.base.FS.removetree` for a way to remove the
                directory contents.).
            fs.errors.DirectoryExpected: If the path does not refer to
                a directory.
            fs.errors.ResourceNotFound: If no resource exists at the
                given path.
            fs.errors.RemoveRootError: If an attempt is made to remove
                the root directory (i.e. ``'/'``)

        """
        raise errors.ResourceReadOnly(path)

    def setinfo(self, path, info):
        # type: (Text, RawInfo) -> None
        """Set info on a resource.

        This method is the complement to `~fs.base.FS.getinfo`
        and is used to set info values on a resource.

        Arguments:
            path (str): Path to a resource on the filesystem.
            info (dict): Dictionary of resource info.

        Raises:
            fs.errors.ResourceNotFound: If ``path`` does not exist
                on the filesystem

        The ``info`` dict should be in the same format as the raw
        info returned by ``getinfo(file).raw``.

        Example:
            >>> details_info = {"details": {
            ...     "modified": time.time()
            ... }}
            >>> my_fs.setinfo('file.txt', details_info)

        """
        raise errors.ResourceReadOnly(path)

    # ---------------------------------------------------------------- #
    # Optional methods                                                 #
    # Filesystems *may* implement these methods.                       #
    # ---------------------------------------------------------------- #

    def scandir(
        self,
        path,  # type: Text
        namespaces=None,  # type: Optional[Collection[Text]]
        page=None,  # type: Optional[Tuple[int, int]]
    ):
        # type: (...) -> Iterator[Info]
        """Get an iterator of resource info.

        Arguments:
            path (str): A path to a directory on the filesystem.
            namespaces (list, optional): A list of namespaces to include
                in the resource information, e.g. ``['basic', 'access']``.
            page (tuple, optional): May be a tuple of ``(<start>, <end>)``
                indexes to return an iterator of a subset of the resource
                info, or `None` to iterate over the entire directory.
                Paging a directory scan may be necessary for very large
                directories.

        Returns:
            ~collections.abc.Iterator: an iterator of `Info` objects.

        Raises:
            fs.errors.DirectoryExpected: If ``path`` is not a directory.
            fs.errors.ResourceNotFound: If ``path`` does not exist.

        """
        namespaces = namespaces or ()
        if path in ("/", "") or path is None:
            return self._scandir_from_root(namespaces)

        _res = self._getresource(path)
        if not _res:
            raise errors.ResourceNotFound(path)

        # if not _res.isdir():
        #     raise errors.DirectoryExpected(path)

        # info = (
        #     self.getinfo(join(_path, name), namespaces=namespaces)
        #     for name in self.listdir(path)
        # )
        # iter_info = iter(info)
        if page is not None:
            start, end = page
            iter_info = self._scandir_from_resource(
                _res, namespaces, end - start, start
            )
        else:
            limit = self._limit
            offset = 0
            iter_info = self._scandir_from_resource(_res, namespaces, limit, offset)
        # if page is not None:
        #     start, end = page
        #     iter_info = itertools.islice(iter_info, start, end)
        return iter_info

    def todo_filterdir(
        self,
        path,  # type: Text
        files=None,  # type: Optional[Iterable[Text]]
        dirs=None,  # type: Optional[Iterable[Text]]
        exclude_dirs=None,  # type: Optional[Iterable[Text]]
        exclude_files=None,  # type: Optional[Iterable[Text]]
        namespaces=None,  # type: Optional[Collection[Text]]
        page=None,  # type: Optional[Tuple[int, int]]
    ):
        # type: (...) -> Iterator[Info]
        """Get an iterator of resource info, filtered by patterns.

        This method enhances `~fs.base.FS.scandir` with additional
        filtering functionality.

        Arguments:
            path (str): A path to a directory on the filesystem.
            files (list, optional): A list of UNIX shell-style patterns
                to filter file names, e.g. ``['*.py']``.
            dirs (list, optional): A list of UNIX shell-style patterns
                to filter directory names.
            exclude_dirs (list, optional): A list of patterns used
                to exclude directories.
            exclude_files (list, optional): A list of patterns used
                to exclude files.
            namespaces (list, optional): A list of namespaces to include
                in the resource information, e.g. ``['basic', 'access']``.
            page (tuple, optional): May be a tuple of ``(<start>, <end>)``
                indexes to return an iterator of a subset of the resource
                info, or `None` to iterate over the entire directory.
                Paging a directory scan may be necessary for very large
                directories.

        Returns:
            ~collections.abc.Iterator: an iterator of `Info` objects.

        """
        resources = self.scandir(path, namespaces=namespaces)
        filters = []

        def match_dir(patterns, info):
            # type: (Optional[Iterable[Text]], Info) -> bool
            """Pattern match info.name."""
            return info.is_file or self.match(patterns, info.name)

        def match_file(patterns, info):
            # type: (Optional[Iterable[Text]], Info) -> bool
            """Pattern match info.name."""
            return info.is_dir or self.match(patterns, info.name)

        def exclude_dir(patterns, info):
            # type: (Optional[Iterable[Text]], Info) -> bool
            """Pattern match info.name."""
            return info.is_file or not self.match(patterns, info.name)

        def exclude_file(patterns, info):
            # type: (Optional[Iterable[Text]], Info) -> bool
            """Pattern match info.name."""
            return info.is_dir or not self.match(patterns, info.name)

        if files:
            filters.append(partial(match_file, files))
        if dirs:
            filters.append(partial(match_dir, dirs))
        if exclude_dirs:
            filters.append(partial(exclude_dir, exclude_dirs))
        if exclude_files:
            filters.append(partial(exclude_file, exclude_files))

        if filters:
            resources = (
                info for info in resources if all(_filter(info) for _filter in filters)
            )

        iter_info = iter(resources)
        if page is not None:
            start, end = page
            iter_info = itertools.islice(iter_info, start, end)
        return iter_info

    def close(self):
        # type: () -> None
        """Close the filesystem and release any resources.

        It is important to call this method when you have finished
        working with the filesystem. Some filesystems may not finalize
        changes until they are closed (archives for example). You may
        call this method explicitly (it is safe to call close multiple
        times), or you can use the filesystem as a context manager to
        automatically close.

        Example:
            >>> with OSFS('~/Desktop') as desktop_fs:
            ...    desktop_fs.writetext(
            ...        'note.txt',
            ...        "Don't forget to tape Game of Thrones"
            ...    )

        If you attempt to use a filesystem that has been closed, a
        `~fs.errors.FilesystemClosed` exception will be thrown.

        """
        if not self._closed:
            db.close()
        return super().close()

    # ---------------------------------------------------------------- #
    # Internal methods                                                 #
    # Filesystem-specific methods.                                     #
    # ---------------------------------------------------------------- #

    @classmethod
    def _make_info_from_root(cls, namespaces):
        name = ""
        parent = None
        return cls._make_info_from_name_parent(name, parent, namespaces)

    @classmethod
    def _make_info_from_resource(cls, _res, namespaces):
        if isinstance(_res, db.DocumentReference):
            return cls._make_info_from_doc_ref(_res, namespaces)
        if isinstance(_res, db.DocumentSnapshot):
            return cls._make_info_from_document(_res, namespaces)
        return cls._make_info_from_collection(_res, namespaces)

    @classmethod
    def _make_info_from_collection(cls, coll_ref, namespaces):
        name = coll_ref.id
        parent = coll_ref.parent
        return cls._make_info_from_name_parent(name, parent, namespaces)

    @classmethod
    def _make_info_from_name_parent(cls, name, parent, namespaces):
        info = {"basic": {"name": name, "is_dir": True}}
        if "details" in namespaces:
            now = time.time()
            st_size = None
            st_atime = now
            st_mtime = now
            st_ctime = now
            info["details"] = {
                # "_write": ["accessed", "modified"],
                # "_write": ["created", "modified"],
                "_write": [],
                "accessed": st_atime,
                "modified": st_mtime,
                "created": st_ctime,
                "size": st_size,
                "type": 1,
                # from coll_ref properties
                "id": name,
                "parent": parent,
            }

        return Info(info)

    @classmethod
    def _make_info_from_doc_ref(cls, doc_ref, namespaces):
        if (
            "properties" in namespaces
            or "details" in namespaces
            or "stat" in namespaces
        ):
            if "properties" in namespaces:
                doc = doc_ref.get()
            else:
                # select limited set of field_paths
                doc = doc_ref.get(["size"])
            return cls._make_info_from_document(doc, namespaces)

        name = doc_ref.id
        # CHECKME: this needs to be pre-configured or cached
        coll_path = dirname(doc_ref.path)
        if coll_path not in cls._has_colls:
            cls._has_colls[coll_path] = False
            for coll_ref in doc_ref.collections():
                cls._has_colls[coll_path] = True
                break
        if cls._has_colls[coll_path]:
            info = {"basic": {"name": name, "is_dir": True}}
        else:
            info = {"basic": {"name": name, "is_dir": False}}

        return Info(info)

    @classmethod
    def _make_info_from_document(cls, doc, namespaces):
        def epoch(pb):
            # return time.mktime(dt.utctimetuple())
            if hasattr(pb, "timestamp_pb"):
                pb = pb.timestamp_pb()
            return pb.seconds + float(pb.nanos / 1000000000.0)

        name = doc.id
        doc_ref = doc.reference
        # CHECKME: this needs to be pre-configured or cached
        coll_path = dirname(doc_ref.path)
        if coll_path not in cls._has_colls:
            cls._has_colls[coll_path] = False
            for coll_ref in doc_ref.collections():
                cls._has_colls[coll_path] = True
                break
        if cls._has_colls[coll_path]:
            info = {"basic": {"name": name, "is_dir": True}}
        else:
            info = {"basic": {"name": name, "is_dir": False}}
        now = time.time()
        # when combined with FS2DAVProvider(), size None tells WsgiDAV to read until EOF
        # st_size = doc.to_dict().get("size", 0)
        st_size = None
        st_atime = now
        st_mtime = epoch(doc.update_time)
        st_ctime = epoch(doc.create_time)
        if "properties" in namespaces:
            info["properties"] = doc.to_dict()
            # add other doc properties too?
            info["properties"].update(doc.__dict__)
            del info["properties"]["_data"]
            # skip setting size if we want to read a property
            if "size" in info["properties"]:
                st_size = info["properties"]["size"]
            else:
                st_size = 0
                for value in list(info["properties"].values()):
                    st_size += value.__sizeof__()
            # if "create_time" in info["properties"]:
            #     st_ctime = epoch(info["properties"]["create_time"])
            # if "update_time" in info["properties"]:
            #     st_mtime = epoch(info["properties"]["update_time"])
            # elif "modify_time" in info["properties"]:
            #     st_mtime = epoch(info["properties"]["modify_time"])
        if "details" in namespaces:
            info["details"] = {
                # "_write": ["accessed", "modified"],
                # "_write": ["created", "modified"],
                "_write": [],
                "accessed": st_atime,
                "modified": st_mtime,
                "created": st_ctime,
                "size": st_size,
                # "type": int(cls._get_type_from_stat(stat_result)),
                # from doc properties
                "id": doc.id,
                "reference": doc.reference,
                "exists": doc.exists,
                # from doc_ref properties
                "parent": doc_ref.parent,
                "path": doc_ref.path,
            }
            if cls._has_colls[coll_path]:
                info["details"]["type"] = 1
            else:
                info["details"]["type"] = 2
        if "stat" in namespaces:
            info["stat"] = {
                "st_size": st_size,
                "st_atime": st_atime,
                "st_mtime": st_mtime,
                "st_ctime": st_ctime,
            }
        # if "lstat" in namespaces:
        #     info["lstat"] = {
        #         k: getattr(_lstat, k) for k in dir(_lstat) if k.startswith("st_")
        #     }
        # if "link" in namespaces:
        #     info["link"] = cls._make_link_info(sys_path)
        # if "access" in namespaces:
        #     info["access"] = cls._make_access_from_stat(_stat)

        return Info(info)

    @classmethod
    def _scandir_from_root(cls, namespaces):
        for coll_ref in db.list_root():
            yield cls._make_info_from_collection(coll_ref, namespaces)

    @classmethod
    def _scandir_from_resource(cls, _res, namespaces, limit=None, offset=0):
        if isinstance(_res, db.DocumentReference):
            return cls._scandir_from_document(_res, namespaces, limit, offset)
        # if isinstance(_res, db.DocumentSnapshot):
        #     return cls._scandir_from_document(_res.reference, namespaces, limit, offset)
        return cls._scandir_from_collection(_res, namespaces, limit, offset)

    @classmethod
    def _scandir_from_collection(cls, coll_ref, namespaces, limit=None, offset=0):
        if (
            "properties" in namespaces
            or "details" in namespaces
            or "stat" in namespaces
        ):
            if "properties" in namespaces:
                query = coll_ref
            else:
                # select limited set of field_paths
                query = coll_ref.select(["size"])
            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)
            for doc in query.stream():
                yield cls._make_info_from_document(doc, namespaces)
            return
        iter_info = coll_ref.list_documents()
        if limit:
            iter_info = itertools.islice(iter_info, offset, offset + limit)
        for doc_ref in iter_info:
            yield cls._make_info_from_doc_ref(doc_ref, namespaces)

    @classmethod
    def _scandir_from_document(cls, doc_ref, namespaces, limit=None, offset=0):
        for coll_ref in doc_ref.collections():
            yield cls._make_info_from_collection(coll_ref, namespaces)

    def _getresource(self, path):
        # type: (Text) -> bool
        """Get the internal resource for a path (Dir, File or None).

        Arguments:
            path (str): Path to a resource.

        Returns:
            resource: internal resource at the given path (Dir, File or None).

        """
        _path = self.validatepath(path)
        if _path.startswith("/"):
            _path = _path[1:]
        if _path == "":
            # create virtual doc for root
            return db.get_client()

        parts = _path.split("/")
        if len(parts) % 2 == 1:
            log.info("Coll %s" % path)
            return db.get_coll_ref(_path)

        if "[" not in _path or not _path.endswith("]"):
            log.info("Doc %s" % path)
            return db.get_doc_ref(_path)

        # format: id[propname]
        log.info("Prop %s" % path)
        _path, propname = _path[:-1].split("[", 1)
        doc_ref = db.get_doc_ref(_path)
        doc = doc_ref.get([propname])
        info = doc.to_dict()
        # add other doc properties too?
        info.update(doc.__dict__)
        data = info.get(propname)
        if not isinstance(data, (str, bytes)):
            data = repr(data)
        if isinstance(data, str):
            data = data.encode("utf-8")
        stream = io.BytesIO(data)
        return make_stream(propname, stream, "rb")

    def __repr__(self):
        return "%s()" % (self.__class__.__name__)


class WrapFirestoreDB(WrapFS):
    def __init__(self, root_path=None):
        self._temp_fs_url = "temp://__firestore_tempdb__"
        # self._temp_fs_url = "mem://"
        self._temp_fs = open_fs(self._temp_fs_url)
        log.info(self._temp_fs)
        # self._meta = {}
        super().__init__(self._temp_fs)


@registry.install
class FirestoreDBOpener(Opener):

    protocols = ["firestore_db"]

    def open_fs(self, fs_url, parse_result, writeable, create, cwd):
        fire_db = FirestoreDB()
        return fire_db


def main(coll=None, id=None, *args):
    # logging.getLogger().setLevel(logging.DEBUG)
    fire_db = FirestoreDB(limit=20)
    # fire_db = open_fs("firestore_db://")
    # fire_db = WrapFirestoreDB()
    # path = "/"
    if coll is None:
        # result = fire_db.listdir(path)
        # result = fire_db.tree(max_levels=6)
        result = fire_db.listdir("/")
        # result = list(fire_db.scandir("/", ["details"]))
        # for item in result:
        #     print(item.raw)
    else:
        # path += coll
        fire_coll = fire_db.opendir(coll)
        if id is None:
            # result = fire_coll.getinfo("/", namespaces=["properties"]).raw
            result = fire_coll.listdir("/")
        else:
            # path += "/" + str(id)
            path = str(id)
            if len(args) < 1:
                # format: id[propname]
                if "[" in path and path.endswith("]"):
                    fp = fire_coll.openbin(path, "rb")
                    result = fp.read()
                    fp.close()
                else:
                    result = fire_coll.getinfo(
                        path, namespaces=["properties", "details"]
                    ).raw
            else:
                path += "/" + "/".join(args)
                result = fire_coll.getinfo(
                    path, namespaces=["properties", "details"]
                ).raw
                # fp = fire_coll.openbin(path, "rb")
                # result = fp.read()
                # fp.close()
    fire_db.close()
    return result


if __name__ == "__main__":
    import sys
    from pprint import pprint

    if len(sys.argv) > 1:
        result = main(*sys.argv[1:])
    else:
        print(
            "%s [<coll> [<id> [<coll> [<id> [...]]]]]" % "python3 -m fire.firestore_db"
        )
        print(
            "%s <coll>[/<id>[/<coll>]] <id>[<propname>]"
            % "python3 -m fire.firestore_db"
        )
        result = main()

    pprint(result)
