import os.path
import time
from . import GenericPath, GenericDirEntry, guess_mime_type


class DavPath(GenericPath):
    """
    Wsgi DAV Provider using resource_inst.get_member_list()
    """

    __slots__ = ("_dav_provider")

    def __init__(self, *args):
        self._dav_provider = None
        super().__init__(*args)

    def roots(self):
        return ["temp", "user", "data_dav", "fs2dav", "fire_dav_todo"]

    def set_root(self, path):
        root, path = path.split("/", 1)
        if self._root_path == root:
            return path

        self._root_path = root
        if root == "temp":
            # Open the DAV Provider as source
            from wsgidav.fs_dav_provider import FilesystemProvider

            self._dav_provider = FilesystemProvider("/tmp")

        elif root == "user":
            from wsgidav.fs_dav_provider import FilesystemProvider

            self._dav_provider = FilesystemProvider(os.path.expanduser("~"))

        elif root == "data_dav":
            from data.datastore_dav import DatastoreDAVProvider

            self._dav_provider = DatastoreDAVProvider()

        elif root == "fs2dav":
            # Open the PyFilesystem2 filesystem as source
            from mapper.dav_provider_from_fs import FS2DAVProvider

            # from fs import open_fs
            from fs.osfs import OSFS
            from data.datastore_fs import DatastoreFS

            # source_fs = open_fs("osfs://" + BASE_DIR)
            # source_fs = OSFS(BASE_DIR)
            source_fs = DatastoreFS("/")
            self._dav_provider = FS2DAVProvider(source_fs)

        elif root == "fire_dav_todo":
            from fire.firestore_dav import FirestoreDAVProvider

            self._dav_provider = FirestoreDAVProvider()

        else:
            raise ValueError("Invalid Wsgi DAV Provider root '%s'" % root.replace("<", "&lt;"))

        return path

    def filesystem(self):
        if self._dav_provider:
            return self._dav_provider
        return self

    def get_environ(self):
        environ = {}
        # dav_config = None
        # from wsgidav_app
        # environ["wsgidav.config"] = dav_config or {}
        environ["wsgidav.provider"] = self._dav_provider
        # environ["wsgidav.verbose"] = 3
        # from http_authenticator
        # environ["wsgidav.auth.realm"] = "Filesystem"
        # environ["wsgidav.auth.user_name"] = ""
        # environ["wsgidav.auth.roles"] = None
        # environ["wsgidav.auth.permissions"] = None
        return environ

    def ilist_files(self, path):
        path = self.set_root(path)
        if path is None:
            path = ""
        if not path.startswith("/"):
            path = "/%s" % path
        environ = self.get_environ()
        res = self._dav_provider.get_resource_inst(path, environ)
        # print(res)
        for child_res in res.get_member_list():
            # print(child_res, dir(child_res))
            fileinfo = {}
            fileinfo["name"] = child_res.name
            if child_res.is_collection:
                fileinfo["name"] += "/"
                fileinfo["size"] = 0
            else:
                fileinfo["size"] = child_res.get_content_length()
            fileinfo["date"] = time.strftime(
                "%Y-%m-%d %H:%M", time.gmtime(child_res.get_last_modified())
            )
            fileinfo["type"] = guess_mime_type(fileinfo["name"])
            yield fileinfo

    def iterdir(self):
        raise NotImplementedError


# https://stackoverflow.com/questions/38307995/create-os-direntry
# class DavDirEntry(os.DirEntry):
class DavDirEntry(GenericDirEntry):
    def __init__(self, path):
        # self.path = os.path.realpath(path)
        # self.name = os.path.basename(self.path)
        # self.is_dir = os.path.isdir(self.path)
        # self.stat = lambda: os.stat(self.path)
        pass

