# https://docs.pyfilesystem.org/en/latest/implementers.html#testing-filesystems
from .datastore_fs import DatastoreFS, WrapDatastoreFS
from . import bt_fs
import unittest

# import pytest
from fs.test import FSTestCases

# Create the test playground if needed
ds_fs = DatastoreFS(root_path="/_playground_", use_cache=False)
ds_fs._reset_path("/", True)
ds_fs.close()
test_count = 0


class TestDatastoreFS(FSTestCases, unittest.TestCase):
    def make_fs(self):
        global test_count
        test_count += 1
        # Return an instance of your FS object here - disable caching on client side for test
        ds_fs = DatastoreFS(root_path="/_playground_/%02d_%s" % (test_count, self.id().split('.')[-1]), use_cache=False)
        return ds_fs

    def destroy_fs(self, ds_fs):
        ds_fs._reset_path("/", True)
        ds_fs.close()

# class TestWrapDatastoreFS(FSTestCases, unittest.TestCase):
#     def make_fs(self):
#         # Return an instance of your FS object here
#         return WrapDatastoreFS()


class TestDatastoreOpener(unittest.TestCase):
    def test_open_datastore(self):
        from fs.opener import open_fs

        ds_fs = open_fs("datastore://")
        self.assertIsInstance(ds_fs, DatastoreFS)
