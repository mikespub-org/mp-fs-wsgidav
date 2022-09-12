# https://docs.pyfilesystem.org/en/latest/implementers.html#testing-filesystems
import unittest

import pytest
from fs.test import FSTestCases
from wsgidav.fs_dav_provider import FilesystemProvider

from .fs_from_dav_provider import DAVProvider2FS

# Create the test playground if needed
dav_provider = FilesystemProvider("/tmp")
dav_fs = DAVProvider2FS(dav_provider)
dav_fs._reset_path("/_playground_", True)
dav_fs.close()
test_count = 0


class TestDAVProvider2FS(FSTestCases, unittest.TestCase):
    def make_fs(self):
        global test_count
        test_count += 1
        test_name = self.id().split(".")[-1]
        # if test_name in ("test_upload", "test_download"):
        #     pytest.skip("No time to waste...")
        #     return
        if test_name in ("test_appendbytes", "test_appendtext"):
            pytest.xfail("Appending is not supported")
        if test_name in ("test_bin_files", "test_files", "test_open_files"):
            pytest.xfail("Updating is not supported")
        if test_name in ("test_setinfo"):
            pytest.xfail("Modified time is in seconds (int) instead of (float)")
        if test_name in ("test_invalid_chars"):
            pytest.xfail("TODO: get list of invalid characters from the DAV Provider")
        # Return an instance of your FS object here
        dav_provider = FilesystemProvider("/tmp/_playground_")
        dav_fs = DAVProvider2FS(dav_provider)
        test_path = "/%02d_%s" % (test_count, test_name)
        test_fs = dav_fs._reset_path(test_path, True)
        return test_fs

    def destroy_fs(self, test_fs):
        test_fs.close()


# class TestWrapDAVProvider2FS(FSTestCases, unittest.TestCase):
#     def make_fs(self):
#         # Return an instance of your FS object here
#         return WrapDAVProvider2FS()


# class TestDAVProvider2FSOpener(unittest.TestCase):
#     def test_open_dav_provider(self):
#         from fs.opener import open_fs
#
#         dav_fs = open_fs("dav_provider://")
#         self.assertIsInstance(dav_fs, DAVProvider2FS)
