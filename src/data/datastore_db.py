#!/usr/bin/env python3
#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: https://opensource.org/licenses/mit-license.php
#
"""Basic support for a read-only database explorer of Google Cloud Datastore with PyFilesystem2

Example opening directly with DatastoreDB():
    >>> from datastore_db import DatastoreDB
    >>> data_db = DatastoreDB()
    >>> data_db.listdir("/")

Example opening via a FS URL "datastore_db://"
    >>> import fs
    >>> import datastore_db  # not registered by default, so we need to import first
    >>> data_db = fs.open_fs("datastore_db://")
    >>> data_db.listdir("/")

For more information on PyFilesystem2, see https://docs.pyfilesystem.org/
"""
from fs import errors
from fs.base import FS
from fs.info import Info
from fs.path import split, join, basename
from fs.wrapfs import WrapFS
from fs.opener import open_fs

# for opener
from fs.opener import Opener
from fs.opener import registry

from functools import partial
import time
import datetime
import itertools
import json
import logging

# use the db module here
from . import db
import io
from fs.iotools import RawWrapper, make_stream

# from .model import Path as PathModel
# TODO: replace with more advanced IO class - see e.g. _MemoryFile in fs.memoryfs
# from .fs import BtIO

#
# Specify location of your service account credentials in environment variable before you start:
#
# $ export GOOGLE_APPLICATION_CREDENTIALS="~/datastore-user.cred.json"
#
# See https://cloud.google.com/docs/authentication/getting-started for details...
#
# Or specify in startup script or .env file elsewere:
# import os
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "~/datastore-user.cred.json"
#

__all__ = ["DatastoreDB", "WrapDatastoreDB"]


log = logging.getLogger(__name__)


class DatastoreDB(FS):
    def __init__(self, limit=1000):
        # self._meta = {}
        super(DatastoreDB, self).__init__()
        self._limit = limit
        # Initialize Datastore database if needed
        # db.initdb(self)
        self._namespaces = db.list_namespaces()
        # include meta kinds here too
        self._kinds = db.list_kinds(True)
        self._metakinds = db.list_metakinds()
        self._properties = db.get_properties()
        # for kind in self._kinds:
        #     self._properties[kind] = db.get_properties_for_kind(kind)

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
            # return [kind for kind in self._kinds if kind not in self._metakinds]
            return self._kinds
        if path.startswith("/"):
            path = path[1:]
        parts = path.split("/")
        kind = parts.pop(0)
        if kind not in self._kinds:
            raise errors.ResourceNotFound(path)
        if len(parts) > 0:
            # we should return this error here, but we could also make it easier to navigate...
            raise errors.DirectoryExpected(path)
            # id_or_name = "/".join(parts)
            # ...
        if limit is None:
            limit = self._limit
        # return [str(key.id_or_name) for key in db.list_entity_keys(kind, limit, offset)]
        result = []
        for key in db.list_entity_keys(kind, limit, offset):
            name = self._key_to_path(key)
            result.append(name)
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
        **options  # type: Any
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
            if not isinstance(_res, db.Model):
                raise TypeError("io stream expected")

            # CHECKME: someone wants to read the whole entity, so let's give it to them as a json dump
            data = json.dumps(_res.to_dict(True), indent=2, default=lambda o: repr(o))
            stream = io.BytesIO(data.encode("utf-8"))
            name = self._key_to_path(_res.key()) + ".json"
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
            return self._scandir_root(namespaces)

        _res = self._getresource(path)
        if not _res:
            raise errors.ResourceNotFound(path)

        if not _res.isdir():
            raise errors.DirectoryExpected(path)

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
            """Pattern match info.name.
            """
            return info.is_file or self.match(patterns, info.name)

        def match_file(patterns, info):
            # type: (Optional[Iterable[Text]], Info) -> bool
            """Pattern match info.name.
            """
            return info.is_dir or self.match(patterns, info.name)

        def exclude_dir(patterns, info):
            # type: (Optional[Iterable[Text]], Info) -> bool
            """Pattern match info.name.
            """
            return info.is_file or not self.match(patterns, info.name)

        def exclude_file(patterns, info):
            # type: (Optional[Iterable[Text]], Info) -> bool
            """Pattern match info.name.
            """
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
        return super(DatastoreDB, self).close()

    # ---------------------------------------------------------------- #
    # Internal methods                                                 #
    # Filesystem-specific methods.                                     #
    # ---------------------------------------------------------------- #

    @classmethod
    def _make_info_from_resource(cls, _res, namespaces):
        def epoch(dt):
            # return time.mktime(dt.utctimetuple())
            return (
                dt - datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
            ) / datetime.timedelta(seconds=1)

        # st_size = _res.size
        # st_atime = epoch(_res.modify_time)
        # st_mtime = st_atime
        # st_ctime = epoch(_res.create_time)
        now = time.time()
        # when combined with FS2DAVProvider(), size None tells WsgiDAV to read until EOF
        # st_size = 0
        st_size = None
        st_atime = now
        st_mtime = st_atime
        st_ctime = now

        # info = {"basic": {"name": basename(_res.path), "is_dir": _res.isdir()}}
        if _res.isdir():
            name = _res._kind
            info = {"basic": {"name": name, "is_dir": True}}
            if "properties" in namespaces:
                info["properties"] = _res._properties
        else:
            name = cls._key_to_path(_res.key())
            info = {"basic": {"name": name, "is_dir": False}}
            if "properties" in namespaces:
                info["properties"] = _res.to_dict(True)
                # skip setting size if we want to read a property
                if "size" in info["properties"]:
                    st_size = info["properties"]["size"]
                else:
                    st_size = 0
                    for value in list(info["properties"].values()):
                        st_size += value.__sizeof__()
                if "create_time" in info["properties"]:
                    st_ctime = epoch(info["properties"]["create_time"])
                if "update_time" in info["properties"]:
                    st_mtime = epoch(info["properties"]["update_time"])
                elif "modify_time" in info["properties"]:
                    st_mtime = epoch(info["properties"]["modify_time"])
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
            }
            if _res.isdir():
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

    def _scandir_root(self, namespaces):
        for kind in self._kinds:
            instance = db.make_instance(kind)
            instance._properties = self._properties[kind]
            yield self._make_info_from_resource(instance, namespaces)

    @classmethod
    def _scandir_from_resource(cls, _res, namespaces, limit=None, offset=0):
        for _child_res in db.ilist_entities(_res._kind, limit, offset):
            # yield cls._make_info_from_resource(_child_res, namespaces)
            instance = db.make_instance(_res._kind, _child_res)
            # instance._properties = _res._properties
            yield cls._make_info_from_resource(instance, namespaces)

    @staticmethod
    def _key_to_path(key):
        if key.parent is not None:
            parts = [*key.flat_path]
            # skip the current kind at the end
            id_or_name = parts.pop()
            kind = parts.pop()
            name = str(id_or_name)
            while len(parts) > 0:
                # Parent:id_or_name
                name += ":" + parts.pop(0) + ":" + str(parts.pop(0))
            # name = "{URL:}" + key.to_legacy_urlsafe().decode("utf-8")
        else:
            name = str(key.id_or_name)
        return name.replace("/", "§")

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
            # create virtual instance for root
            instance = db.make_instance("__kind__")
            instance._properties = []
            return instance
        parts = _path.split("/")
        kind = parts.pop(0)
        if kind not in self._kinds:
            raise errors.ResourceNotFound(path)
        if len(parts) < 1:
            instance = db.make_instance(kind)
            instance._properties = self._properties[kind]
            return instance
        # CHECKME: leading / may be eaten already
        # id_or_name = "/".join(parts)
        id_or_name = parts.pop(0)
        id_or_name = id_or_name.replace("§", "/")
        if ":" in id_or_name:
            id_or_name, parent = key.split(":", 1)
            path_args = parent.split(":")
            if id_or_name.isdecimal():
                id_or_name = int(id_or_name)
            # put back the current kind
            key = db.get_key(kind, id_or_name, *path_args)
        else:
            if id_or_name.isdecimal():
                id_or_name = int(id_or_name)
            key = db.get_key(kind, id_or_name)
        # CHECKME: we need to make the entity ourselves for meta kinds
        if kind in self._metakinds:
            entity = db.make_entity(key)
        else:
            entity = db.get_entity(key)
        # entity = db.get_entity_by_id(kind, id_or_name)
        instance = db.make_instance(kind, entity)
        # instance._properties = self._properties[kind]
        if len(parts) > 0:
            propname = parts.pop(0)
            if not hasattr(instance, propname):
                raise errors.ResourceNotFound(path)
            # return getattr(instance, propname)
            data = getattr(instance, propname)
            if not isinstance(data, (str, bytes)):
                data = repr(data)
            if isinstance(data, str):
                data = data.encode("utf-8")
            stream = io.BytesIO(data)
            return make_stream(propname, stream, "rb")
        return instance


class WrapDatastoreDB(WrapFS):
    def __init__(self, root_path=None):
        self._temp_fs_url = "temp://__datastore_tempdb__"
        # self._temp_fs_url = "mem://"
        self._temp_fs = open_fs(self._temp_fs_url)
        log.info(self._temp_fs)
        # self._meta = {}
        super(WrapDatastoreDB, self).__init__(self._temp_fs)


@registry.install
class DatastoreDBOpener(Opener):

    protocols = ["datastore_db"]

    def open_fs(self, fs_url, parse_result, writeable, create, cwd):
        data_db = DatastoreDB()
        return data_db


def main(kind=None, id=None, *args):
    # logging.getLogger().setLevel(logging.DEBUG)
    data_db = DatastoreDB(limit=20)
    # data_db = open_fs("datastore_db://")
    # data_db = WrapDatastoreDB()
    # path = "/"
    if kind is None:
        # result = data_db.listdir(path)
        result = data_db.tree()
    else:
        # path += kind
        data_kind = data_db.opendir(kind)
        if id is None:
            # result = data_kind.getinfo("/", namespaces=["properties"]).raw
            result = data_kind.listdir("/")
        else:
            # path += "/" + str(id)
            if len(args) < 1:
                result = data_kind.getinfo(str(id), namespaces=["properties"]).raw
            else:
                # path += "/" + "/".join(args)
                path = str(id) + "/" + "/".join(args)
                fp = data_kind.openbin(path, "rb")
                result = fp.read()
                fp.close()
    data_db.close()
    return result


if __name__ == "__main__":
    from pprint import pformat, pprint
    import sys

    if len(sys.argv) > 1:
        result = main(*sys.argv[1:])
    else:
        print("%s [<kind> [<id> [<propname>]]]" % "python3 -m data.datastore_db")
        result = main()

    pprint(result)
