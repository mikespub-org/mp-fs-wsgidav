#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: https://opensource.org/licenses/mit-license.php
#
import json
from .db import get_client, to_dict
from .tree import get_structure
import logging

logging.getLogger().setLevel(logging.DEBUG)


def test_my_fs(my_fs):
    # Try creating a dir and a file
    # my_fs.make_dir("/my_dir")
    # my_fs.make_file("/my_file.txt", b"Hello world")
    # my_fs.make_file("/my_dir/your_file.txt", b"=" * 1024)
    # result = my_fs.get_file_data("/my_dir/your_file.txt")
    # my_fs.clean_file("/my_dir/your_file.txt")
    # my_fs.clean_dir("/my_dir")
    # my_fs.clean_file("/my_file.txt")
    #
    # Verify correct ref_to_path
    # result = my_fs.make_file("/test/dir.9/dir.9.9/file.9.9.1.txt")
    # ref_path = result.reference.path
    # print(ref_path, my_fs.convert_ref_to_path(ref_path))
    # result = my_fs.get_file_ref("/test/dir.9/dir.9.9/file.9.9.1.txt")
    #
    # Create/delete a test filesystem
    # my_fs.make_dir("/test")
    my_fs.make_tree("/test", 0)
    # my_fs.clean_tree("/test", 0)
    # my_fs.make_tree("/test", 0)
    # result = my_fs.count
    # and now do it again
    # my_fs.make_tree("/test", 0)
    #
    # Compare speed of looking up by ref or by doc
    # result = my_fs.list_dir_refs("/test")
    # result = my_fs.list_dir_refs("/test", True)
    # result = my_fs.list_dir_docs("/test")
    # result = my_fs.list_dir_docs("/test", True)
    #
    data = my_fs.get_file_data("/test/dir.7/dir.7.3/file.7.3.6.txt")
    print(len(data))
    #
    my_fs.close()


def main():
    result = None
    client = get_client()
    # client = None
    #
    # my_fs = BaseStructure(client)
    # my_fs = FileStructure(client)
    # my_fs = TestStructure(client)
    # my_fs = TreeStructure(client)
    # my_fs = FlatStructure(client)
    # my_fs = get_structure("test", client)
    #
    # test_my_fs(my_fs)
    #
    for struct in ["test", "tree", "flat", "hash"]:
        my_fs = get_structure(struct, client)
        test_my_fs(my_fs)
    client = None
    return result


if __name__ == "__main__":
    result = main()
    # print(json.dumps(result, indent=2, default=lambda o: repr(o)))
    print("Result: %s" % type(result).__name__)
    print(json.dumps(result, indent=2, default=lambda o: to_dict(o)))
