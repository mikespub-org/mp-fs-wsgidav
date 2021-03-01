#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: https://opensource.org/licenses/mit-license.php
#
import logging
import os.path
import time
import uuid


# Base container for collections
class BaseContainer:
    def __init__(self, path="", parent=None):
        self.path = path
        self.id = os.path.basename(self.path)
        self.parent = parent
        self._init_coll()

    def _init_coll(self):
        self._coll = {}

    def collections(self):
        return self._coll.values()

    def collection(self, name):
        if name not in self._coll:
            logging.debug(f"Adding collection {name} in {self.path}")
            self._coll[name] = BaseCollReference(self, name)
        return self._coll[name]


# Fake client for off-line testing
class BaseClient(BaseContainer):
    def document(self, doc_path):
        if isinstance(doc_path, str):
            doc_path = doc_path.split("/")
        doc_ref = self
        while len(doc_path) > 0:
            coll_name = doc_path.pop(0)
            coll_ref = doc_ref.collection(coll_name)
            doc_name = doc_path.pop(0)
            doc_ref = coll_ref.document(doc_name)
        return doc_ref


# Base document reference
class BaseDocReference(BaseContainer):
    def __init__(self, path, kind="Base", parent=None):
        self.kind = kind
        super().__init__(path, parent)
        self._init_doc()

    def _init_doc(self):
        self.info = {}
        self._kind_map = {
            "Base": BaseDocument,
            "Dir": DirDocument,
            "File": FileDocument,
            "Chunk": ChunkDocument,
        }
        self._doc = self._kind_map[self.kind](self, self.info)

    def _init_coll(self):
        super()._init_coll()
        # if self.kind in ('Dir', 'File'):
        #     self.collection('_')
        # if self.kind == 'Dir':
        #     self.collection('d')
        # if self.kind == 'File':
        #     self.collection('c')

    def get(self, field_paths=None):
        self._doc.update(self.info)
        if len(self.info) > 0:
            self._doc.exists = True
        return self._doc

    def set(self, info):
        # delay setting the info here so that make_tree goes through update
        self.info = info
        self._doc.update_time = time.time()
        # self.tmp = info
        # for key in info:
        #    if isinstance(info[key], int):
        #        self.info[key] = 0
        #    else:
        #        self.info[key] = info[key]

    def update(self, info={}):
        self.info.update(info)
        self._doc.update_time = time.time()
        # self.info = self.tmp
        # self.info.update(info)

    def delete(self):
        if self.parent and self.id not in self.parent:
            logging.error(f"Invalid id {self.id} for parent {self.parent}")
            raise ValueError
        self._doc = None
        self._coll = {}
        del self.parent[self.id]

    def query(self):
        return BaseQuery(self)


# Base collection reference
class BaseCollReference(dict):
    def __init__(self, doc_ref, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = doc_ref
        if name == "_":
            self.id = ""
        else:
            self.id = name
        if self.parent.path:
            if self.id:
                self.path = self.parent.path + "/" + self.id
            else:
                self.path = self.parent.path
        else:
            self.path = self.id

    def add(self, info, name=None):
        if name is None:
            name = uuid.uuid4().hex
        doc_ref = self.document(name)
        doc_ref.set(info)
        return doc_ref

    def document(self, name):
        # TODO: how to know which kind of DocRef to make here?
        if name not in self:
            logging.debug(f"Adding document {name} in {self.path}")
            self[name] = BaseDocReference(self.path + "/" + name, parent=self)
        return self[name]

    def list_documents(self):
        return self.values()

    def reset_query(self):
        self.selected = None
        self.ordered = None
        self.filters = None

    def select(self, field_paths):
        self.selected = field_paths
        return self

    def order_by(self, field_path):
        # TODO: order fields when streaming below
        self.ordered = field_path
        return self

    def where(self, field_path, op_string, value):
        self.filters = (field_path, op_string, value)
        if op_string != "==":
            raise NotImplementedError
        return self

    def stream(self):
        # return BaseQuery(self).stream()
        for doc_ref in self.values():
            doc = doc_ref.get()
            if self.filters:
                value = doc[self.filters[0]]
                if self.filters[1] == "==":
                    if value != self.filters[2]:
                        continue
                # TODO: add <, <=, >= and >
            if self.selected:
                # we try to preserve .id etc. here
                copy = doc.copy()
                field_list = list(copy.keys())
                for field in field_list:
                    if field not in self.selected:
                        del copy[field]
                yield copy
            else:
                yield doc
        self.reset_query()


# Base document snapshot
class BaseDocument(dict):
    def __init__(self, doc_ref, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reference = doc_ref
        self.id = doc_ref.id
        self.exists = False
        if len(kwargs) > 0:
            self.exists = True
        self.create_time = time.time()
        self.update_time = self.create_time

    def to_dict(self):
        return dict(self)

    def copy(self):
        return type(self)(self.reference, dict(self))


class DirDocument(BaseDocument):
    def __init__(self, doc_ref, *args, **kwargs):
        super().__init__(doc_ref, *args, **kwargs)
        self.setdefault("count", 0)


class FileDocument(BaseDocument):
    def __init__(self, doc_ref, *args, **kwargs):
        super().__init__(doc_ref, *args, **kwargs)
        self.setdefault("size", 0)


class ChunkDocument(BaseDocument):
    def __init__(self, doc_ref, *args, **kwargs):
        super().__init__(doc_ref, *args, **kwargs)
        self.setdefault("size", 0)
        self.setdefault("offset", 0)
        self.setdefault("data", b"")


# Base query
class BaseQuery:
    def __init__(self, doc_ref, kind="Base"):
        self.reference = doc_ref
        self.kind = kind

    # when simulating without specific structure, we use an internal collection
    def stream(self):
        raise NotImplementedError
