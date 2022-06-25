#!/usr/bin/env python3
#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: https://opensource.org/licenses/mit-license.php
#
"""Basic support of WsgiDAV DAV Providers as filesystem for PyFilesystem2

Example opening directly with DAVProvider2FS():
    >>> from .fs_from_dav_provider import DAVProvider2FS
    >>> from wsgidav.fs_dav_provider import FilesystemProvider
    >>>
    >>> dav_provider = FilesystemProvider("/tmp")
    >>> # dav_fs.environ["wsgidav.auth.user_name"] = "tester"
    >>> # dav_fs.environ["wsgidav.auth.roles"] = ["admin"]
    >>> dav_fs = DAVProvider2FS(dav_provider)
    >>> dav_fs.listdir("/")

Example opening via a FS URL "dav_provider://"  # TODO
    >>> import fs
    >>> import fs_from_dav_provider  # not registered by default, so we need to import first
    >>>
    >>> dav_fs = fs.open_fs("dav_provider://")
    >>> dav_fs.listdir("/")

For more information on PyFilesystem2, see https://docs.pyfilesystem.org/
For more information on WsgiDAV, see https://wsgidav.readthedocs.io/
"""
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
from fs.path import split
from fs.time import epoch_to_datetime
from fs.wrapfs import WrapFS

__all__ = ["DAVProvider2FS", "WrapDAVProvider2FS"]


log = logging.getLogger(__name__)


class DAVProvider2FS(FS):
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

    def __init__(self, dav_provider, dav_config=None):
        # self._meta = {}
        super().__init__()
        self.provider = dav_provider
        self.provider.share_path = ""
        # TODO: get list of invalid characters from DAV Provider
        self.environ = {}
        # from wsgidav_app
        self.environ["wsgidav.config"] = dav_config or {}
        self.environ["wsgidav.provider"] = self.provider
        self.environ["wsgidav.verbose"] = 3
        # from http_authenticator
        self.environ["wsgidav.auth.realm"] = "DAVProvider2FS"
        self.environ["wsgidav.auth.user_name"] = ""
        self.environ["wsgidav.auth.roles"] = None
        self.environ["wsgidav.auth.permissions"] = None

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

            if not _res.is_collection:
                raise errors.DirectoryExpected(path)

            return _res.get_member_names()

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
            if not _dir_res or not _dir_res.is_collection:
                raise errors.ResourceNotFound(path)

            if dir_name in _dir_res.get_member_names():
                if not recreate:
                    raise errors.DirectoryExists(path)

                _res = self._getresource(path)
                if _res and _res.is_collection:
                    return self.opendir(path)

            _dir_res.create_collection(dir_name)
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
            if not _dir_res or not _dir_res.is_collection:
                raise errors.ResourceNotFound(path)

            if _mode.create:
                if file_name in _dir_res.get_member_names():
                    if _mode.exclusive:
                        raise errors.FileExists(path)

                    _res = self._getresource(path)
                    if not _res or _res.is_collection:
                        raise errors.FileExpected(path)

                    stream = io.BufferedWriter(_res.begin_write())
                    io_object = RawWrapper(
                        stream, mode=_mode.to_platform_bin(), name=path
                    )
                    return io_object

                _res = _dir_res.create_empty_resource(file_name)
                stream = io.BufferedWriter(_res.begin_write())
                io_object = RawWrapper(stream, mode=_mode.to_platform_bin(), name=path)
                return io_object

            if file_name not in _dir_res.get_member_names():
                raise errors.ResourceNotFound(path)

            _res = self._getresource(path)
            if not _res or _res.is_collection:
                raise errors.FileExpected(path)

            if _mode.appending:
                # stream.seek(0, 2)  # io.SEEK_END
                raise NotImplementedError("Appending is not supported")

            if _mode.updating:
                raise NotImplementedError("Updating is not supported")

            if _mode.reading:
                stream = io.BufferedReader(_res.get_content())
                io_object = RawWrapper(stream, mode=_mode.to_platform_bin(), name=path)
                return io_object

            stream = io.BufferedWriter(_res.begin_write())
            io_object = RawWrapper(stream, mode=_mode.to_platform_bin(), name=path)
            return io_object

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

            if _res.is_collection:
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

            if not _res.is_collection:
                raise errors.DirectoryExpected(path)

            if len(_res.get_member_names()) > 0:
                raise errors.DirectoryNotEmpty(path)

            # _res.delete(recursive=False)
            _res.delete()

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
                        pass
                    if modified_time:
                        dt = epoch_to_datetime(modified_time)
                        rfc1123_time = dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
                        _res.set_last_modified(_res.path, rfc1123_time, dry_run=False)

            if "properties" in info:
                prop_names = _res.get_property_names(True)
                for prop_name in prop_names:
                    # let the DAV provider handle the standard live properties
                    if prop_name.startswith("{DAV:}"):
                        continue
                    # skip unknonwn properties
                    if prop_name not in info["properties"]:
                        continue
                    _res.set_property_value(prop_name, info["properties"][prop_name])

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
        if not _res or not _res.is_collection:
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
        if not _res or _res.is_collection:
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

        if not _res.is_collection:
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
            if not _dir_res or not _dir_res.is_collection:
                raise errors.ResourceNotFound(dst_path)

            _src_res = self._getresource(src_path)
            if not _src_res:
                raise errors.ResourceNotFound(src_path)
            if _src_res.is_collection:
                raise errors.FileExpected(src_path)

            _src_res.copy_move_single(_dst_path, is_move=False)

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
        self.validatepath(src_path)
        _dst_path = self.validatepath(dst_path)
        with self._lock:
            if not overwrite and self.exists(dst_path):
                raise errors.DestinationExists(dst_path)

            dir_path, file_name = split(_dst_path)
            _dir_res = self._getresource(dir_path)
            if not _dir_res or not _dir_res.is_collection:
                raise errors.ResourceNotFound(dst_path)

            _src_res = self._getresource(src_path)
            if not _src_res:
                raise errors.ResourceNotFound(src_path)
            if _src_res.is_collection:
                raise errors.FileExpected(src_path)

            if not overwrite and _src_res.support_recursive_move(_dst_path):
                _src_res.move_recursive(_dst_path)
            else:
                # CHECKME: this doesn't actually seem to delete _src_res in DAV Provider
                _src_res.copy_move_single(_dst_path, is_move=True)
                try:
                    _src_res.delete()
                except:
                    pass

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
                if _res.is_collection:
                    raise errors.FileExpected(path)
                if not wipe:
                    return False

                fp = _res.begin_write()
                fp.close()

            else:
                _path = self.validatepath(path)

                dir_path, file_name = split(_path)
                _dir_res = self._getresource(dir_path)
                if not _dir_res or not _dir_res.is_collection:
                    raise errors.ResourceNotFound(path)

                _res = _dir_res.create_empty_resource(file_name)

            return True

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
            if hasattr(self.provider, "close") and callable(self.provider.close):
                self.provider.close()
            self.provider = None
        return super().close()

    # ---------------------------------------------------------------- #
    # Internal methods                                                 #
    # Filesystem-specific methods.                                     #
    # ---------------------------------------------------------------- #

    @staticmethod
    def _make_info_from_resource(_res, namespaces):
        st_size = _res.get_content_length()
        st_atime = _res.get_last_modified()
        st_mtime = st_atime
        st_ctime = _res.get_creation_date()

        info = {"basic": {"name": _res.name, "is_dir": _res.is_collection}}
        if "details" in namespaces:
            write = []
            try:
                dt = epoch_to_datetime(st_mtime)
                rfc1123_time = dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
                _res.set_last_modified(_res.path, rfc1123_time, dry_run=True)
                write.append("modified")
            except Exception:
                pass
            info["details"] = {
                # "_write": ["accessed", "modified"],
                "_write": write,
                "accessed": st_atime,
                "modified": st_mtime,
                "created": st_ctime,
                "size": st_size,
                # "type": int(cls._get_type_from_stat(stat_result)),
            }
            if _res.is_collection:
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
        if "properties" in namespaces:
            info["properties"] = _res.get_properties("allprop")
        # if "lstat" in namespaces:
        #     info["lstat"] = {
        #         k: getattr(_lstat, k) for k in dir(_lstat) if k.startswith("st_")
        #     }
        if "link" in namespaces:
            info["link"] = _res.get_href()
        # if "access" in namespaces:
        #     info["access"] = cls._make_access_from_stat(_stat)

        return Info(info)

    @classmethod
    def _scandir_from_resource(cls, _res, namespaces):
        for _child_res in _res.get_member_list():
            yield cls._make_info_from_resource(_child_res, namespaces)

    def _getresource(self, path):
        # type: (Text) -> bool
        """Get the internal resource for a path. (FS2FileResource, FS2FolderResource or None)

        Arguments:
            path (str): Path to a resource.

        Returns:
            resource: internal resource at the given path (FS2FileResource, FS2FolderResource or None).

        """
        _path = self.validatepath(path)
        return self.provider.get_resource_inst(_path, self.environ)

    def __repr__(self):
        return f"{self.__class__.__name__}({repr(self.provider)})"

    def _reset_path(self, path, confirm=False):
        if not confirm:
            print(
                "Are you sure you want to reset path '{}' on the DAV Provider?".format(
                    path
                )
            )
            return False

        with self._lock:
            _res = self._getresource(path)
            if _res and _res.is_collection:
                self.removetree(path)

            _res = self.makedir(path, recreate=True)
            return self.opendir(path)


class WrapDAVProvider2FS(WrapFS):
    def __init__(self, dav_provider=None):
        self._temp_fs_url = "temp://__dav_provider_tempfs__"
        # self._temp_fs_url = "mem://"
        self._temp_fs = open_fs(self._temp_fs_url)
        print(self._temp_fs)
        # self._meta = {}
        super().__init__(self._temp_fs)


@registry.install
class DAVProvider2FSOpener(Opener):

    protocols = ["dav_provider"]

    def open_fs(self, fs_url, parse_result, writeable, create, cwd):
        dav_provider = None  # TODO: define based on input args
        dav_fs = DAVProvider2FS(dav_provider)
        return dav_fs


def main():
    # from .fs_from_dav_provider import DAVProvider2FS
    from wsgidav.fs_dav_provider import FilesystemProvider

    dav_provider = FilesystemProvider("/tmp")
    dav_fs = DAVProvider2FS(dav_provider)
    # dav_fs = open_fs("dav_provider://")
    # dav_fs = WrapDAVProvider2FS(dav_provider)
    # dav_fs.environ["wsgidav.auth.user_name"] = "tester"
    # dav_fs.environ["wsgidav.auth.roles"] = ["admin"]
    result = dav_fs.tree()
    # result = dav_fs.listdir("/")
    return result


if __name__ == "__main__":
    result = main()
    from pprint import pprint

    pprint(result)
