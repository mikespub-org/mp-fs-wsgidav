#!/usr/bin/env python3
#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: https://opensource.org/licenses/mit-license.php
#
"""Basic support of Google Cloud Datastore as filesystem with PyFilesystem2

Example opening directly with DatastoreFS():
    >>> from datastore_fs import DatastoreFS
    >>> data_fs = DatastoreFS()
    >>> data_fs.listdir("/")

Example opening via a FS URL "datastore://"
    >>> import fs
    >>> import datastore_fs  # not registered by default, so we need to import first
    >>> data_fs = fs.open_fs("datastore://")
    >>> data_fs.listdir("/")

For more information on PyFilesystem2, see https://docs.pyfilesystem.org/
"""
import datetime
import io
import itertools
import logging
from functools import partial

from fs import errors
from fs.base import FS
from fs.info import Info
from fs.iotools import RawWrapper
from fs.mode import Mode

# for opener
from fs.opener import Opener, open_fs, registry
from fs.path import join, split
from fs.wrapfs import WrapFS

# use the datastore fs module here
from . import fs as data_fs

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

__all__ = ["DatastoreFS", "WrapDatastoreFS"]


log = logging.getLogger(__name__)


class DatastoreFS(FS):
    _meta = {
        "case_insensitive": False,
        "invalid_path_chars": "\0",
        "network": True,
        "read_only": False,
        "supports_rename": False,
        "thread_safe": False,
        "unicode_paths": True,
        "virtual": False,
    }

    def __init__(self, root_path=None, use_cache=True):
        # self._meta = {}
        super().__init__()
        if root_path is None:
            root_path = "/_datastore_fs_"
        _root_path = self.validatepath(root_path)
        if not _root_path.startswith("/"):
            _root_path = "/" + _root_path
        self._is_cached = True
        if not use_cache:
            self._stop_cache(True)
        # Initialize Datastore filesystem if needed
        data_fs.initfs()
        # Check if the requested root_path exists
        _res = data_fs._getresource(_root_path)
        if _res:
            if _res.isdir():
                log.info("Root path exists %s" % _root_path)
            else:
                raise errors.DirectoryExpected(root_path)
        else:
            log.info("Creating root path %s" % _root_path)
            _res = data_fs.mkdir(_root_path)
        log.info("Resource: %s" % _res)
        self.root_path = _root_path
        self.root_res = _res

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

    def listdir(self, path):
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
        with self._lock:
            _res = self._getresource(path)
            if not _res:
                raise errors.ResourceNotFound(path)

            if not _res.isdir():
                raise errors.DirectoryExpected(path)

            return _res.listdir()

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
        # mode = Permissions.get_mode(permissions)
        _path = self.validatepath(path)

        with self._lock:
            if _path == "/":
                if recreate:
                    return self.opendir(path)
                else:
                    raise errors.DirectoryExists(path)

            if _path.endswith("/"):
                _path = _path[:-1]
            dir_path, dir_name = split(_path)

            _dir_res = self._getresource(dir_path)
            if not _dir_res or not _dir_res.isdir():
                raise errors.ResourceNotFound(path)

            if dir_name in _dir_res.listdir():
                if not recreate:
                    raise errors.DirectoryExists(path)

                _res = self._getresource(path)
                if _res and _res.isdir():
                    return self.opendir(path)

            _res = data_fs.mkdir(self._prep_path(_path))
            return self.opendir(path)

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
        _mode = Mode(mode)
        _mode.validate_bin()
        _path = self.validatepath(path)
        dir_path, file_name = split(_path)

        if not file_name:
            raise errors.FileExpected(path)

        with self._lock:
            _dir_res = self._getresource(dir_path)
            if not _dir_res or not _dir_res.isdir():
                raise errors.ResourceNotFound(path)

            if _mode.create:
                if file_name in _dir_res.listdir():
                    if _mode.exclusive:
                        raise errors.FileExists(path)

                    _res = self._getresource(path)
                    if not _res or not _res.isfile():
                        raise errors.FileExpected(path)

                    return self._btopen(_res, _mode.to_platform_bin())

                return self._btopen(self._prep_path(_path), _mode.to_platform_bin())

            if file_name not in _dir_res.listdir():
                raise errors.ResourceNotFound(path)

            _res = self._getresource(path)
            if not _res or not _res.isfile():
                raise errors.FileExpected(path)

            return self._btopen(_res, _mode.to_platform_bin())

    def remove(self, path):
        # type: (Text) -> None
        """Remove a file from the filesystem.

        Arguments:
            path (str): Path of the file to remove.

        Raises:
            fs.errors.FileExpected: If the path is a directory.
            fs.errors.ResourceNotFound: If the path does not exist.

        """
        with self._lock:
            _res = self._getresource(path)
            if not _res:
                raise errors.ResourceNotFound(path)

            if not _res.isfile():
                raise errors.FileExpected(path)

            _res.delete()

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
        _path = self.validatepath(path)
        if _path == "/" or _path == "" or _path is None:
            raise errors.RemoveRootError()
        if _path.endswith("/"):
            _path = _path[:-1]

        with self._lock:
            _res = self._getresource(path)
            if not _res:
                raise errors.ResourceNotFound(path)

            if not _res.isdir():
                raise errors.DirectoryExpected(path)

            if len(_res.listdir()) > 0:
                raise errors.DirectoryNotEmpty(path)

            _res.delete(recursive=False)

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
        with self._lock:
            _res = self._getresource(path)
            if not _res:
                raise errors.ResourceNotFound(path)

            if "details" in info:
                details = info["details"]
                if (
                    "accessed" in details
                    or "modified" in details
                    or "created" in details
                ):
                    accessed_time = int(details.get("accessed", 0))
                    modified_time = int(details.get("modified", 0))
                    created_time = int(details.get("created", 0))
                    if accessed_time and not modified_time:
                        modified_time = accessed_time
                    if created_time:
                        _res.create_time = datetime.datetime.fromtimestamp(
                            created_time, datetime.UTC
                        )
                    if modified_time:
                        _res.modify_time = datetime.datetime.fromtimestamp(
                            modified_time, datetime.UTC
                        )
                    _res.put()

    # ---------------------------------------------------------------- #
    # Optional methods                                                 #
    # Filesystems *may* implement these methods.                       #
    # ---------------------------------------------------------------- #

    def exists(self, path):
        # type: (Text) -> bool
        """Check if a path maps to a resource.

        Arguments:
            path (str): Path to a resource.

        Returns:
            bool: `True` if a resource exists at the given path.

        """
        _res = self._getresource(path)
        return _res is not None

    def isdir(self, path):
        # type: (Text) -> bool
        """Check if a path maps to an existing directory.

        Parameters:
            path (str): A path on the filesystem.

        Returns:
            bool: `True` if ``path`` maps to a directory.

        """
        _res = self._getresource(path)
        if not _res or not _res.isdir():
            return False
        return True

    def isfile(self, path):
        # type: (Text) -> bool
        """Check if a path maps to an existing file.

        Parameters:
            path (str): A path on the filesystem.

        Returns:
            bool: `True` if ``path`` maps to a file.

        """
        _res = self._getresource(path)
        if not _res or not _res.isfile():
            return False
        return True

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

        _res = self._getresource(path)
        if not _res:
            raise errors.ResourceNotFound(path)

        if not _res.isdir():
            raise errors.DirectoryExpected(path)

        iter_info = self._scandir_from_resource(_res, namespaces)
        if page is not None:
            start, end = page
            iter_info = itertools.islice(iter_info, start, end)
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
        # TODO: apply filters directly in Dir.get_content() - see scandir()
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

    def copy(self, src_path, dst_path, overwrite=False, preserve_time=False):
        # type: (Text, Text, bool) -> None
        """Copy file contents from ``src_path`` to ``dst_path``.

        Arguments:
            src_path (str): Path of source file.
            dst_path (str): Path to destination file.
            overwrite (bool): If `True`, overwrite the destination file
                if it exists (defaults to `False`).

        Raises:
            fs.errors.DestinationExists: If ``dst_path`` exists,
                and ``overwrite`` is `False`.
            fs.errors.ResourceNotFound: If a parent directory of
                ``dst_path`` does not exist.

        """
        self.validatepath(src_path)
        _dst_path = self.validatepath(dst_path)
        with self._lock:
            if not overwrite and self.exists(dst_path):
                raise errors.DestinationExists(dst_path)

            dir_path, file_name = split(_dst_path)
            _dir_res = self._getresource(dir_path)
            if not _dir_res or not _dir_res.isdir():
                raise errors.ResourceNotFound(dst_path)

            _src_res = self._getresource(src_path)
            if not _src_res:
                raise errors.ResourceNotFound(src_path)
            if not _src_res.isfile():
                raise errors.FileExpected(src_path)

            data_fs.copyfile(_src_res, self._prep_path(_dst_path))

    def move(self, src_path, dst_path, overwrite=False, preserve_time=False):
        # type: (Text, Text, bool) -> None
        """Move a file from ``src_path`` to ``dst_path``.

        Arguments:
            src_path (str): A path on the filesystem to move.
            dst_path (str): A path on the filesystem where the source
                file will be written to.
            overwrite (bool): If `True`, destination path will be
                overwritten if it exists.

        Raises:
            fs.errors.FileExpected: If ``src_path`` maps to a
                directory instead of a file.
            fs.errors.DestinationExists: If ``dst_path`` exists,
                and ``overwrite`` is `False`.
            fs.errors.ResourceNotFound: If a parent directory of
                ``dst_path`` does not exist.

        """
        # TODO: update parent key of chunk entities instead of copy & delete?
        self.copy(src_path, dst_path, overwrite, preserve_time)
        self.remove(src_path)

    def create(self, path, wipe=False):
        # type: (Text, bool) -> bool
        """Create an empty file.

        The default behavior is to create a new file if one doesn't
        already exist. If ``wipe`` is `True`, any existing file will
        be truncated.

        Arguments:
            path (str): Path to a new file in the filesystem.
            wipe (bool): If `True`, truncate any existing
                file to 0 bytes (defaults to `False`).

        Returns:
            bool: `True` if a new file had to be created.

        """
        with self._lock:
            _res = self._getresource(path)
            if _res:
                if not _res.isfile():
                    raise errors.FileExpected(path)
                if not wipe:
                    return False
                _res.truncate(0)

            else:
                _path = self.validatepath(path)

                dir_path, file_name = split(_path)
                _dir_res = self._getresource(dir_path)
                if not _dir_res or not _dir_res.isdir():
                    raise errors.ResourceNotFound(path)

                _res = data_fs.mkfile(self._prep_path(_path))

            return True

    def readbytes(self, path):
        # type: (Text) -> bytes
        """Get the contents of a file as bytes.

        Arguments:
            path (str): A path to a readable file on the filesystem.

        Returns:
            bytes: the file contents.

        Raises:
            fs.errors.ResourceNotFound: if ``path`` does not exist.

        """
        with self._lock:
            _res = self._getresource(path)
            if not _res:
                raise errors.ResourceNotFound(path)
            if not _res.isfile():
                raise errors.FileExpected(path)

            return _res.get_content()

    def download(self, path, file, chunk_size=None, **options):
        # type: (Text, BinaryIO, Optional[int], **Any) -> None
        """Copies a file from the filesystem to a file-like object.

        This may be more efficient that opening and copying files
        manually if the filesystem supplies an optimized method.

        Arguments:
            path (str): Path to a resource.
            file (file-like): A file-like object open for writing in
                binary mode.
            chunk_size (int, optional): Number of bytes to read at a
                time, if a simple copy is used, or `None` to use
                sensible default.
            **options: Implementation specific options required to open
                the source file.

        Note that the file object ``file`` will *not* be closed by this
        method. Take care to close it after this method completes
        (ideally with a context manager).

        Example:
            >>> with open('starwars.mov', 'wb') as write_file:
            ...     my_fs.download('/movies/starwars.mov', write_file)

        """
        with self._lock:
            _res = self._getresource(path)
            if not _res:
                raise errors.ResourceNotFound(path)
            if not _res.isfile():
                raise errors.FileExpected(path)

            # Note: we always write in chunks here, regardless of the chunk_size
            _res.download(file)

    def writebytes(self, path, contents):
        # type: (Text, bytes) -> None
        # FIXME(@althonos): accept bytearray and memoryview as well ?
        """Copy binary data to a file.

        Arguments:
            path (str): Destination path on the filesystem.
            contents (bytes): Data to be written.

        Raises:
            TypeError: if contents is not bytes.

        """
        if not isinstance(contents, bytes):
            raise TypeError("contents must be bytes")
        with self._lock:
            _res = self._getresource(path)
            if _res:
                if not _res.isfile():
                    raise errors.FileExpected(path)
                _res.truncate(0)

            else:
                _path = self.validatepath(path)

                dir_path, file_name = split(_path)
                _dir_res = self._getresource(dir_path)
                if not _dir_res or not _dir_res.isdir():
                    raise errors.ResourceNotFound(path)

                _res = data_fs.mkfile(self._prep_path(_path))

            _res.put_content(contents)

    def upload(self, path, file, chunk_size=None, **options):
        # type: (Text, BinaryIO, Optional[int], **Any) -> None
        """Set a file to the contents of a binary file object.

        This method copies bytes from an open binary file to a file on
        the filesystem. If the destination exists, it will first be
        truncated.

        Arguments:
            path (str): A path on the filesystem.
            file (io.IOBase): a file object open for reading in
                binary mode.
            chunk_size (int, optional): Number of bytes to read at a
                time, if a simple copy is used, or `None` to use
                sensible default.
            **options: Implementation specific options required to open
                the source file.

        Note that the file object ``file`` will *not* be closed by this
        method. Take care to close it after this method completes
        (ideally with a context manager).

        Example:
            >>> with open('~/movies/starwars.mov', 'rb') as read_file:
            ...     my_fs.upload('starwars.mov', read_file)

        """
        with self._lock:
            _res = self._getresource(path)
            if _res:
                if not _res.isfile():
                    raise errors.FileExpected(path)
                _res.truncate(0)

            else:
                _path = self.validatepath(path)

                dir_path, file_name = split(_path)
                _dir_res = self._getresource(dir_path)
                if not _dir_res or not _dir_res.isdir():
                    raise errors.ResourceNotFound(path)

                _res = data_fs.mkfile(self._prep_path(_path))

            # Note: we always read in chunks here, regardless of the chunk_size
            _res.upload(file)

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
            if hasattr(data_fs, "close") and callable(data_fs.close):
                data_fs.close()
        return super().close()

    # ---------------------------------------------------------------- #
    # Internal methods                                                 #
    # Filesystem-specific methods.                                     #
    # ---------------------------------------------------------------- #

    @staticmethod
    def _make_info_from_resource(_res, namespaces):
        def epoch(dt):
            # return time.mktime(dt.utctimetuple())
            return (
                dt - datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)
            ) / datetime.timedelta(seconds=1)

        st_size = _res.size
        st_atime = epoch(_res.modify_time)
        st_mtime = st_atime
        st_ctime = epoch(_res.create_time)

        info = {"basic": {"name": _res.basename(_res.path), "is_dir": _res.isdir()}}
        if "details" in namespaces:
            info["details"] = {
                # "_write": ["accessed", "modified"],
                "_write": ["created", "modified"],
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

    @classmethod
    def _scandir_from_resource(cls, _res, namespaces):
        for _child_res in _res.iget_content():
            yield cls._make_info_from_resource(_child_res, namespaces)

    def _prep_path(self, _path):
        if _path.startswith(self.root_path + "/"):
            return _path
        if _path.startswith("/"):
            _path = _path[1:]
        return join(self.root_path, _path)

    def _reset_path(self, path, confirm=False):
        if not confirm:
            print(
                "Are you sure you want to reset path '%s' - located at '%s' on Cloud Datastore?"
                % (path, self._prep_path(path))
            )
            return False

        with self._lock:
            try:
                _res = self._getresource(path)
            except:
                _res = data_fs._getresource(self._prep_path(path))
            if not _res or not _res.isdir():
                raise errors.DirectoryExpected(path)

            if len(_res.listdir()) < 1:
                return self.opendir(path)

            if not self._is_cached:
                self._stop_cache(False)
                _res.delete(recursive=True)
                self._stop_cache(True)
            else:
                _res.delete(recursive=True)

            _res = data_fs.mkdir(self._prep_path(path))
            return self.opendir(path)

    def _stop_cache(self, confirm=False):
        if confirm:
            self._is_cached = False
        else:
            self._is_cached = True
        data_fs.stop_cache(confirm)

    def _getresource(self, path):
        # type: (Text) -> bool
        """Get the internal resource for a path (Dir, File or None).

        Arguments:
            path (str): Path to a resource.

        Returns:
            resource: internal resource at the given path (Dir, File or None).

        """
        _path = self.validatepath(path)
        return data_fs._getresource(self._prep_path(_path))

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.root_path}')"

    @staticmethod
    def _btopen(path, mode="r"):
        """Open the file (eg. return a BtIO object)"""
        stream = data_fs.btopen(path, mode)
        _mode = Mode(mode)
        if _mode.truncate:
            stream.seek(0)
            stream.truncate()
        if _mode.reading and _mode.writing:
            stream = io.BufferedRandom(stream)
        elif _mode.reading:
            stream = io.BufferedReader(stream)
        elif _mode.writing or _mode.appending:
            stream = io.BufferedWriter(stream)
        # if not _mode.reading:
        #     stream.readable = lambda: False  # mock a write-only stream
        # if not _mode.writing:
        #     stream.writable = lambda: False  # mock a read-only stream
        if _mode.appending:
            stream.seek(0, 2)  # io.SEEK_END
        io_object = RawWrapper(stream, mode=mode, name=path)
        return io_object


class WrapDatastoreFS(WrapFS):
    def __init__(self, root_path=None):
        self._temp_fs_url = "temp://__datastore_tempfs__"
        # self._temp_fs_url = "mem://"
        self._temp_fs = open_fs(self._temp_fs_url)
        print(self._temp_fs)
        # self._meta = {}
        super().__init__(self._temp_fs)


@registry.install
class DatastoreOpener(Opener):

    protocols = ["datastore"]

    def open_fs(self, fs_url, parse_result, writeable, create, cwd):
        data_fs = DatastoreFS()
        return data_fs


def main():
    data_fs = DatastoreFS("/")
    # data_fs = WrapDatastoreFS()
    # data_fs = open_fs("datastore://")
    data_fs.tree()
    data_fs.close()
    return data_fs


if __name__ == "__main__":
    result = main()
    from pprint import pprint

    pprint(result)
    pprint(result.root_path)
    pprint(result.root_res.__dict__)
