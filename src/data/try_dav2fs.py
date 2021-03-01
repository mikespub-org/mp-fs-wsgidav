#!/usr/bin/env python3
#
# Use the Datastore DAV provider for DAVProvider2FS()
#


def main(path=None, file=None, *args):
    from data.datastore_dav import DatastoreDAVProvider
    from mapper.fs_from_dav_provider import DAVProvider2FS

    dav_provider = DatastoreDAVProvider()
    dav_fs = DAVProvider2FS(dav_provider)
    # result = dav_fs.tree()
    if path is None:
        path = "/"
    path_fs = dav_fs.opendir(path)
    if file is None:
        result = path_fs.listdir("/")
    else:
        result = path_fs.getinfo(file, namespaces=["details", "properties"]).raw
    dav_fs.close()
    return result


if __name__ == "__main__":
    import sys
    from pprint import pprint

    if len(sys.argv) > 1:
        result = main(*sys.argv[1:])
    else:
        print("%s [<path> [<file>]]" % "python3 -m data.try_dav2fs")
        result = main()

    pprint(result)
