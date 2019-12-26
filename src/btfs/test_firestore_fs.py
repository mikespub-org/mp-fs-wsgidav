# https://docs.pyfilesystem.org/en/latest/implementers.html#testing-filesystems
from .firestore_fs import FirestoreFS, WrapFirestoreFS
from . import fire_fs
import unittest

# import pytest
from fs.test import FSTestCases


class TestFirestoreFS(FSTestCases, unittest.TestCase):
    def make_fs(self):
        # Return an instance of your FS object here - disable caching on client side for test
        fi_fs = FirestoreFS(root_path="/_playground_", use_cache=False)
        # Clean up the test playground before we start, so be careful with the root_path above!
        items = fi_fs.listdir("/")
        if len(items) > 0:
            print("Cleaning up root path %s" % fi_fs.root_path)
            fi_fs._reset_path("/", True)
        return fi_fs


# class TestWrapFirestoreFS(FSTestCases, unittest.TestCase):
#     def make_fs(self):
#         # Return an instance of your FS object here
#         return WrapFirestoreFS()


class TestFirestoreOpener(unittest.TestCase):
    def test_open_firestore(self):
        from fs.opener import open_fs

        fi_fs = open_fs("firestore://")
        self.assertIsInstance(fi_fs, firestoreFS)
