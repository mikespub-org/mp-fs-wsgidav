#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: https://opensource.org/licenses/mit-license.php
#
import os.path

# from future.utils import with_metaclass
from google.cloud import firestore

# from .cache import NamespacedCache
# from .tree import get_structure

GOOGLE_APPLICATION_CREDENTIALS = None

# cached_doc = NamespacedCache("doc")

_client = None


def get_client(project_id=None, cred_file=GOOGLE_APPLICATION_CREDENTIALS):
    global _client
    if _client is not None:
        return _client
    if cred_file and os.path.isfile(cred_file):
        _client = firestore.Client.from_service_account_json(cred_file)
    else:
        _client = firestore.Client(project_id)
    return _client


def to_dict(ref):
    if not hasattr(ref, "__dict__"):
        return repr(ref)
    result = dict(ref.__dict__)
    result.pop("_client", None)
    return result


def list_root():
    return list(get_client().collections())


def get_doc_ref(path):
    return get_client().document(path)


def get_coll_ref(path):
    return get_client().collection(path)


def close():
    global _client
    if _client is not None:
        # _client.close()
        _client = None
