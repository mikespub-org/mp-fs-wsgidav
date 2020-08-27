#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# (c) 2010 Martin Wendt; see CloudDAV http://clouddav.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
"""
WsgiDAV DAV provider that implements a virtual file system based
on Google Cloud Firestore in native mode.

Example using FirestoreDAVProvider() as DAV provider in WsgiDAV:
    >>> from wsgidav.wsgidav_app import WsgiDAVApp
    >>> from .fire.firestore_dav import FirestoreDAVProvider
    >>>
    >>> dav_provider = FirestoreDAVProvider()
    >>> config = {"provider_mapping": {"/": dav_provider}}
    >>> config["simple_dc"] = {"user_mapping": {"*": True}}  # allow anonymous access or use domain controller
    >>>
    >>> app = WsgiDAVApp(config)
    >>> # run_wsgi_app(app)

"""
from __future__ import absolute_import

import hashlib
import logging
import mimetypes
from builtins import str

from future import standard_library
from wsgidav import util
from wsgidav.dav_error import HTTP_FORBIDDEN, DAVError
from wsgidav.dav_provider import DAVProvider, _DAVResource

from .model import Dir, File, Path

# from . import sessions
from . import fs as fire_fs

standard_library.install_aliases()


__docformat__ = "reStructuredText en"

# _logger = util.get_module_logger(__name__)

# ===============================================================================
# FirestoreDAVResource classes
# ===============================================================================
class FirestoreDAVResource(_DAVResource):
    """."""

    _supported_props = [
        "{firestore:}key",
    ]
    _namespaces = ["firestore:"]

    def __init__(self, path, environ):
        if isinstance(path, Path):
            self.path_entity = path
            path = self.path_entity.path
        else:
            self.path_entity = Path.retrieve(path)
        if not self.path_entity:
            raise ValueError("Path not found: %r" % path)
        is_collection = type(self.path_entity) is Dir
        logging.debug("%s(%r): %r" % (type(self).__name__, path, is_collection))
        super(FirestoreDAVResource, self).__init__(path, is_collection, environ)
        # check access based on user roles in environ
        self._get_user_roles(environ)
        self.statresults = fire_fs.stat(self.path_entity)
        self._etag = None
        self._content_type = None
        # TODO: fill self._data with some properties from self.path_entity?
        self._data = {}

    def _get_user_roles(self, environ):
        self._roles = []
        if environ is None or not environ.get("wsgidav.auth.roles"):
            self._roles.append(self.provider.anon_role)
            logging.debug("Roles: %s" % self._roles)
            return
        # set by Firebase DC based on wsgidav config, custom claims or user database
        if environ.get("wsgidav.auth.roles"):
            for role in environ.get("wsgidav.auth.roles"):
                if role in self.provider.known_roles and role not in self._roles:
                    self._roles.append(role)
        if len(self._roles) < 1:
            if not environ.get("wsgidav.auth.user_name"):
                self._roles.append(self.provider.anon_role)
            else:
                self._roles.append(self.provider.user_role)
        logging.debug("Roles: %s" % self._roles)

    def _check_write_access(self):
        """Raise HTTP_FORBIDDEN, if resource is unwritable."""
        if self.provider.is_readonly():
            raise DAVError(HTTP_FORBIDDEN)
        for role in ("admin", "editor"):
            if role in self._roles:
                return
        raise DAVError(HTTP_FORBIDDEN)

    def _check_read_access(self):
        """Raise HTTP_FORBIDDEN, if resource is unreadable."""
        for role in ("admin", "editor", "reader"):
            if role in self._roles:
                return
        raise DAVError(HTTP_FORBIDDEN)

    def get_content_length(self):
        if self.is_collection:
            return None
        return self.statresults.st_size

    def get_content_type(self):
        if self.is_collection:
            # TODO: should be None?
            return "httpd/unix-directory"
        if self._content_type:
            return self._content_type
        (mimetype, _mimeencoding) = mimetypes.guess_type(self.path, strict=False)
        logging.debug("Guess type of %s is %s", repr(self.path), mimetype)
        if mimetype == "" or mimetype is None:
            mimetype = "application/octet-stream"
        # mimetype = 'application/octet-stream'
        self._content_type = mimetype
        return mimetype

    def get_creation_date(self):
        return self.statresults.st_ctime

    def get_display_name(self):
        return self.name

    def get_etag(self):
        if self._etag:
            return self._etag
        if self.is_collection:
            self._etag = '"' + hashlib.md5(self.path.encode("utf-8")).hexdigest() + '"'
        else:
            self._etag = (
                hashlib.md5(self.path.encode("utf-8")).hexdigest()
                + "-"
                + str(self.statresults.st_mtime)
                + "-"
                + str(self.statresults.st_size)
            )
        return self._etag

    def get_last_modified(self):
        return self.statresults.st_mtime

    def support_ranges(self):
        return True

    def get_member_names(self):
        """Return list of (direct) collection member names (_DAVResource or derived).

        See _DAVResource.get_member_list()
        """
        # self._check_browse_access()
        return fire_fs.listdir(self.path_entity)

    def get_member(self, name):
        """Return list of (direct) collection members (_DAVResource or derived).

        See _DAVResource.get_member_list()
        """
        # logging.debug('%r + %r' % (self.path, name))
        # self._check_browse_access()
        # res = FirestoreDAVResource(util.join_uri(self.path, name), self.environ)
        res = type(self)(util.join_uri(self.path, name), self.environ)
        return res

    def get_member_list(self):
        """Return a list of direct members (_DAVResource or derived objects).
        """
        if not self.is_collection:
            raise NotImplementedError
        memberList = []
        for entity in fire_fs.scandir(self.path_entity):
            # member = FirestoreDAVResource(entity, self.environ)
            member = type(self)(entity, self.environ)
            assert member is not None
            memberList.append(member)
        return memberList

    # def handle_delete(self):
    #     raise DAVError(HTTP_FORBIDDEN)
    # def handle_move(self, dest_path):
    #     raise DAVError(HTTP_FORBIDDEN)
    # def handle_copy(self, dest_path, depth_infinity):
    #     raise DAVError(HTTP_FORBIDDEN)

    # --- Read / write ---------------------------------------------------------

    def create_empty_resource(self, name):
        """Create an empty (length-0) resource.

        See _DAVResource.create_empty_resource()
        """
        assert self.is_collection
        assert not "/" in name
        self._check_write_access()
        path = util.join_uri(self.path, name)
        f = fire_fs.btopen(path, "wb")
        # FIXME: should be length-0
        # f.write(".")
        f.close()
        return self.provider.get_resource_inst(path, self.environ)

    def create_collection(self, name):
        """Create a new collection as member of self.

        See _DAVResource.create_collection()
        """
        assert self.is_collection
        self._check_write_access()
        path = util.join_uri(self.path, name)
        fire_fs.mkdir(path)

    def get_content(self):
        """Open content as a stream for reading.

        See _DAVResource.get_content()
        """
        assert not self.is_collection
        self._check_read_access()
        # return fire_fs.btopen(self.path, "rb")
        return fire_fs.btopen(self.path_entity, "rb")

    def begin_write(self, content_type=None):
        """Open content as a stream for writing.

        See _DAVResource.begin_write()
        """
        assert not self.is_collection
        self._check_write_access()
        # return fire_fs.btopen(self.path, "wb")
        return fire_fs.btopen(self.path_entity, "wb")

    def support_recursive_delete(self):
        """Return True, if delete() may be called on non-empty collections
        (see comments there).

        This method MUST be implemented for collections (not called on
        non-collections).
        """
        # TODO: should support recursive operations
        return False

    def delete(self):
        """Remove this resource or collection (recursive).

        See _DAVResource.delete()
        """
        self._check_write_access()
        if self.is_collection:
            # fire_fs.rmtree(self.path)
            fire_fs.rmtree(self.path_entity)
        else:
            # fire_fs.unlink(self.path)
            fire_fs.unlink(self.path_entity)
        self.remove_all_properties(True)
        self.remove_all_locks(True)

    def copy_move_single(self, dest_path, is_move):
        """See _DAVResource.copy_move_single() """
        assert not util.is_equal_or_child_uri(self.path, dest_path)
        self._check_write_access()
        if self.is_collection:
            # Create destination collection, if not exists
            if not fire_fs.exists(dest_path):
                fire_fs.mkdir(dest_path)
        else:
            # Copy file (overwrite, if exists)
            # fire_fs.copyfile(self.path, dest_path)
            fire_fs.copyfile(self.path_entity, dest_path)
        # shutil.copy2(self._file_path, fpDest)
        # (Live properties are copied by copy2 or copystat)
        # Copy dead properties
        prop_man = self.provider.prop_manager
        if prop_man:
            dest_res = self.provider.get_resource_inst(dest_path, self.environ)
            if is_move:
                prop_man.move_properties(
                    self.get_ref_url(), dest_res.get_ref_url(), with_children=False
                )
            else:
                prop_man.copy_properties(self.get_ref_url(), dest_res.get_ref_url())

    def support_recursive_move(self, dest_path):
        """Return True, if move_recursive() is available (see comments there)."""
        # TODO: should support recursive operations
        return False

    # def move_recursive(self, dest_path):
    #     """See _DAVResource.move_recursive() """
    #     # FIXME
    #     raise NotImplementedError()
    #     fpDest = self.provider._locToFilePath(dest_path)
    #     assert not util.is_equal_or_child_uri(self.path, dest_path)
    #     assert not os.path.exists(fpDest)
    #     _logger.debug("moveRecursive(%s, %s)" % (self._file_path, fpDest))
    #     shutil.move(self._file_path, fpDest)
    #     # (Live properties are copied by copy2 or copystat)
    #     # Move dead properties
    #     if self.provider.prop_manager:
    #         dest_res = self.provider.get_resource_inst(dest_path, self.environ)
    #         self.provider.prop_manager.move_properties(self.get_ref_url(), dest_res.get_ref_url(),
    #                                                    with_children=True)

    def get_property_names(self, is_allprop):
        """Return list of supported property names in Clark Notation.

        See _DAVResource.get_property_names()
        """
        # Let base class implementation add supported live and dead properties
        propNameList = super(FirestoreDAVResource, self).get_property_names(is_allprop)
        # Add custom live properties (report on 'allprop' and 'propnames')
        # propNameList.extend(type(self)._supported_props)
        return propNameList

    def get_property_value(self, name):
        """Return the value of a property.

        See _DAVResource.get_property_value()
        """
        # Supported custom live properties
        if name in self._supported_props:
            # Example: '{DAV:}foo'  -> ('DAV:', 'foo')
            ns, localname = util.split_namespace(name)
            if ns in self._namespaces and localname in self._data:
                return self._data[localname]
        # Let base class implementation report live and dead properties
        return super(FirestoreDAVResource, self).get_property_value(name)

    # def set_property_value(self, name, value, dry_run=False):
    #     """Set or remove property value.
    #
    #     See _DAVResource.set_property_value()
    #     """
    #     if value is None:
    #         # We can never remove properties
    #         raise DAVError(HTTP_FORBIDDEN)
    #     if name == "{firestore:}tags":
    #         # value is of type etree.Element
    #         self._data["tags"] = value.text.split(",")
    #     elif name == "{firestore:}description":
    #         # value is of type etree.Element
    #         self._data["description"] = value.text
    #     elif name in type(self)._supported_props:
    #         # Supported property, but read-only
    #         raise DAVError(HTTP_FORBIDDEN,
    #                        errcondition=PRECONDITION_CODE_ProtectedProperty)
    #     else:
    #         # Unsupported property
    #         raise DAVError(HTTP_FORBIDDEN)
    #     # Write OK
    #     return

    # called by wsgidav.request_server for do_GET and do_HEAD methods
    # def finalize_headers(self, environ, response_headers):
    #     sessions.finalize_headers(environ, response_headers)
    #     return super(FirestoreDAVResource, self).finalize_headers(environ, response_headers)


# ===============================================================================
# FirestoreDAVProvider
# ===============================================================================
class FirestoreDAVProvider(DAVProvider):
    """
    WsgiDAV provider that implements a virtual filesystem based on Googles Big Table.
    Update: actually, it used the old App Engine Firestore, which has now been upgraded
    to Cloud Firestore in Firestore mode. Firestore in Native mode is not supported yet.
    """

    known_roles = ("admin", "editor", "reader", "browser", "none")
    resource_class = FirestoreDAVResource

    def __init__(self, *args, **kwargs):
        super(FirestoreDAVProvider, self).__init__()
        # TODO: make provider configurable
        self._readonly = kwargs.pop("readonly", False)
        # TODO: support firestore in native mode
        self._backend = kwargs.pop("backend", "firestore")
        # default role for authenticated users, unless specified in DC config or /auth/users
        self.user_role = kwargs.pop("user_role", "reader")
        # default role for anonymous visitors, unless specified in DC config
        self.anon_role = kwargs.pop("anon_role", "browser")
        # return (no) desktop.ini for Microsoft-WebDAV-MiniRedir
        self.desktop_ini = kwargs.pop("desktop_ini", False)
        fire_fs.initfs()

    def is_readonly(self):
        return self._readonly

    def get_resource_inst(self, path, environ):
        # return (no) desktop.ini for Microsoft-WebDAV-MiniRedir
        if not self.desktop_ini and path.endswith("/desktop.ini"):
            return
        self._count_get_resource_inst += 1
        try:
            # res = FirestoreDAVResource(path, environ)
            res = self.resource_class(path, environ)
        except Exception as e:
            logging.debug(e)
            logging.exception("get_resource_inst(%r) failed" % path)
            res = None
        logging.debug("get_resource_inst(%r): %s" % (path, res))
        return res

    def __repr__(self):
        return "%s()" % (self.__class__.__name__)

    # called by wsgidav.request_server to handle all do_* methods
    # def custom_request_handler(self, environ, start_response, default_handler):
    #    #return default_handler(environ, start_response)
    #    logging.debug('Custom: %r %r' % (start_response, default_handler))
    #    return super(FirestoreDAVProvider, self).custom_request_handler(environ, start_response, default_handler)


def create_app(config=None):
    # from .fire.firestore_dav import FirestoreDAVProvider
    from wsgidav.wsgidav_app import WsgiDAVApp

    dav_provider = FirestoreDAVProvider()

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
        except KeyboardInterrupt as e:
            print("Goodbye...")


def main():
    # Create the WsgiDAV app with the Firestore DAV provider
    app = create_app()

    # Run the WsgiDAV app with your preferred WSGI server
    run_wsgi_app(app)


if __name__ == "__main__":
    main()
