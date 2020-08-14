#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: https://opensource.org/licenses/mit-license.php
#
from .base import BaseClient

import os.path
import hashlib
import logging


def get_structure(name="base", client=None):
    structures = {
        "base": BaseStructure,
        "file": FileStructure,
        "test": TestStructure,
        "tree": TreeStructure,
        "flat": FlatStructure,
    }
    if name not in structures:
        raise ValueError
    return structures[name](client)


#
# There are different ways to structure data in the Firestore database, as explained in
# https://cloud.google.com/firestore/docs/concepts/structure-data
#
class BaseStructure(object):
    def __init__(self, client):
        # Fake client for off-line testing - for any structure
        if client is None:
            # from .base import BaseClient
            client = BaseClient()
        logging.debug("Starting %s(%s)" % (type(self).__name__, client))
        self.client = client

    def convert_path_to_ref(self, path):
        # /my_coll/my_doc/your_coll/your_doc -> /my_coll/my_doc/your_coll/your_doc (no change)
        ref_path = path
        return ref_path

    def convert_ref_to_path(self, ref_path):
        # /my_coll/my_doc/your_coll/your_doc -> /my_coll/my_doc/your_coll/your_doc (no change)
        path = ref_path
        return path

    def get_doc_ref(self, path, kind="Base"):
        ref_path = self.convert_path_to_ref(path)
        doc_ref = self.client.document(ref_path)
        return doc_ref

    def get_coll_ref(self, path):
        ref_path = self.convert_path_to_ref(path)
        coll_ref = self.client.collection(ref_path)
        return coll_ref

    def get_parent_path(self, doc_ref):
        # /my_coll/my_doc/your_coll/your_doc -> /my_coll/my_doc/your_coll
        return os.path.dirname(doc_ref.path)

    def get_parent_ref(self, doc_ref):
        ref_path = self.get_parent_path(doc_ref)
        raise NotImplementedError("TODO: doc or coll?")

    def add_doc(self, doc_path, info=None):
        # doc_ref = self.client.document(doc_path)
        if isinstance(doc_path, str):
            doc_path = doc_path.split("/")
        doc_ref = self.client
        while len(doc_path) > 0:
            coll_name = doc_path.pop(0)
            coll_ref = doc_ref.collection(coll_name)
            doc_name = doc_path.pop(0)
            doc_ref = coll_ref.document(doc_name)
            # if not doc_ref.get().exists:
            #     doc_ref.set({'size': 0})
        if info:
            return self.create_doc(doc_ref, info)
        return doc_ref

    def add_coll_doc(self, coll_ref, doc_id=None, info=None):
        if doc_id:
            doc_ref = coll_ref.document(doc_id)
            logging.debug("Adding doc %s" % doc_ref.path)
            if info:
                return self.create_doc(doc_ref, info)
            return doc_ref
        timestamp, doc_ref = coll_ref.add(info)
        logging.debug("Adding doc %s" % doc_ref.path)
        return doc_ref

    def create_doc(self, doc_ref, info, merge=False):
        logging.debug("Creating doc %s" % doc_ref.path)
        if merge:
            return doc_ref.set(info, merge)
        return doc_ref.set(info)

    def update_doc(self, doc_ref, info):
        logging.debug("Updating doc %s" % doc_ref.path)
        return doc_ref.update(info)

    def delete_doc(self, doc_ref):
        logging.debug("Deleting doc %s" % doc_ref.path)
        return doc_ref.delete()

    def get_doc(self, doc_ref, field_paths=None):
        return doc_ref.get(field_paths)

    def watch_doc(self, doc_ref, callback):
        return doc_ref.on_snapshot(callback)

    def get_doc_coll(self, doc_ref, coll_name):
        if doc_ref is None:
            return self.client.collection(coll_name)
        return doc_ref.collection(coll_name)

    def watch_coll(self, coll_ref, callback):
        return coll_ref.on_snapshot(callback)

    def get_coll_query(self, coll_ref, field_paths=None, where=None, order_by=None):
        query = coll_ref
        if field_paths:
            query = query.select(field_paths)
        if where:
            query = query.where(where)
        if order_by:
            query = query.order_by(order_by)
        return query

    def get_doc_query(
        self, doc_ref, coll_name, field_paths=None, where=None, order_by=None
    ):
        # return doc_ref.collection(coll_name).select(field_paths).where(where).order_by(order_by)
        coll_ref = self.get_doc_coll(doc_ref, coll_name)
        return self.get_coll_query(
            coll_ref, field_paths=field_paths, where=where, order_by=order_by
        )

    def list_query_docs(
        self, query, limit=None, offset=None, start_at=None, end_at=None
    ):
        return list(
            self.ilist_query_docs(
                query, limit=limit, offset=offset, start_at=start_at, end_at=end_at
            )
        )

    def ilist_query_docs(
        self, query, limit=None, offset=None, start_at=None, end_at=None
    ):
        # TODO: apply limit, offset, start_at, end_at
        for doc in query.stream():
            # info = doc.to_dict()
            # info.update(doc.__dict__)
            # info['create_time'] = doc.create_time
            # info['update_time'] = doc.update_time
            # yield info
            yield doc

    def list_coll_refs(self, coll_ref, page_size=None):
        return list(self.ilist_coll_refs(coll_ref, page_size=page_size))

    def ilist_coll_refs(self, coll_ref, page_size=None):
        for doc_ref in coll_ref.list_documents(page_size=page_size):
            yield doc_ref

    def list_doc_colls(self, doc_ref, page_size=None):
        return list(self.ilist_doc_colls(doc_ref, page_size=page_size))

    def ilist_doc_colls(self, doc_ref, page_size=None):
        for coll_ref in doc_ref.collections(page_size=page_size):
            yield coll_ref

    def list_root(self):
        return list(self.client.collections())

    def close(self):
        self.client = None


# When simulating without specific structure, we use an internal collection '_'
def _build_tree(root, doc_path, kind):
    # logging.debug('Building tree %s' % doc_path)
    if isinstance(doc_path, str):
        doc_path = doc_path.split("/")
    if doc_path[0] == "root":
        doc_path.pop(0)
    doc_ref = root
    coll_name = "root"
    while len(doc_path) > 0:
        doc_name = doc_path.pop(0)
        if doc_name == "" or doc_name == "_":
            continue
        coll_ref = doc_ref.collection(coll_name)
        doc_ref = coll_ref.document(doc_name)
        coll_name = "_"
    # doc_ref = BaseDocReference(doc_path, kind)
    return doc_ref


#
# Because collections cannot have subcollections directly, each Dir and File is a document
#
# Below are two possible ways to do it: by using a tree structure with subcollections, or
# a flat structure with parent path field as used with Firestore in Datastore mode
#
class FileStructure(BaseStructure):

    with_parent_path = False

    def __init__(self, client):
        super(FileStructure, self).__init__(client)
        self.count = 0

    def convert_path_to_ref(self, path):
        # /test/my_dir/your_dir/my_file -> /test/my_dir/your_dir/my_file (no change)
        return path

    def convert_ref_to_path(self, path):
        # /test/my_dir/your_dir/my_file -> /test/my_dir/your_dir/my_file (no change)
        if path.startswith("_/"):
            path = path[1:]
        elif path.startswith("root/"):
            path = path[4:]
        return path.replace("/_/", "/")

    def get_doc_ref(self, path, kind="Base"):
        ref_path = self.convert_path_to_ref(path)
        # doc_ref = BaseDocReference(ref_path, kind)
        # Fake root for off-line or on-line testing - for BaseStructure only (try self.client on-line)
        if not hasattr(self, "fake_root"):
            # self.fake_root = BaseDocReference('')
            self.fake_root = self.client
        doc_ref = _build_tree(self.fake_root, ref_path, kind)
        return doc_ref

    def get_dir_ref(self, path):
        return self.get_doc_ref(path, "Dir")

    def get_file_ref(self, path):
        return self.get_doc_ref(path, "File")

    def get_chunk_ref(self, path):
        return self.get_doc_ref(path, "Chunk")

    def get_parent_path(self, doc_ref):
        # /test/my_dir/your_dir/my_file -> /test/my_dir/your_dir
        return os.path.dirname(doc_ref.path)

    def get_parent_ref(self, doc_ref):
        ref_path = self.get_parent_path(doc_ref)
        # TODO: what if we need file_ref for chunk someday?
        return self.get_dir_ref(ref_path)

    def add_chunk(self, file_ref, data, offset=0):
        # info = {'data': data, 'size': len(data), 'offset': offset}
        info = {"size": len(data), "offset": offset, "data": data}
        chunk_id = hashlib.md5(file_ref.path.encode("utf-8")).hexdigest()
        chunk_path = file_ref.path + "/" + chunk_id + "-" + str(offset)
        chunk_ref = self.get_chunk_ref(chunk_path)
        logging.debug("Adding chunk %s" % chunk_ref.path)
        # for delayed info here
        chunk_ref.set(info)
        # chunk_ref.update()
        return chunk_ref.get()

    def create_file(self, file_ref, data):
        logging.debug("Creating file %s" % file_ref.path)
        info = {"size": len(data)}
        if self.with_parent_path:
            parent = self.get_parent_ref(file_ref)
            info.update({"parent_ref": parent})
        file_ref.set(info)
        offset = 0
        self.add_chunk(file_ref, data, offset)
        # file_ref.collection('c').add({'offset': 0, 'size': len(data), 'data': data})
        # TODO: update count of file_ref.parent.parent (= document that owns the collection this file belongs to)
        # self.client.collection(self.chunks).add({'offset': offset, 'size': len(data), 'data': data, 'parent_ref': file_ref})
        # TODO: update count of parent
        # see firestore.transactional or washington_ref.update({"population": firestore.Increment(50)})
        return file_ref.get()

    def get_chunks_query(self, file_ref):
        return file_ref.collection("_").select(["offset", "size"]).order_by("offset")
        # return file_ref.collection('_')

    def update_file_size(self, file_ref):
        logging.debug("Updating size %s" % file_ref.path)
        # offset = 0
        size = 0
        for chunk in self.get_chunks_query(file_ref).stream():
            print("Chunk", chunk.id, chunk.to_dict())
            # data = b'=' * 1024
            # chunk.reference.update({'data': data, 'size': len(data), 'offset': offset})
            size += chunk.get("size")
            # offset += 1
        file_ref.update({"size": size})
        return file_ref.get()

    def iget_chunks_data(self, file_ref):
        query = file_ref.collection("_").order_by("offset")
        for chunk in query.stream():
            yield chunk.get("data")

    def get_chunks_data(self, file_ref):
        content = b""
        for data in self.iget_chunks_data(file_ref):
            content += data
        return content

    def get_file_data(self, path):
        file_ref = self.get_file_ref(path)
        return self.get_chunks_data(file_ref)

    def create_dir(self, dir_ref):
        logging.debug("Creating dir %s" % dir_ref.path)
        info = {"count": 0}
        if self.with_parent_path:
            parent = self.get_parent_ref(dir_ref)
            info.update({"parent_ref": parent})
        dir_ref.set(info)
        # dir_ref.collection('d').document('.empty').set({'size': 0})
        return dir_ref.get()

    def get_dir_query(self, dir_ref, field_paths=["size", "count"]):
        # for doc in dir_ref.collection('d').select(['size', 'count']).stream():
        # return dir_ref.collection('d').stream()
        # return self.client.collection(self.paths).select(['size', 'count']).where('parent_ref', '==', dir_ref).stream()
        # return []
        return dir_ref.collection("_").select(field_paths)

    def update_dir_count(self, dir_ref):
        logging.debug("Updating count %s" % dir_ref.path)
        count = 0
        for doc in self.get_dir_query(dir_ref).stream():
            count += 1
        dir_ref.update({"count": count})
        return dir_ref.get()

    def list_dir_docs(self, path, recursive=False):
        dir_ref = self.get_dir_ref(path)
        print("Stream Documents %s" % dir_ref.path)
        return self.list_coll_docs(self.get_dir_query(dir_ref), recursive)

    def list_coll_docs(self, query, recursive=False, depth=0):
        result = []
        # for doc in dir_ref.collection('d').select(['size', 'count']).stream():
        for doc in query.stream():
            info = doc.to_dict()
            info.update(doc.__dict__)
            # info['create_time'] = doc.create_time
            # info['update_time'] = doc.update_time
            result.append(info)
            # CHECKME: no need to check all subcollections here - is this faster?
            if "count" in doc.to_dict():
                # subcoll_refs = dict([(coll_ref.id, coll_ref) for coll_ref in doc.reference.collections()])
                print("  " * depth, "Dir", doc.id, doc.to_dict())
                if recursive:
                    self.list_coll_docs(
                        self.get_dir_query(doc.reference), recursive, depth + 1
                    )
            else:
                print("  " * depth, "File", doc.id, doc.to_dict())
        return result

    # the following methods aren't really the best way to walk through a hierarchy - better to get all docs at once
    def list_dirs(self, dir_path):
        # return self.list_dir_docs(dir_path, recursive=False, field_paths=['count']) # does not filter
        dir_ref = self.get_dir_ref(dir_path)
        query = self.get_dir_query(dir_ref).where("count", ">=", 0)
        return self.list_coll_docs(query)

    def list_files(self, dir_path):
        # return self.list_dir_docs(dir_path, recursive=False, field_paths=['size']) # does not filter
        dir_ref = self.get_dir_ref(dir_path)
        query = self.get_dir_query(dir_ref).where("size", ">=", 0)
        return self.list_coll_docs(query)

    # the following methods only apply when dealing with a dir collection supporting .list_documents(), i.e. not flat
    def get_dir_coll(self, dir_ref):
        return dir_ref.collection("_")

    def list_dir_refs(self, path, recursive=False):
        dir_ref = self.get_dir_ref(path)
        print("List Document Refs for %s" % path)
        self.list_coll_refs(self.get_dir_coll(dir_ref), recursive)

    def list_coll_refs(self, coll_ref, recursive=False, depth=0):
        for doc_ref in coll_ref.list_documents():
            # print('Ref', doc_ref.id, to_dict(doc_ref), [subcoll_ref.id for subcoll_ref in doc_ref.collections()])
            # subcoll_refs = dict([(subcoll_ref.id, subcoll_ref) for coll_ref in doc_ref.collections()])
            # print("  " * depth, 'Ref', doc_ref.path, list(subcoll_refs.keys()))
            # if recursive and 'd' in subcoll_refs:
            #    self.list_coll_refs(subcoll_refs['d'], recursive, depth + 1)
            # has_dir_coll = self.get_dir_coll(doc_ref).document('.empty').get().exists
            has_dir_coll = "count" in doc_ref.get(["count"]).to_dict()
            print("  " * depth, "Ref", doc_ref.path, has_dir_coll)
            if recursive and has_dir_coll:
                self.list_coll_refs(self.get_dir_coll(doc_ref), recursive, depth + 1)


class TestStructure(FileStructure):
    def make_file(self, path, data=b""):
        file_ref = self.get_file_ref(path)
        doc = file_ref.get()
        # CHECKME: if some of the parent dirs don't exist, they won't really be created as documents - ghost :-)
        if not doc.exists:
            doc = self.create_file(file_ref, data)
        else:
            logging.debug("Found file %s" % file_ref.path)
        # if doc.to_dict()['size'] == 0:
        if doc.get("size") != len(data):
            doc = self.update_file_size(file_ref)
        assert doc.exists
        # print(path, doc.reference.path, self.convert_ref_to_path(doc.reference.path))
        assert path == self.convert_ref_to_path(doc.reference.path)
        # assert data == self.get_file_data(path)
        assert doc.get("size") == len(data)
        return doc

    def make_dir(self, path):
        dir_ref = self.get_dir_ref(path)
        doc = dir_ref.get()
        if not doc.exists:
            doc = self.create_dir(dir_ref)
        else:
            logging.debug("Found dir %s" % dir_ref.path)
        if doc.get("count") == 0:
            doc = self.update_dir_count(dir_ref)
        assert doc.exists
        assert path == self.convert_ref_to_path(doc.reference.path)
        # assert doc.get('count') > 0
        return doc

    def make_tree(self, parent, depth):
        dirname = os.path.basename(parent).replace("test", "dir")
        filename = dirname.replace("dir", "file")
        data = b"x" * 1024
        for i in range(1, 10):
            name = "%s.%s.txt" % (filename, i)
            path = os.path.join(parent, name)
            print("  " * depth, path)
            self.make_file(path, data)
            self.count += 1
        if depth > 1:
            return
        for i in range(1, 10):
            name = "%s.%s" % (dirname, i)
            path = os.path.join(parent, name)
            print("  " * depth, path)
            self.make_dir(path)
            self.make_tree(path, depth + 1)

    def clean_file(self, path):
        logging.debug("Deleting File %s" % path)
        file_ref = self.get_file_ref(path)
        # we need to retrieve the list first here, before deleting chunks
        chunk_list = list(self.get_chunks_query(file_ref).stream())
        for chunk in chunk_list:
            logging.debug("Deleting Chunk %s" % chunk.id)
            chunk.reference.delete()
        file_ref.delete()

    def clean_dir(self, path):
        logging.debug("Deleting Dir %s" % path)
        dir_ref = self.get_dir_ref(path)
        dir_ref.delete()

    def clean_tree(self, parent, depth):
        dirname = os.path.basename(parent).replace("test", "dir")
        filename = dirname.replace("dir", "file")
        for i in range(1, 10):
            name = "%s.%s.txt" % (filename, i)
            path = os.path.join(parent, name)
            print("  " * depth, path)
            self.clean_file(path)
            self.count -= 1
        if depth > 1:
            return
        for i in range(1, 10):
            name = "%s.%s" % (dirname, i)
            path = os.path.join(parent, name)
            print("  " * depth, path)
            self.clean_tree(path, depth + 1)
            # self.clean_file(path + '/.empty')
            self.clean_dir(path)


#
# Note: outdated - FileStructure is actually nicer :-)
#
# In TreeStructure, Dirs have a 'd' subcollection to hold the child dir & file documents
# So each / in the file path is replaced by a Dir document + a 'd' subcollection
#
# Files have their own 'c' subcollection to hold the data chunks
#
class TreeStructure(TestStructure):

    with_parent_path = False

    def __init__(self, client, files="files"):
        super(TreeStructure, self).__init__(client)
        self.root = files + "/"
        self.count = 0

    def convert_path_to_ref(self, path):
        if path[0] == "/":
            path = path[1:]
        # /test/my_dir/your_dir/my_file -> files/test/d/my_dir/d/your_dir/d/my_file
        ref_path = self.root + path.replace("/", "/d/")
        return ref_path

    def convert_ref_to_path(self, ref_path):
        if not ref_path.startswith(self.root):
            raise ValueError
        # files/test/d/my_dir/d/your_dir/d/my_file -> /test/my_dir/your_dir/my_file
        path = ref_path[5:].replace("/d/", "/")
        return path

    def get_doc_ref(self, path, kind="Base"):
        ref_path = self.convert_path_to_ref(path)
        doc_ref = self.client.document(ref_path)
        return doc_ref

    def get_parent_path(self, doc_ref):
        # files/test/d/my_dir/d/your_dir/d/my_file -> files/test/d/my_dir/d/your_dir
        return "/".join(doc_ref.path.split("/")[:-2])

    def get_parent_ref(self, doc_ref):
        ref_path = self.get_parent_path(doc_ref)
        doc_ref = self.client.document(ref_path)
        return doc_ref

    def add_chunk(self, file_ref, data, offset=0):
        result = file_ref.collection("c").add(
            {"offset": offset, "size": len(data), "data": data}
        )
        return result

    def get_chunks_query(self, file_ref):
        return file_ref.collection("c").select(["offset", "size"]).order_by("offset")

    def iget_chunks_data(self, file_ref):
        query = file_ref.collection("c").order_by("offset")
        for chunk in query.stream():
            yield chunk.get("data")

    def create_dir(self, dir_ref):
        logging.debug("Creating dir %s" % dir_ref.path)
        dir_ref.set({"count": 0})
        # CHECKME: do we really need this?
        # dir_ref.collection('d').document('.empty').set({'size': 0})
        return dir_ref.get()

    def get_dir_query(self, dir_ref, field_paths=["size", "count"]):
        # for doc in dir_ref.collection('d').select(['size', 'count']).stream():
        return dir_ref.collection("d").select(field_paths)

    # the following methods only apply when dealing with a dir collection supporting .list_documents(), i.e. not flat
    def get_dir_coll(self, dir_ref):
        return dir_ref.collection("d")


#
# In FlatStructure, no subcollections are used but we have 'paths' and 'chunks' collections with documents
# containing a parent path field like with Google Cloud Firestore in Datastore mode
#
class FlatStructure(TestStructure):

    with_parent_path = True

    def __init__(self, client, paths="paths", chunks="chunks"):
        super(FlatStructure, self).__init__(client)
        self.paths = paths
        self.chunks = chunks

    def convert_path_to_ref(self, path):
        if path[0] == "/":
            path = path[1:]
        # /test/my_dir/your_dir/my_file -> test:my_dir:your_dir:my_file
        ref_path = path.replace("/", ":")
        return ref_path

    def convert_ref_to_path(self, ref_path):
        # paths/test:my_dir:your_dir:my_file -> /test/my_dir/your_dir/my_file
        path = ref_path[len(self.paths) :].replace(":", "/")
        return path

    def get_doc_ref(self, path, kind="Base"):
        ref_path = self.convert_path_to_ref(path)
        if not ref_path:
            return None
        doc_ref = self.client.collection(self.paths).document(ref_path)
        return doc_ref

    def get_parent_path(self, doc_ref):
        # test:my_dir:your_dir:my_file -> test:my_dir:your_dir
        return ":".join(doc_ref.id.split(":")[:-1])

    def get_parent_ref(self, doc_ref):
        ref_path = self.get_parent_path(doc_ref)
        if not ref_path:
            return None
        doc_ref = self.client.collection(self.paths).document(ref_path)
        return doc_ref

    def add_chunk(self, file_ref, data, offset=0):
        result = self.client.collection(self.chunks).add(
            {"offset": offset, "size": len(data), "data": data, "parent_ref": file_ref}
        )
        return result

    def get_chunks_query(self, file_ref):
        return (
            self.client.collection(self.chunks)
            .select(["offset", "size"])
            .where("parent_ref", "==", file_ref)
            .order_by("offset")
        )

    def iget_chunks_data(self, file_ref):
        query = (
            self.client.collection(self.chunks)
            .where("parent_ref", "==", file_ref)
            .order_by("offset")
        )
        for chunk in query.stream():
            yield chunk.get("data")

    def get_dir_query(self, dir_ref, field_paths=["size", "count"]):
        # return self.client.collection(self.paths).where('parent_ref', '==', dir_ref).stream()
        return (
            self.client.collection(self.paths)
            .select(field_paths)
            .where("parent_ref", "==", dir_ref)
        )

    # the following methods only apply when dealing with a dir collection supporting .list_documents(), i.e. not flat
    def get_dir_coll(self, dir_ref):
        raise NotImplementedError
