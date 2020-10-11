import os.path
import time
from . import GenericPath, GenericDirEntry, guess_mime_type


class FirePath(GenericPath):
    """
    Firestore Filesystem using tree.ilist_dir_docs()
    """

    __slots__ = ["_client", "_tree"]

    def __init__(self, *args):
        from fire.db import get_client

        self._client = get_client()
        self._tree = None
        super().__init__(*args)

    def roots(self):
        return [
            "test",
            "tree",
            "flat",
            "hash",
        ]

    def set_root(self, path):
        root, path = path.split("/", 1)
        if self._root_path == root:
            return path

        self._root_path = root
        if root in self.roots():
            from fire.tree import get_structure

            self._tree = get_structure(root, self._client)

        else:
            raise ValueError("Invalid Firestore root '%s'" % root.replace("<", "&lt;"))

        return path

    def filesystem(self):
        if self._tree:
            return self._tree
        return self

    def ilist_files(self, path):
        from fire.api import item_to_dict

        path = self.set_root(path)
        if path is None:
            path = ""
        if not path.startswith("/"):
            path = "/" + path
        if len(path) > 1 and path[1:].endswith("/"):
            path = path[:-1]
        # print("Path:", path)
        for doc in self._tree.ilist_dir_docs(path):
            info = item_to_dict(doc)
            if self._tree.with_path:
                doc_path = info.get("path")
            else:
                doc_path = self._tree.convert_ref_to_path(doc.reference.path)
            # print(doc_path, doc.reference.path, info)
            # if self._tree.with_parent_path:
            #     print("Parent Ref:", doc.get("parent_ref"))
            # if self._tree.with_path:
            #     assert self._tree.convert_path_to_ref(path) == doc.reference.id
            # else:
            #     assert path == self._tree.convert_ref_to_path(doc.reference.path)
            fileinfo = {}
            fileinfo["name"] = doc_path.split("/")[-1]
            if "count" in info:
                fileinfo["name"] += "/"
                fileinfo["size"] = 0
            else:
                fileinfo["size"] = info.get("size")
            fileinfo["date"] = time.strftime(
                "%Y-%m-%d %H:%M", time.gmtime(info.get("update_time"))
            )
            fileinfo["type"] = guess_mime_type(fileinfo["name"])
            yield fileinfo

    def iterdir(self):
        raise NotImplementedError


# https://stackoverflow.com/questions/38307995/create-os-direntry
# class FireDirEntry(os.DirEntry):
class FireDirEntry(GenericDirEntry):
    def __init__(self, path):
        # self.path = os.path.realpath(path)
        # self.name = os.path.basename(self.path)
        # self.is_dir = os.path.isdir(self.path)
        # self.stat = lambda: os.stat(self.path)
        pass
