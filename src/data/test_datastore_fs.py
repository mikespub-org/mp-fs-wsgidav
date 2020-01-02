# https://docs.pyfilesystem.org/en/latest/implementers.html#testing-filesystems
from .datastore_fs import DatastoreFS, WrapDatastoreFS
import unittest

import pytest
from fs.test import FSTestCases

# Create the test playground if needed
# data_fs = DatastoreFS(root_path="/_playground_", use_cache=False)
data_fs = DatastoreFS(root_path="/_playground_")
data_fs._reset_path("/", True)
data_fs.close()
test_count = 0


class TestDatastoreFS(FSTestCases, unittest.TestCase):
    def make_fs(self):
        global test_count
        test_count += 1
        test_name = self.id().split(".")[-1]
        if test_name in ("test_upload", "test_download"):
            pytest.skip("No time to waste...")
            return
        if test_name in ("test_settimes"):
            pytest.xfail("Modify time is updated automatically on model.put()")
        # Return an instance of your FS object here - disable caching on client side for test
        data_fs = DatastoreFS(
            root_path="/_playground_/%02d_%s" % (test_count, test_name),
        )
        return data_fs

    def destroy_fs(self, data_fs):
        try:
            data_fs._reset_path("/", True)
        except:
            pass
        data_fs.close()


# class TestWrapDatastoreFS(FSTestCases, unittest.TestCase):
#     def make_fs(self):
#         # Return an instance of your FS object here
#         return WrapDatastoreFS()


class TestDatastoreOpener(unittest.TestCase):
    def test_open_datastore(self):
        from fs.opener import open_fs

        data_fs = open_fs("datastore://")
        self.assertIsInstance(data_fs, DatastoreFS)
