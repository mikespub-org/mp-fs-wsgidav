import os
import time
from . import GenericPath, GenericDirEntry, guess_mime_type


class LocalPath(GenericPath):
    """
    Local Filesystem using os.scandir()
    """

    __slots__ = "_base_dir"

    def __init__(self, *args):
        self._base_dir = None
        super().__init__(*args)

    def roots(self):
        return ["temp", "user", "here"]

    def set_root(self, path):
        self._str = path
        root, path = path.split("/", 1)
        if self._root_path == root:
            return path

        self._root_path = root
        if root == "temp":
            self._base_dir = "/tmp"

        elif root == "user":
            self._base_dir = os.path.expanduser("~")

        elif root == "here":
            self._base_dir = os.path.abspath(".")

        else:
            raise ValueError(
                "Invalid local filesystem root '%s'" % root.replace("<", "&lt;")
            )

        # see https://github.com/python/cpython/blob/3.8/Lib/pathlib.py -> used in __str__
        # self._drv, self._root, self._parts = self._parse_args(self._base_dir)
        # self._str = self._format_parsed_parts(self._drv, self._root, self._parts) or '.'
        # self._str = root
        return path

    def ilist_files(self, path):
        path = self.set_root(path)
        if path is not None:
            root = os.path.join(self._base_dir, path)
        else:
            root = self._base_dir
        for entry in os.scandir(root):
            # print(entry, dir(entry))
            fileinfo = {}
            fileinfo["name"] = entry.name
            stat = entry.stat()
            if entry.is_dir():
                fileinfo["name"] += "/"
                fileinfo["size"] = 0
            else:
                fileinfo["size"] = stat.st_size
            fileinfo["date"] = time.strftime(
                "%Y-%m-%d %H:%M", time.gmtime(stat.st_mtime)
            )
            fileinfo["type"] = guess_mime_type(fileinfo["name"])
            yield fileinfo

    def iterdir(self):
        raise NotImplementedError


# https://stackoverflow.com/questions/38307995/create-os-direntry
# class LocalDirEntry(os.DirEntry):
class LocalDirEntry(GenericDirEntry):
    def __init__(self, path):
        self.path = os.path.realpath(path)
        self.name = os.path.basename(self.path)
        self.is_dir = os.path.isdir(self.path)
        self.stat = lambda: os.stat(self.path)
