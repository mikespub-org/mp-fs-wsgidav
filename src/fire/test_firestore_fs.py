# https://docs.pyfilesystem.org/en/latest/implementers.html#testing-filesystems
from .firestore_fs import FirestoreFS, WrapFirestoreFS
import unittest

import pytest
from fs.test import FSTestCases

# Create the test playground if needed
# fire_fs = FirestoreFS(root_path="/_playground_", use_cache=False)
fire_fs = FirestoreFS(root_path="/_playground_")
fire_fs._reset_path("/", True)
fire_fs.close()
test_count = 0


class TestFirestoreFS(FSTestCases, unittest.TestCase):
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
        fire_fs = FirestoreFS(
            root_path="/_playground_/%02d_%s" % (test_count, test_name),
        )
        return fire_fs

    def destroy_fs(self, fire_fs):
        try:
            fire_fs._reset_path("/", True)
        except:
            pass
        fire_fs.close()


# class TestWrapFirestoreFS(FSTestCases, unittest.TestCase):
#     def make_fs(self):
#         # Return an instance of your FS object here
#         return WrapFirestoreFS()


class TestFirestoreOpener(unittest.TestCase):
    def test_open_firestore(self):
        from fs.opener import open_fs

        fire_fs = open_fs("firestore://")
        self.assertIsInstance(fire_fs, FirestoreFS)
