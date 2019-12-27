# -*- coding: iso-8859-1 -*-
# (c) 2010 Martin Wendt; see CloudDAV http://clouddav.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
"""
Implementation of a WsgiDAV provider that implements a virtual file system based
on Google's Big Table.
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

from btfs.model import Dir, File, Path

from . import bt_fs, sessions

standard_library.install_aliases()


__docformat__ = "reStructuredText en"

# _logger = util.get_module_logger(__name__)
BUFFER_SIZE = 8192

# ===============================================================================
# BTFSResource classes
# ===============================================================================
class BTFSResource(_DAVResource):
    """."""

    _supportedProps = [
        "{btfs:}key",
    ]

    def __init__(self, path, environ):
        self.pathEntity = Path.retrieve(path)
        if not self.pathEntity:
            raise ValueError("Path not found: %r" % path)
        is_collection = type(self.pathEntity) is Dir
        logging.debug("BTFSResource(%r): %r" % (path, is_collection))
        super(BTFSResource, self).__init__(path, is_collection, environ)
        # check access based on user roles in environ
        self._get_user_roles(environ)
        self.statresults = bt_fs.stat(self.pathEntity)
        self._etag = None
        self._content_type = None

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

    def getContentLength(self):
        if self.is_collection:
            return None
        return self.statresults.st_size

    get_content_length = getContentLength

    def getContentType(self):
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

    get_content_type = getContentType

    def getCreationDate(self):
        return self.statresults.st_ctime

    get_creation_date = getCreationDate

    def getDisplayName(self):
        return self.name

    get_display_name = getDisplayName

    def getEtag(self):
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

    get_etag = getEtag

    def getLastModified(self):
        return self.statresults.st_mtime

    get_last_modified = getLastModified

    def supportRanges(self):
        return True

    support_ranges = supportRanges

    def getMemberNames(self):
        """Return list of (direct) collection member names (_DAVResource or derived).

        See _DAVResource.getMemberList()
        """
        # self._check_browse_access()
        return bt_fs.listdir(self.pathEntity)

    get_member_names = getMemberNames

    def getMember(self, name):
        """Return list of (direct) collection members (_DAVResource or derived).

        See _DAVResource.getMemberList()
        """
        # logging.debug('%r + %r' % (self.path, name))
        # self._check_browse_access()
        res = BTFSResource(util.join_uri(self.path, name), self.environ)
        return res

    get_member = getMember

    # def handleDelete(self):
    #     raise DAVError(HTTP_FORBIDDEN)
    # def handleMove(self, destPath):
    #     raise DAVError(HTTP_FORBIDDEN)
    # def handleCopy(self, destPath, depthInfinity):
    #     raise DAVError(HTTP_FORBIDDEN)

    # --- Read / write ---------------------------------------------------------

    def createEmptyResource(self, name):
        """Create an empty (length-0) resource.

        See _DAVResource.createEmptyResource()
        """
        assert self.is_collection
        assert not "/" in name
        self._check_write_access()
        path = util.join_uri(self.path, name)
        f = bt_fs.btopen(path, "wb")
        # FIXME: should be length-0
        # f.write(".")
        f.close()
        return self.provider.getResourceInst(path, self.environ)

    create_empty_resource = createEmptyResource

    def createCollection(self, name):
        """Create a new collection as member of self.

        See _DAVResource.createCollection()
        """
        assert self.is_collection
        self._check_write_access()
        path = util.join_uri(self.path, name)
        bt_fs.mkdir(path)

    create_collection = createCollection

    def getContent(self):
        """Open content as a stream for reading.

        See _DAVResource.getContent()
        """
        assert not self.is_collection
        self._check_read_access()
        # return bt_fs.btopen(self.path, "rb")
        return bt_fs.btopen(self.pathEntity, "rb")

    get_content = getContent

    def beginWrite(self, content_type=None):
        """Open content as a stream for writing.

        See _DAVResource.beginWrite()
        """
        assert not self.is_collection
        self._check_write_access()
        # return bt_fs.btopen(self.path, "wb")
        return bt_fs.btopen(self.pathEntity, "wb")

    begin_write = beginWrite

    def supportRecursiveDelete(self):
        """Return True, if delete() may be called on non-empty collections
        (see comments there).

        This method MUST be implemented for collections (not called on
        non-collections).
        """
        # TODO: should support recursive operations
        return False

    support_recursive_delete = supportRecursiveDelete

    def delete(self):
        """Remove this resource or collection (recursive).

        See _DAVResource.delete()
        """
        self._check_write_access()
        if self.is_collection:
            # bt_fs.rmtree(self.path)
            bt_fs.rmtree(self.pathEntity)
        else:
            # bt_fs.unlink(self.path)
            bt_fs.unlink(self.pathEntity)
        self.removeAllProperties(True)
        self.removeAllLocks(True)

    def copyMoveSingle(self, dest_path, is_move):
        """See _DAVResource.copyMoveSingle() """
        assert not util.is_equal_or_child_uri(self.path, dest_path)
        self._check_write_access()
        if self.is_collection:
            # Create destination collection, if not exists
            if not bt_fs.exists(dest_path):
                bt_fs.mkdir(dest_path)
        else:
            # Copy file (overwrite, if exists)
            # bt_fs.copyfile(self.path, dest_path)
            bt_fs.copyfile(self.pathEntity, dest_path)
        # shutil.copy2(self._filePath, fpDest)
        # (Live properties are copied by copy2 or copystat)
        # Copy dead properties
        propMan = self.provider.prop_manager
        if propMan:
            destRes = self.provider.get_resource_inst(dest_path, self.environ)
            if is_move:
                propMan.move_properties(
                    self.get_ref_url(), destRes.get_ref_url(), with_children=False
                )
            else:
                propMan.copy_properties(self.get_ref_url(), destRes.get_ref_url())

    copy_move_single = copyMoveSingle

    def supportRecursiveMove(self, dest_path):
        """Return True, if moveRecursive() is available (see comments there)."""
        # TODO: should support recursive operations
        return False

    support_recursive_move = supportRecursiveMove

    # def moveRecursive(self, destPath):
    #     """See _DAVResource.moveRecursive() """
    #     # FIXME
    #     raise NotImplementedError()
    #     fpDest = self.provider._locToFilePath(destPath)
    #     assert not util.is_equal_or_child_uri(self.path, destPath)
    #     assert not os.path.exists(fpDest)
    #     _logger.debug("moveRecursive(%s, %s)" % (self._filePath, fpDest))
    #     shutil.move(self._filePath, fpDest)
    #     # (Live properties are copied by copy2 or copystat)
    #     # Move dead properties
    #     if self.provider.prop_manager:
    #         destRes = self.provider.get_resource_inst(destPath, self.environ)
    #         self.provider.prop_manager.move_properties(self.get_ref_url(), destRes.get_ref_url(),
    #                                                    with_children=True)

    def getPropertyNames(self, is_allprop):
        """Return list of supported property names in Clark Notation.

        See _DAVResource.getPropertyNames()
        """
        # Let base class implementation add supported live and dead properties
        propNameList = super(BTFSResource, self).get_property_names(is_allprop)
        # Add custom live properties (report on 'allprop' and 'propnames')
        # propNameList.extend(BTFSResource._supportedProps)
        return propNameList

    get_property_names = getPropertyNames

    def getPropertyValue(self, name):
        """Return the value of a property.

        See _DAVResource.getPropertyValue()
        """
        # Supported custom live properties
        if name == "{btfs:}key":
            return self._data["key"]
        # Let base class implementation report live and dead properties
        return super(BTFSResource, self).get_property_value(name)

    get_property_value = getPropertyValue

    # def setPropertyValue(self, name, value, dry_run=False):
    #     """Set or remove property value.
    #
    #     See _DAVResource.setPropertyValue()
    #     """
    #     if value is None:
    #         # We can never remove properties
    #         raise DAVError(HTTP_FORBIDDEN)
    ##     if name == "{btfs:}key":
    ##         # value is of type etree.Element
    ##         self._data["tags"] = value.text.split(",")
    #     elif name == "{virtres:}description":
    #         # value is of type etree.Element
    #         self._data["description"] = value.text
    #     elif name in VirtualResource._supportedProps:
    #         # Supported property, but read-only
    #         raise DAVError(HTTP_FORBIDDEN,
    #                        errcondition=PRECONDITION_CODE_ProtectedProperty)
    #     else:
    #         # Unsupported property
    #         raise DAVError(HTTP_FORBIDDEN)
    #     # Write OK
    #     return

    # called by wsgidav.request_server for do_GET and do_HEAD methods
    def finalize_headers(self, environ, response_headers):
        sessions.finalize_headers(environ, response_headers)
        return super(BTFSResource, self).finalize_headers(environ, response_headers)


# ===============================================================================
# BTFSResourceProvider
# ===============================================================================


class BTFSResourceProvider(DAVProvider):
    """
    WsgiDAV provider that implements a virtual filesystem based on Googles Big Table.
    Update: actually, it used the old App Engine Datastore, which has now been upgraded
    to Cloud Firestore in Datastore mode. Firestore in Native mode is not supported yet.
    """

    known_roles = ("admin", "editor", "reader", "browser", "none")

    def __init__(self, *args, **kwargs):
        super(BTFSResourceProvider, self).__init__()
        # TODO: make provider configurable
        self._readonly = kwargs.pop("readonly", False)
        # TODO: support firestore in native mode
        self._backend = kwargs.pop("backend", "datastore")
        # default role for authenticated users, unless specified in DC config or /auth/users
        self.user_role = kwargs.pop("user_role", "reader")
        # default role for anonymous visitors, unless specified in DC config
        self.anon_role = kwargs.pop("anon_role", "browser")
        # return (no) desktop.ini for Microsoft-WebDAV-MiniRedir
        self.desktop_ini = kwargs.pop("desktop_ini", False)
        bt_fs.initfs()

    def is_readonly(self):
        return self._readonly

    def getResourceInst(self, path, environ):
        # return (no) desktop.ini for Microsoft-WebDAV-MiniRedir
        if not self.desktop_ini and path.endswith("/desktop.ini"):
            return
        self._count_get_resource_inst += 1
        try:
            res = BTFSResource(path, environ)
        except Exception as e:
            logging.debug(e)
            logging.exception("getResourceInst(%r) failed" % path)
            res = None
        logging.debug("getResourceInst(%r): %s" % (path, res))
        return res

    get_resource_inst = getResourceInst

    # called by wsgidav.request_server to handle all do_* methods
    # def custom_request_handler(self, environ, start_response, default_handler):
    #    #return default_handler(environ, start_response)
    #    logging.debug('Custom: %r %r' % (start_response, default_handler))
    #    return super(BTFSResourceProvider, self).custom_request_handler(environ, start_response, default_handler)
