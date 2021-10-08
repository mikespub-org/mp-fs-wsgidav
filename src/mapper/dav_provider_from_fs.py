#!/usr/bin/env python3
#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# (c) 2009-2019 Martin Wendt and contributors; see WsgiDAV https://github.com/mar10/wsgidav
# Original PyFileServer (c) 2005 Ho Chun Wei.
# Licensed under the MIT license: https://opensource.org/licenses/mit-license.php
#
"""Basic support of PyFilesystem2 filesystems as DAV provider for WsgiDAV

Example using the FS2DAVProvider() in WsgiDAV:
    >>> from wsgidav.wsgidav_app import WsgiDAVApp
    >>> from .dav_provider_from_fs import FS2DAVProvider
    >>> from fs.osfs import OSFS
    >>>
    >>> source_fs = OSFS("/tmp")
    >>> dav_provider = FS2DAVProvider(source_fs)
    >>> config = {"provider_mapping": {"/": dav_provider}}
    >>> config["simple_dc"] = {"user_mapping": {"*": True}}  # allow anonymous access or use domain controller
    >>>
    >>> app = WsgiDAVApp(config)
    >>> # run_wsgi_app(app)

For more information on WsgiDAV, see https://wsgidav.readthedocs.io/
For more information on PyFilesystem2, see https://docs.pyfilesystem.org/
"""

import fs.base
import fs.path
import fs.time

# logging.basicConfig(format='%(levelname)s:%(module)s.%(funcName)s:%(message)s', level=logging.DEBUG)
from wsgidav import util
from wsgidav.dav_error import HTTP_FORBIDDEN, DAVError
from wsgidav.dav_provider import DAVCollection, DAVNonCollection, DAVProvider

_logger = util.get_module_logger(__name__)
# _logger = logging.getLogger("wsgidav")
# _logger.propagate = True
# _logger.setLevel(logging.DEBUG)


# ========================================================================
# FS2FileResource
# ========================================================================
class FS2FileResource(DAVNonCollection):
    """Represents a single existing DAV resource instance.

    See also _DAVResource, DAVNonCollection, and FS2DAVProvider.
    """

    def __init__(self, path, environ, info):
        super().__init__(path, environ)
        self.info = info
        if not self.info.created and self.info.metadata_changed:
            self.info.raw["details"]["created"] = self.info.raw["details"][
                "metadata_changed"
            ]
        self.name = info.name
        self._content_type = None
        self._etag = None

    # Getter methods for standard live properties
    def get_content_length(self):
        return self.info.size

    def get_content_type(self):
        if self._content_type:
            return self._content_type
        self._content_type = util.guess_mime_type(self.path)
        return self._content_type

    def get_creation_date(self):
        return fs.time.datetime_to_epoch(self.info.created)

    def get_display_name(self):
        return self.name

    def get_etag(self):
        if self._etag:
            return self._etag
        self._etag = util.get_etag(self.path)
        return self._etag

    def get_last_modified(self):
        return fs.time.datetime_to_epoch(self.info.modified)

    def support_etag(self):
        return True

    def support_ranges(self):
        return True

    def get_content(self):
        """Open content as a stream for reading.

        See DAVResource.get_content()
        """
        assert not self.is_collection
        return self.provider.source_fs.openbin(self.path, "rb")

    def begin_write(self, content_type=None):
        """Open content as a stream for writing.

        See DAVResource.begin_write()
        """
        assert not self.is_collection
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        return self.provider.source_fs.openbin(self.path, "wb")

    def delete(self):
        """Remove this resource or collection (recursive).

        See DAVResource.delete()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        self.provider.source_fs.remove(self.path)
        self.remove_all_properties(True)
        self.remove_all_locks(True)

    def copy_move_single(self, dest_path, is_move):
        """See DAVResource.copy_move_single()"""
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        assert not util.is_equal_or_child_uri(self.path, dest_path)
        # Copy file (overwrite, if exists)
        self.provider.source_fs.copy(self.path, dest_path, overwrite=True)
        # (Live properties are copied by copy2 or copystat)
        # Copy dead properties
        propMan = self.provider.prop_manager
        if propMan:
            destRes = self.provider.get_resource_inst(dest_path, self.environ)
            if is_move:
                propMan.move_properties(
                    self.get_ref_url(),
                    destRes.get_ref_url(),
                    with_children=False,
                    environ=self.environ,
                )
            else:
                propMan.copy_properties(
                    self.get_ref_url(), destRes.get_ref_url(), self.environ
                )
        # TODO: shouldn't we delete the resource here after the move?
        if is_move:
            pass

    def support_recursive_move(self, dest_path):
        """Return True, if move_recursive() is available (see comments there)."""
        return True

    def move_recursive(self, dest_path):
        """See DAVResource.move_recursive()"""
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        assert not util.is_equal_or_child_uri(self.path, dest_path)
        _logger.debug(f"move_recursive({self.path}, {dest_path})")
        self.provider.source_fs.move(self.path, dest_path, overwrite=False)
        # (Live properties are copied by copy2 or copystat)
        # Move dead properties
        if self.provider.prop_manager:
            destRes = self.provider.get_resource_inst(dest_path, self.environ)
            self.provider.prop_manager.move_properties(
                self.get_ref_url(),
                destRes.get_ref_url(),
                with_children=True,
                environ=self.environ,
            )

    def set_last_modified(self, dest_path, time_stamp, dry_run):
        """Set last modified time for destPath to timeStamp on epoch-format"""
        # Translate time from RFC 1123 to seconds since epoch format
        if not self.info.is_writeable("details", "modified"):
            raise NotImplementedError("Last modified time is not writable")
        secs = util.parse_time_string(time_stamp)
        details_info = {"details": {"modified": secs}}
        if not dry_run:
            self.provider.source_fs.setinfo(dest_path, details_info)
        return True


# ========================================================================
# FS2FolderResource
# ========================================================================
class FS2FolderResource(DAVCollection):
    """Represents a single existing file system folder DAV resource.

    See also _DAVResource, DAVCollection, and FS2DAVProvider.
    """

    def __init__(self, path, environ, info):
        super().__init__(path, environ)
        self.info = info
        if not self.info.created and self.info.metadata_changed:
            self.info.raw["details"]["created"] = self.info.raw["details"][
                "metadata_changed"
            ]
        self.name = info.name

    # Getter methods for standard live properties
    def get_content_length(self):
        return None

    def get_content_type(self):
        return None

    def get_creation_date(self):
        return fs.time.datetime_to_epoch(self.info.created)

    def get_display_name(self):
        return self.name

    def get_directory_info(self):
        return None

    def get_etag(self):
        return None

    def get_last_modified(self):
        return fs.time.datetime_to_epoch(self.info.modified)

    def get_member_names(self):
        """Return list of direct collection member names (utf-8 encoded).

        See DAVCollection.get_member_names()
        """
        nameList = []
        for name in self.provider.source_fs.listdir(self.path):
            nameList.append(name)
        return nameList

    def get_member(self, name):
        """Return direct collection member (DAVResource or derived).

        See DAVCollection.get_member()
        """
        path = fs.path.join(self.path, name)
        info = self.provider.get_details(path)
        if not info:
            _logger.debug(f"Skipping non-file {path}")
            return
        if info.is_dir:
            res = FS2FolderResource(path, self.environ, info)
        else:
            res = FS2FileResource(path, self.environ, info)
        return res

    def get_member_list(self):
        """Return a list of direct members (_DAVResource or derived objects).

        This default implementation calls self.get_member_names() and
        self.get_member() for each of them.
        A provider COULD overwrite this for performance reasons.
        """
        memberList = []
        for info in self.provider.source_fs.scandir(self.path, namespaces=["details"]):
            path = fs.path.join(self.path, info.name)
            if info.is_dir:
                res = FS2FolderResource(path, self.environ, info)
            else:
                res = FS2FileResource(path, self.environ, info)
            memberList.append(res)
        return memberList

    # --- Read / write -------------------------------------------------------

    def create_empty_resource(self, name):
        """Create an empty (length-0) resource.

        See DAVResource.create_empty_resource()
        """
        assert "/" not in name
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        path = fs.path.join(self.path, name)
        self.provider.source_fs.create(path)
        return self.provider.get_resource_inst(path, self.environ)

    def create_collection(self, name):
        """Create a new collection as member of self.

        See DAVResource.create_collection()
        """
        assert "/" not in name
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        path = fs.path.join(self.path, name)
        self.provider.source_fs.makedir(path)

    def support_recursive_delete(self):
        """Return True, if delete() may be called on non-empty collections
        (see comments there).

        This default implementation returns False.
        """
        return False
        # return True

    def delete(self):
        """Remove this resource or collection (recursive).

        See DAVResource.delete()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        self.provider.source_fs.removedir(self.path)
        # self.provider.source_fs.removetree(self.path)
        self.remove_all_properties(True)
        self.remove_all_locks(True)

    def copy_move_single(self, dest_path, is_move):
        """See DAVResource.copy_move_single()"""
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        assert not util.is_equal_or_child_uri(self.path, dest_path)
        # Create destination collection, if not exists
        self.provider.source_fs.makedir(dest_path, recreate=True)
        try:
            details_info = self.info.raw
            del details_info["basic"]
            self.provider.source_fs.setinfo(dest_path, details_info)
        except Exception:
            _logger.exception(f"Could not copy folder stats: {self.path}")
        # (Live properties are copied by copy2 or copystat)
        # Copy dead properties
        propMan = self.provider.prop_manager
        if propMan:
            destRes = self.provider.get_resource_inst(dest_path, self.environ)
            if is_move:
                propMan.move_properties(
                    self.get_ref_url(),
                    destRes.get_ref_url(),
                    with_children=False,
                    environ=self.environ,
                )
            else:
                propMan.copy_properties(
                    self.get_ref_url(), destRes.get_ref_url(), self.environ
                )
        # TODO: shouldn't we delete the resource here after the move?
        if is_move:
            pass

    def support_recursive_move(self, dest_path):
        """Return True, if move_recursive() is available (see comments there)."""
        return True

    def move_recursive(self, dest_path):
        """See DAVResource.move_recursive()"""
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        assert not util.is_equal_or_child_uri(self.path, dest_path)
        _logger.debug(f"move_recursive({self.path}, {dest_path})")
        self.provider.source_fs.movedir(self.path, dest_path, create=True)
        # (Live properties are copied by copy2 or copystat)
        # Move dead properties
        if self.provider.prop_manager:
            destRes = self.provider.get_resource_inst(dest_path, self.environ)
            self.provider.prop_manager.move_properties(
                self.get_ref_url(),
                destRes.get_ref_url(),
                with_children=True,
                environ=self.environ,
            )

    def set_last_modified(self, dest_path, time_stamp, dry_run):
        """Set last modified time for destPath to timeStamp on epoch-format"""
        # Translate time from RFC 1123 to seconds since epoch format
        if not self.info.is_writeable("details", "modified"):
            raise NotImplementedError("Last modified time is not writable")
        secs = util.parse_time_string(time_stamp)
        details_info = {"details": {"modified": secs}}
        if not dry_run:
            self.provider.source_fs.setinfo(dest_path, details_info)
        return True


# ========================================================================
# FS2DAVProvider
# ========================================================================
class FS2DAVProvider(DAVProvider):
    def __init__(self, source_fs, readonly=False):
        if not source_fs or not isinstance(source_fs, fs.base.FS):
            raise ValueError(f"Invalid source fs: {source_fs}")

        super().__init__()

        self.source_fs = source_fs
        self.readonly = readonly

    def is_readonly(self):
        return self.readonly

    def get_details(self, path):
        return self.source_fs.getinfo(path, namespaces=["details"])

    def get_resource_inst(self, path, environ):
        """Return info dictionary for path.

        See DAVProvider.get_resource_inst()
        """
        self._count_get_resource_inst += 1
        try:
            info = self.get_details(path)
        except Exception as e:
            _logger.debug(f"Error {e} for {path}")
            return None

        if not info:
            return None
        if info.is_dir:
            return FS2FolderResource(path, environ, info)
        return FS2FileResource(path, environ, info)

    def __repr__(self):
        return f"{self.__class__.__name__}({repr(self.source_fs)})"


def create_app(source_fs, config=None):
    # from .dav_provider_from_fs import FS2DAVProvider
    from wsgidav.wsgidav_app import WsgiDAVApp

    dav_provider = FS2DAVProvider(source_fs)

    config = config or {}
    config["provider_mapping"] = {"/": dav_provider}
    # allow anonymous access or use domain controller
    config["simple_dc"] = {"user_mapping": {"*": True}}
    config["verbose"] = 3

    return WsgiDAVApp(config)


def run_wsgi_app(app, port=8080):
    from wsgiref.simple_server import make_server

    with make_server("", port, app) as httpd:
        print("Serving HTTP on port %s..." % port)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Goodbye...")


def main():
    # from fs import open_fs
    from fs.osfs import OSFS

    # Open the PyFilesystem2 filesystem as source
    # source_fs = open_fs("osfs:///tmp")
    source_fs = OSFS("/tmp")

    # Create the WsgiDAV app with the source FS filesystem
    app = create_app(source_fs)

    # Run the WsgiDAV app with your preferred WSGI server
    run_wsgi_app(app)


if __name__ == "__main__":
    main()
