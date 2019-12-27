#!/usr/bin/env python3
"""Basic support of Google Cloud Firestore as filesystem with PyFilesystem2

Example opening directly with FirestoreFS():
    >>> from firestore_fs import FirestoreFS
    >>> fi_fs = FirestoreFS()
    >>> fi_fs.listdir("/")

Example opening via a FS URL "firestore://"
    >>> import fs
    >>> import firestore_fs  # not registered by default, so we need to import first
    >>> fi_fs = fs.open_fs("firestore://")
    >>> fi_fs.listdir("/")

For more information on PyFilesystem2, see https://docs.pyfilesystem.org/
"""
from fs import errors
from fs.base import FS
from fs.info import Info
from fs.mode import Mode
from fs.wrapfs import WrapFS
from fs.opener import open_fs
from functools import partial
from datetime import datetime
import itertools
import os.path
import logging

# for opener
from fs.opener import Opener
from fs.opener import registry

# use the fire_fs module here - TODO
from . import fire_fs

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

__all__ = ["FirestoreFS", "WrapFirestoreFS"]


log = logging.getLogger(__name__)


class FirestoreFS(FS):
    def __init__(self, root_path=None, use_cache=True):
        # self._meta = {}
        if root_path is None:
            root_path = "/_firestore_fs_"
        _root_path = self.validatepath(root_path)
        _root_path = _root_path.replace(os.sep, "/")
        if not _root_path.startswith("/"):
            _root_path = "/" + _root_path
        self._is_cached = True
        if not use_cache:
            self._stop_cache(True)
        _res = fire_fs.getdir(_root_path)
        if _res and fire_fs.isdir(_res):
            log.info("Root path exists %s" % _root_path)
        else:
            log.info("Creating root path %s" % _root_path)
            _res = fire_fs.mkdir(_root_path)
        log.info("Resource: %s" % _res)
        self.root_path = _root_path
        self.root_res = _res
        super(FirestoreFS, self).__init__()

    # https://docs.pyfilesystem.org/en/latest/implementers.html#essential-methods
    # From https://github.com/PyFilesystem/pyfilesystem2/blob/master/fs/base.py

    @classmethod
    def _make_details_from_stat(cls, stat_result):
        # type: (os.stat_result) -> Dict[Text, object]
        """Make a *details* info dict from an `os.stat_result` object.
        """
        details = {
            # "_write": ["accessed", "modified"],
            "_write": ["created", "modified"],
            "accessed": stat_result.st_atime,
            "modified": stat_result.st_mtime,
            "created": stat_result.st_ctime,
            "size": stat_result.st_size,
            # "type": int(cls._get_type_from_stat(stat_result)),
        }
        return details

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
        self.check()
        namespaces = namespaces or ()
        _path = self.validatepath(path)
        _res = fire_fs._getresource(self._prep_path(_path))
        if _res is None:
            raise errors.ResourceNotFound(path)

        _stat = fire_fs.stat(_res)
        info = {
            "basic": {"name": os.path.basename(_path), "is_dir": fire_fs.isdir(_res)}
        }
        if "details" in namespaces:
            info["details"] = self._make_details_from_stat(_stat)
            if fire_fs.isdir(_res):
                info["details"]["type"] = 1
            else:
                info["details"]["type"] = 2
        if "stat" in namespaces:
            info["stat"] = {
                k: getattr(_stat, k) for k in dir(_stat) if k.startswith("st_")
            }
        # if "lstat" in namespaces:
        #     info["lstat"] = {
        #         k: getattr(_lstat, k) for k in dir(_lstat) if k.startswith("st_")
        #     }
        # if "link" in namespaces:
        #     info["link"] = self._make_link_info(sys_path)
        # if "access" in namespaces:
        #     info["access"] = self._make_access_from_stat(_stat)

        return Info(info)

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
        self.check()
        _path = self.validatepath(path)
        with self._lock:
            _res = fire_fs._getresource(self._prep_path(_path))
            if not _res:
                raise errors.ResourceNotFound(path)

            if not fire_fs.isdir(_res):
                raise errors.DirectoryExpected(path)

            return fire_fs.listdir(_res)

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
        self.check()
        # mode = Permissions.get_mode(permissions)
        _path = self.validatepath(path)

        with self._lock:
            if _path == "/":
                if recreate:
                    return self.opendir(path)
                else:
                    raise errors.DirectoryExists(path)

            dir_path, dir_name = os.path.split(_path)

            _dir_res = fire_fs._getresource(self._prep_path(dir_path))
            if not _dir_res or not fire_fs.isdir(_dir_res):
                raise errors.ResourceNotFound(path)

            if dir_name in fire_fs.listdir(_dir_res):
                if not recreate:
                    raise errors.DirectoryExists(path)

                _res = fire_fs._getresource(self._prep_path(_path))
                if _res and fire_fs.isdir(_res):
                    return self.opendir(path)

            _res = fire_fs.mkdir(self._prep_path(_path))
            return self.opendir(path)

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
        self.check()
        _mode = Mode(mode)
        _mode.validate_bin()
        _path = self.validatepath(path)
        dir_path, file_name = os.path.split(_path)

        if not file_name:
            raise errors.FileExpected(path)

        with self._lock:
            _dir_res = fire_fs._getresource(self._prep_path(dir_path))
            if not _dir_res or not fire_fs.isdir(_dir_res):
                raise errors.ResourceNotFound(path)

            if _mode.create:
                if file_name in fire_fs.listdir(_dir_res):
                    if _mode.exclusive:
                        raise errors.FileExists(path)

                    _res = fire_fs._getresource(self._prep_path(_path))
                    if not _res or fire_fs.isdir(_res):
                        raise errors.FileExpected(path)

                    return fire_fs.btopen(_res, mode)

                return fire_fs.btopen(self._prep_path(_path), mode)

            if file_name not in fire_fs.listdir(_dir_res):
                raise errors.ResourceNotFound(path)

            _res = fire_fs._getresource(self._prep_path(_path))
            if not _res or fire_fs.isdir(_res):
                raise errors.FileExpected(path)

            return fire_fs.btopen(_res, mode)

    def remove(self, path):
        # type: (Text) -> None
        """Remove a file from the filesystem.

        Arguments:
            path (str): Path of the file to remove.

        Raises:
            fs.errors.FileExpected: If the path is a directory.
            fs.errors.ResourceNotFound: If the path does not exist.

        """
        self.check()
        _path = self.validatepath(path)

        with self._lock:
            _res = fire_fs._getresource(self._prep_path(_path))
            if not _res:
                raise errors.ResourceNotFound(path)

            if not fire_fs.isfile(_res):
                raise errors.FileExpected(path)

            fire_fs.unlink(_res)

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
        self.check()
        _path = self.validatepath(path)
        if _path == "/" or _path == "" or _path is None:
            raise errors.RemoveRootError()

        with self._lock:
            _res = fire_fs._getresource(self._prep_path(_path))
            if not _res:
                raise errors.ResourceNotFound(path)

            if not fire_fs.isdir(_res):
                raise errors.DirectoryExpected(path)

            if len(fire_fs.listdir(_res)) > 0:
                raise errors.DirectoryNotEmpty(path)

            fire_fs.rmdir(_res)

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
        _path = self.validatepath(path)
        with self._lock:
            _res = fire_fs._getresource(self._prep_path(_path))
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
                        _res.create_time = datetime.fromtimestamp(created_time)
                    if modified_time:
                        _res.modify_time = datetime.fromtimestamp(modified_time)
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
        _path = self.validatepath(path)
        try:
            # self.getinfo(path)
            return fire_fs.exists(self._prep_path(_path))
        # except errors.ResourceNotFound:
        #     return False
        except AssertionError:
            return False
        # else:
        #     return True

    def isdir(self, path):
        # type: (Text) -> bool
        """Check if a path maps to an existing directory.

        Parameters:
            path (str): A path on the filesystem.

        Returns:
            bool: `True` if ``path`` maps to a directory.

        """
        _path = self.validatepath(path)
        try:
            # return self.getinfo(path).is_dir
            return fire_fs.isdir(self._prep_path(_path))
        # except errors.ResourceNotFound:
        #     return False
        except AssertionError:
            return False
        # else:
        #     return True

    def isfile(self, path):
        # type: (Text) -> bool
        """Check if a path maps to an existing file.

        Parameters:
            path (str): A path on the filesystem.

        Returns:
            bool: `True` if ``path`` maps to a file.

        """
        _path = self.validatepath(path)
        try:
            # return not self.getinfo(path).is_dir
            return fire_fs.isfile(self._prep_path(_path))
        # except errors.ResourceNotFound:
        #     return False
        except AssertionError:
            return False
        # else:
        #     return True

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
        self.check()
        namespaces = namespaces or ()
        _path = self.validatepath(path)

        # TODO: use information from Dir.get_content() directly
        info = (
            self.getinfo(
                os.path.join(_path, name).replace(os.sep, "/"), namespaces=namespaces
            )
            for name in self.listdir(path)
        )
        iter_info = iter(info)
        if page is not None:
            start, end = page
            iter_info = itertools.islice(iter_info, start, end)
        return iter_info

    def filterdir(
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

    def copy(self, src_path, dst_path, overwrite=False):
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
        _src_path = self.validatepath(src_path)
        _dst_path = self.validatepath(dst_path)
        with self._lock:
            if not overwrite and self.exists(dst_path):
                raise errors.DestinationExists(dst_path)

            dir_path, file_name = os.path.split(_dst_path)
            _dir_res = fire_fs._getresource(self._prep_path(dir_path))
            if not _dir_res or not fire_fs.isdir(_dir_res):
                raise errors.ResourceNotFound(path)

            fire_fs.copyfile(self._prep_path(_src_path), self._prep_path(_dst_path))

    # ---------------------------------------------------------------- #
    # Internal methods                                                 #
    # Filesystem-specific methods.                                     #
    # ---------------------------------------------------------------- #

    def _prep_path(self, _path):
        if _path.startswith(self.root_path + "/"):
            return _path
        if _path.startswith("/"):
            _path = _path[1:]
        return os.path.join(self.root_path, _path).replace(os.sep, "/")

    def _reset_path(self, path, confirm=False):
        _path = self.validatepath(path)
        if not confirm:
            print(
                "Are you sure you want to reset path '%s' - located at '%s' on Cloud Firestore?"
                % (path, self._prep_path(_path))
            )
            return False

        with self._lock:
            _res = fire_fs._getresource(self._prep_path(_path))
            if not _res or fire_fs.isfile(_res):
                raise errors.DirectoryExpected(path)

            has_cache = self._is_cached
            if not has_cache:
                self._stop_cache(False)
            fire_fs.rmtree(_res)
            if not has_cache:
                self._stop_cache(True)

            _res = fire_fs.mkdir(self._prep_path(_path))
            return self.opendir(path)

    def _stop_cache(self, confirm=False):
        if confirm:
            self._is_cached = False
        else:
            self._is_cached = True
        fire_fs.stop_cache(confirm)

    def _getresource(self, path):
        # type: (Text) -> bool
        """Get the internal resource for a path (Dir, File or None).

        Arguments:
            path (str): Path to a resource.

        Returns:
            resource: internal resource at the given path (Dir, File or None).

        """
        _path = self.validatepath(path)
        return fire_fs._getresource(self._prep_path(_path))


class WrapFirestoreFS(WrapFS):
    def __init__(self, root_path=None):
        self._temp_fs_url = "temp://__firestore_tempfs__"
        # self._temp_fs_url = "mem://"
        self._temp_fs = open_fs(self._temp_fs_url)
        print(self._temp_fs)
        # self._meta = {}
        super(WrapFirestoreFS, self).__init__(self._temp_fs)


@registry.install
class FirestoreOpener(Opener):

    protocols = ["firestore"]

    def open_fs(self, fs_url, parse_result, writeable, create, cwd):
        fi_fs = FirestoreFS()
        return fi_fs


def main():
    fi_fs = FirestoreFS()
    # fi_fs = WrapFirestoreFS()
    # fi_fs = open_fs("firestore://")
    fi_fs.tree()
    return fi_fs


if __name__ == "__main__":
    result = main()
    from pprint import pformat, pprint

    pprint(result)
    pprint(result.root_path)
    pprint(result.root_res.__dict__)
