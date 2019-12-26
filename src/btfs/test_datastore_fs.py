# https://docs.pyfilesystem.org/en/latest/implementers.html#testing-filesystems
from .datastore_fs import DatastoreFS, WrapDatastoreFS
from . import bt_fs
import unittest

# import pytest
from fs.test import FSTestCases


class TestDatastoreFS(FSTestCases, unittest.TestCase):
    def make_fs(self):
        # Return an instance of your FS object here - disable caching on client side for test
        ds_fs = DatastoreFS(root_path="/_playground_", use_cache=False)
        # Clean up the test playground before we start, so be careful with the root_path above!
        items = ds_fs.listdir("/")
        if len(items) > 0:
            print("Cleaning up root path %s" % ds_fs.root_path)
            ds_fs._reset_path("/", True)
        return ds_fs


# class TestWrapDatastoreFS(FSTestCases, unittest.TestCase):
#     def make_fs(self):
#         # Return an instance of your FS object here
#         return WrapDatastoreFS()


class TestDatastoreOpener(unittest.TestCase):
    def test_open_datastore(self):
        from fs.opener import open_fs

        ds_fs = open_fs("datastore://")
        self.assertIsInstance(ds_fs, DatastoreFS)
