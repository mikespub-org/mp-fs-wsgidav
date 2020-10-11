import mimetypes
import os.path
import time
from pathlib import PurePosixPath


class GenericPath(PurePosixPath):
    """
    Base Filesystem providing common methods, inherited by DAV/FS/OS and Dispatch
    """

    __slots__ = "_root_path"

    # see https://github.com/python/cpython/blob/3.8/Lib/pathlib.py
    def __new__(cls, *args):
        if len(args) > 0:
            fstype, path = args[0].split("/", 1)
            # print(fstype, ":", path)
            # CHECKME: return LocalPath etc. based on fstype!? Nope, see DispatchPath below...
            # if fstype == "os":
            #     from .local import LocalPath
            #     return LocalPath.__new__(path)
        return super().__new__(cls, *args)

    def __init__(self, *args):
        self._root_path = None
        if len(args) > 0:
            self.set_root(args[0])
        # super().__init__()

    def roots(self):
        return ["os", "fs", "dav", "fire", "data_todo"]

    def set_root(self, path):
        root, path = path.split("/", 1)
        if self._root_path == root:
            return path

        self._root_path = root
        raise NotImplementedError

    def filesystem(self):
        return self

    def scandir(self, path=None):
        if path is None or path == "":
            return self.ilist_roots()
        return self.ilist_files(path)

    def ilist_roots(self):
        # yield self.add_parent()
        for root in self.roots():
            yield self.make_dirinfo(root)

    def add_parent(self):
        return self.make_dirinfo("..")

    def make_dirinfo(self, name):
        fileinfo = {}
        fileinfo["name"] = name
        fileinfo["name"] += "/"
        fileinfo["size"] = 0
        fileinfo["date"] = time.strftime("%Y-%m-%d %H:%M", time.gmtime())
        fileinfo["type"] = guess_mime_type(fileinfo["name"])
        return fileinfo

    def ilist_files(self, path):
        path = self.set_root(path)
        raise NotImplementedError

    def list_files(self, path=None, sortkey="name"):
        # if path is None:
        #     return list(self.ilist_roots())
        files = list(self.scandir(path))
        files.insert(0, self.add_parent())
        if sortkey not in ("name", "size", "date", "type"):
            sortkey = "name"
        if sortkey == "name":
            return sorted(files, key=lambda a: a[sortkey])
        return sorted(files, key=lambda a: a[sortkey], reverse=True)

    def iterdir(self):
        raise NotImplementedError


class DispatchPath(GenericPath):
    """
    Dispatcher Filesystem using fstype_object scandir() and ilist_files()
    """

    __slots__ = "_fstypes"

    def __init__(self, *args):
        self._fstypes = {}
        super().__init__(*args)

    def set_root(self, path):
        root, path = path.split("/", 1)
        if self._root_path == root:
            return path

        self._root_path = root
        if self.get_fstype_object(root):
            return path

        raise NotImplementedError

    def get_fstype_object(self, fstype=None):
        if fstype is None:
            fstype = self._root_path
        if fstype in self._fstypes:
            return self._fstypes[fstype]

        if fstype == "os":
            from .local import LocalPath

            self._fstypes[fstype] = LocalPath()

        elif fstype == "fs":
            from .fs import FsPath

            self._fstypes[fstype] = FsPath()

        elif fstype == "dav":
            from .dav import DavPath

            self._fstypes[fstype] = DavPath()

        elif fstype == "fire":
            from .fire import FirePath

            self._fstypes[fstype] = FirePath()

        elif fstype == "data_todo":
            from .data_todo import DataPath

            self._fstypes[fstype] = DataPath()

        else:
            raise ValueError(
                "Invalid filesystem type '%s'" % fstype.replace("<", "&lt;")
            )

        return self._fstypes[fstype]

    def filesystem(self):
        fsobj = self.get_fstype_object()
        return fsobj.filesystem()

    def ilist_files(self, path):
        path = self.set_root(path)
        fsobj = self.get_fstype_object()
        # print(repr(fsobj), repr(path))
        return fsobj.scandir(path)


# https://stackoverflow.com/questions/38307995/create-os-direntry
# class GenericDirEntry(os.DirEntry):
class GenericDirEntry:
    def __init__(self, path):
        # self.path = os.path.realpath(path)
        # self.name = os.path.basename(self.path)
        # self.is_dir = os.path.isdir(self.path)
        # self.stat = lambda: os.stat(self.path)
        pass


def guess_mime_type(filename):
    if filename.endswith("/"):
        return "inode/directory"
    (mimetype, encoding) = mimetypes.guess_type(filename, strict=False)
    if mimetype is not None:
        return mimetype
    ext = os.path.splitext(filename)[1].lower()
    mime_types = {
        ".css": "text/css",
        ".csv": "text/csv",
        ".flv": "video/x-flv",
        ".gif": "image/gif",
        ".ico": "image/x-icon",
        ".jpeg": "image/jpeg",
        ".jpg": "image/jpeg",
        ".js": "application/x-javascript",
        ".json": "application/json",
        ".md": "text/markdown",
        ".mo": "application/octet-stream",  # gettext machine object
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".po": "text/plain",  # gettext portable object
        ".rst": "text/x-rst",
        ".svg": "image/svg+xml",
        ".ttf": "font/ttf",
        ".txt": "text/plain",
        ".wmv": "video/x-ms-wmv",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".yaml": "text/yaml",
        ".zip": "application/zip",
    }
    if ext in mime_types:
        return mime_types[ext]
    # print(filename, ext)
    return
