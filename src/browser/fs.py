import os.path
from . import GenericPath, GenericDirEntry, guess_mime_type


class FsPath(GenericPath):
    """
    PyFilesystem2 Filesystem using root_fs.scandir()
    """

    __slots__ = ("_root_fs")

    def __init__(self, *args):
        self._root_fs = None
        super().__init__(*args)

    def roots(self):
        return ["temp", "user", "data_fs", "data_db", "dav2fs", "fire_fs_wip", "fire_db"]

    def set_root(self, path):
        root, path = path.split("/", 1)
        if self._root_path == root:
            return path

        self._root_path = root
        # namespaces = ["details"]
        if root == "temp":
            # Open the PyFilesystem2 filesystem as source
            # from fs import open_fs
            from fs.osfs import OSFS

            self._root_fs = OSFS("/tmp")

        elif root == "user":
            # Open the PyFilesystem2 filesystem as source
            # from fs import open_fs
            from fs.osfs import OSFS

            self._root_fs = OSFS(os.path.expanduser("~"))

        elif root == "data_fs":
            from data.datastore_fs import DatastoreFS

            self._root_fs = DatastoreFS("/")

        elif root == "dav2fs":
            # Open the DAV Provider as source
            from mapper.fs_from_dav_provider import DAVProvider2FS
            from wsgidav.fs_dav_provider import FilesystemProvider
            from data.datastore_dav import DatastoreDAVProvider

            # dav_provider = FilesystemProvider(BASE_DIR)
            dav_provider = DatastoreDAVProvider()
            self._root_fs = DAVProvider2FS(dav_provider)

        elif root == "data_db":
            # Database explorer with PyFilesystem2
            from data.datastore_db import DatastoreDB

            self._root_fs = DatastoreDB()
            # namespaces = ["details", "properties"]

        elif root == "fire_fs_wip":
            from fire.firestore_fs import FirestoreFS

            self._root_fs = FirestoreFS("/")

        elif root == "fire_db":
            # Database explorer with PyFilesystem2
            from fire.firestore_db import FirestoreDB

            self._root_fs = FirestoreDB()
            # namespaces = ["details", "properties"]

        else:
            raise ValueError("Invalid PyFilesystem2 root '%s'" % root.replace("<", "&lt;"))

        return path

    def filesystem(self):
        if self._root_fs:
            return self._root_fs
        return self

    def get_namespaces(self):
        namespaces = ["details"]
        if self._root_path in ("data_db", "fire_db"):
            namespaces.append("properties")
        return namespaces

    def ilist_files(self, path):
        path = self.set_root(path)
        if path is None:
            path = ""
        namespaces = self.get_namespaces()
        # info = self._root_fs.getinfo(path, namespaces=namespaces).raw
        # print(info)
        for info in self._root_fs.scandir(path, namespaces=namespaces):
            # print(info, info.raw, dir(info))
            fileinfo = {}
            fileinfo["name"] = info.name
            if info.is_dir:
                fileinfo["name"] += "/"
                fileinfo["size"] = 0
            else:
                fileinfo["size"] = info.size
            fileinfo["date"] = info.modified.strftime("%Y-%m-%d %H:%M")
            fileinfo["type"] = guess_mime_type(fileinfo["name"])
            yield fileinfo

    def iterdir(self):
        raise NotImplementedError


# https://stackoverflow.com/questions/38307995/create-os-direntry
# class FsDirEntry(os.DirEntry):
class FsDirEntry(GenericDirEntry):
    def __init__(self, path):
        # self.path = os.path.realpath(path)
        # self.name = os.path.basename(self.path)
        # self.is_dir = os.path.isdir(self.path)
        # self.stat = lambda: os.stat(self.path)
        pass

