#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# (c) 2010 Martin Wendt; see CloudDAV http://clouddav.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
"""
Implementation of a WsgiDAV provider that implements a virtual file system based
on Google Cloud Firestore in Datastore mode.
"""
from data.datastore_dav import DatastoreDAVProvider, DatastoreDAVResource

from . import sessions


__docformat__ = "reStructuredText en"

# _logger = util.get_module_logger(__name__)

# ===============================================================================
# BTFSResource classes
# ===============================================================================
class BTFSResource(DatastoreDAVResource):
    """Expand Datastore DAV Resource with own methods/properties"""

    _supportedProps = [
        "{btfs:}key",
    ]
    _namespaces = ["btfs:", "datastore:"]

    # def set_property_value(self, name, value, dry_run=False):
    #     """Set or remove property value.
    #
    #     See _DAVResource.set_property_value()
    #     """
    #     if value is None:
    #         # We can never remove properties
    #         raise DAVError(HTTP_FORBIDDEN)
    #     if name == "{btfs:}tags":
    #         # value is of type etree.Element
    #         self._data["tags"] = value.text.split(",")
    #     elif name == "{btfs:}description":
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
    def finalize_headers(self, environ, response_headers):
        sessions.finalize_headers(environ, response_headers)
        return super(BTFSResource, self).finalize_headers(environ, response_headers)


# ===============================================================================
# BTFSResourceProvider
# ===============================================================================
class BTFSResourceProvider(DatastoreDAVProvider):
    """Expand Datastore DAV Provider with own methods/properties, starting with own resource_class"""
    resource_class = BTFSResource

    # called by wsgidav.request_server to handle all do_* methods
    # def custom_request_handler(self, environ, start_response, default_handler):
    #    #return default_handler(environ, start_response)
    #    logging.debug('Custom: %r %r' % (start_response, default_handler))
    #    return super(BTFSResourceProvider, self).custom_request_handler(environ, start_response, default_handler)
