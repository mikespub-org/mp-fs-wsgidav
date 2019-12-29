import datetime
import logging
import os.path

from future.utils import with_metaclass
from google.cloud import datastore

from ..cache import cached_model

_client = None


def get_client(project_id=None, cred_file=None):
    global _client
    if _client is not None:
        return _client
    if cred_file and os.path.isfile(cred_file):
        _client = datastore.Client.from_service_account_json(cred_file)
    else:
        _client = datastore.Client(project_id)
    return _client


def make_entity(key, exclude_from_indexes=None, **kwargs):
    if exclude_from_indexes:
        entity = datastore.Entity(key, exclude_from_indexes=exclude_from_indexes)
    else:
        entity = datastore.Entity(key)
    if kwargs and len(kwargs) > 0:
        entity.update(kwargs)
    return entity


def delete(keys):
    if isinstance(keys, list):
        return get_client().delete_multi(keys)
    return get_client().delete(keys)


_class_map = {}


# Register Model classes so we can convert an entity to the right class again
class ModelType(type):
    def __init__(cls, name, bases, dct):
        super(ModelType, cls).__init__(name, bases, dct)
        _class_map[cls.__name__] = cls


# https://python-future.org/compatible_idioms.html#metaclasses
class Model(with_metaclass(ModelType, object)):
    # __metaclass__ = ModelType
    # _client = get_client()
    _kind = "DummyModel"
    _exclude_from_indexes = None
    _auto_now_add = None
    _auto_now = None
    _entity = None

    # def __init__(self, parent=None, key_name=None, _app=None, _from_entity=False, **kwargs):
    def __init__(self, _from_entity=False, **kwargs):
        # _from_entity = kwargs.pop('_from_entity', False)
        if _from_entity is not False:
            self._entity = _from_entity
        else:
            self._init_entity(**kwargs)
        # for key in list(kwargs.keys()):
        #    self._entity[key] = kwargs[key]

    def _init_entity(self, **kwargs):
        parent = kwargs.pop("parent", None)
        key_name = kwargs.pop("key_name", None)
        _app = kwargs.pop("_app", None)
        # CHECKME: this is expected to be the model.key() already
        if parent:
            if key_name:
                key = get_client().key(self._kind, key_name, parent=parent)
            else:
                key = get_client().key(self._kind, parent=parent)
        elif key_name:
            key = get_client().key(self._kind, key_name)
        else:
            key = get_client().key(self._kind)
        self._entity = make_entity(key, self._exclude_from_indexes, **kwargs)

    def __setattr__(self, key, value):
        # if key != "_entity" and self._entity:
        if not key.startswith("_") and self._entity:
            self._entity[key] = value
            return
        super(Model, self).__setattr__(key, value)

    def __getattribute__(self, key):
        # if key != "_entity" and self._entity and key in self._entity:
        if not key.startswith("_") and self._entity and key in self._entity:
            return self._entity[key]
        return super(Model, self).__getattribute__(key)

    def key(self):
        # if self._entity and hasattr(self._entity, "key"):
        if (
            hasattr(self._entity, "key")
            and self._entity.key
            and self._entity.key.id_or_name
        ):
            return self._entity.key
        # logging.debug("No key for %r" % self.__dict__)

    def is_saved(self):
        if not self.key() or self.key().is_partial:
            return False
        return True

    def put(self, *args, **kwargs):
        if self._auto_now:
            for attr in self._auto_now:
                self._entity[attr] = datetime.datetime.now(datetime.timezone.utc)
        return get_client().put(self._entity)

    def delete(self):
        return get_client().delete(self._entity.key)

    def to_dict(self, include_key=False):
        info = dict(self._entity)
        if include_key:
            info["__key__"] = self.key()
        return info

    def __str__(self):
        return str(self.to_dict(True))

    @classmethod
    def from_entity(cls, entity):
        return cls(_from_entity=entity)

    @classmethod
    def class_name(cls):
        return cls.__name__

    # @classmethod
    # def gql(cls, *args, **kwargs):
    #    return GqlQuery(*args, **kwargs)

    @classmethod
    def query(cls, **kwargs):
        # CHECKME: possibly overridden in PolyModel
        query = get_client().query(kind=cls._kind, **kwargs)
        return query

    @classmethod
    def get(cls, key):
        if isinstance(key, str):
            key = get_client().key(cls._kind, key)
        entity = get_client().get(key)
        if entity:
            return cls.from_entity(entity)

    @classmethod
    def list_all(cls, limit=1000, offset=0, **kwargs):
        query = cls.query(**kwargs)
        result = []
        for entity in query.fetch(limit, offset):
            instance = cls.from_entity(entity)
            result.append(instance)
        return result

    @classmethod
    def ilist_all(cls, limit=1000, offset=0, **kwargs):
        query = cls.query(**kwargs)
        for entity in query.fetch(limit, offset):
            instance = cls.from_entity(entity)
            yield instance

    @classmethod
    def get_count(cls, limit=1000, offset=0, **kwargs):
        query = cls.query(**kwargs)
        query.keys_only()
        result = len(list(query.fetch(limit, offset)))
        return result

    @classmethod
    def get_by_property(cls, prop_name, value, **kwargs):
        # assume we always need a value here
        if not value:
            return
        query = cls.query(**kwargs)
        query.add_filter(prop_name, "=", value)
        entities = list(query.fetch(1))
        if entities and len(entities) > 0:
            return cls.from_entity(entities[0])

    @classmethod
    def properties(cls):
        return []

    @classmethod
    def kind(cls):
        return cls._kind


class CachedModel(Model):
    _kind = "CachedModel"

    cache = cached_model

    def get_key_name(self):
        return self.key().id_or_name

    def set_key(self):
        raise NotImplementedError

    def put(self):
        if not self.is_saved():
            self.set_key()
        super(CachedModel, self).put()
        cache_key = self._kind + "." + str(self.get_key_name())
        self.cache.set(cache_key, self)
        return

    def delete(self):
        cache_key = self._kind + "." + str(self.get_key_name())
        self.cache.delete(cache_key)
        return super(CachedModel, self).delete()

    @classmethod
    def get(cls, key):
        if isinstance(key, str):
            key_name = key
        else:
            key_name = key.id_or_name
        cache_key = cls._kind + "." + str(key_name)
        result = cls.cache.get(cache_key)
        if result:
            return result
        result = super(CachedModel, cls).get(key)
        if result:
            if result.get_key_name() != key_name:
                logging.warning(
                    "Key name mismatch: %s != %s" % (result.get_key_name(), key_name)
                )
            cls.cache.set(cache_key, result)
        return result

    @classmethod
    def get_by_property(cls, prop_name, value, **kwargs):
        # assume we always need a value here
        cache_key = cls._kind + "." + str(prop_name) + "=" + str(value)
        result = cls.cache.get(cache_key)
        if result:
            return result
        result = super(CachedModel, cls).get_by_property(prop_name, value, **kwargs)
        if result:
            cls.cache.set(cache_key, result)
        return result


# https://cloud.google.com/datastore/docs/concepts/metadataqueries#namespace_queries
def list_namespaces():
    query = get_query(kind="__namespace__")
    query.keys_only()

    all_namespaces = [entity.key.id_or_name for entity in query.fetch()]
    return all_namespaces


def list_kinds(with_meta=False):
    query = get_query(kind="__kind__")
    query.keys_only()

    kinds = [entity.key.id_or_name for entity in query.fetch()]
    if with_meta:
        kinds = list_metakinds() + kinds
    return kinds


def list_metakinds():
    return ["__namespace__", "__kind__", "__property__"]


def get_properties():
    from collections import defaultdict

    query = get_query(kind="__property__")
    # query.keys_only()

    # properties_by_kind = defaultdict(list)
    properties_by_kind = defaultdict(dict)

    for entity in query.fetch():
        kind = entity.key.parent.name
        property_name = entity.key.name
        property_types = entity["property_representation"]

        # properties_by_kind[kind].append(property_name)
        properties_by_kind[kind][property_name] = property_types

    return properties_by_kind


def get_properties_for_kind(kind):
    ancestor = get_key("__kind__", kind)
    query = get_query(kind="__property__", ancestor=ancestor)

    representations_by_property = {}

    for entity in query.fetch():
        property_name = entity.key.name
        # property_types = entity['property_representation']

        # representations_by_property[property_name] = property_types
        representations_by_property[property_name] = dict(entity)

    return representations_by_property


def list_entities(kind, limit=1000, offset=0, **kwargs):
    # TODO: use cursors in fetch() below if needed
    start_cursor = kwargs.pop("start_cursor", None)
    end_cursor = kwargs.pop("end_cursor", None)
    query = get_query(kind=kind, **kwargs)
    # result = {}
    # for entity in query.fetch(limit, offset):
    #     result[entity.key.id_or_name] = entity
    result = list(query.fetch(limit, offset))
    return result


def ilist_entities(kind, limit=1000, offset=0, **kwargs):
    # TODO: use cursors in fetch() below if needed
    start_cursor = kwargs.pop("start_cursor", None)
    end_cursor = kwargs.pop("end_cursor", None)
    query = get_query(kind=kind, **kwargs)
    for entity in query.fetch(limit, offset):
        yield entity


def list_entity_keys(kind, limit=1000, offset=0, **kwargs):
    # TODO: use cursors in fetch() below if needed
    start_cursor = kwargs.pop("start_cursor", None)
    end_cursor = kwargs.pop("end_cursor", None)
    query = get_query(kind=kind, **kwargs)
    query.keys_only()
    # result = [entity.key.id_or_name for entity in query.fetch(limit, offset)]
    result = [entity.key for entity in query.fetch(limit, offset)]
    return result


def ilist_entity_keys(kind, limit=1000, offset=0, **kwargs):
    # TODO: use cursors in fetch() below if needed
    start_cursor = kwargs.pop("start_cursor", None)
    end_cursor = kwargs.pop("end_cursor", None)
    query = get_query(kind=kind, **kwargs)
    query.keys_only()
    for entity in query.fetch(limit, offset):
        # yield entity.key.id_or_name
        yield entity.key


def get_query(kind, **kwargs):
    # namespace = kwargs.pop("namespace", None)
    # project = kwargs.pop("project", None)
    # ancestor = kwargs.pop("ancestor", None)
    # filters = kwargs.pop("filters", None)
    # projection = kwargs.pop("projection", None)
    # order = kwargs.pop("order", None)
    # distinct_on = kwargs.pop("distinct_on", None)
    query = get_client().query(kind=kind, **kwargs)
    return query


def get_entity_by_id(kind, id_or_name, **kwargs):
    key = get_key(kind, id_or_name, **kwargs)
    entity = get_entity(key)
    return entity


def get_entity(key):
    return get_client().get(key)


# Partial keys with *path_args are ('Parent', 'parent_id', 'Child', ...)
# Partial keys with **kwargs are ('Child', parent=parent_key)
def get_key(kind, id_or_name=None, *path_args, **kwargs):
    # namespace = kwargs.pop("namespace", None)
    # project = kwargs.pop("project", None)
    # parent = kwargs.pop("parent", None)
    path = [*path_args]
    path.append(kind)
    if id_or_name is not None:
        path.append(id_or_name)
    return get_client().key(*path, **kwargs)


class MakeModel(CachedModel):
    _kind = "MakeModel"

    # def __init__(self, parent=None, key_name=None, _app=None, _from_entity=False, **kwargs):
    def __init__(self, kind=None, _from_entity=False, **kwargs):
        # CHECKME: only used for make_instance() below - do not use a "kind" property elsewhere
        if kind is not None:
            self._kind = kind
        else:
            raise ValueError("Missing kind")
        super(MakeModel, self).__init__(_from_entity=_from_entity, **kwargs)

    def set_key(self):
        pass

    def isdir(self):
        return self.key() is None


def make_instance(kind, entity=None):
    if entity is None:
        instance = MakeModel(kind=kind)
    else:
        instance = MakeModel(kind=kind, _from_entity=entity)
    return instance


def close():
    global _client
    if _client is not None:
        # _client.close()
        _client = None
