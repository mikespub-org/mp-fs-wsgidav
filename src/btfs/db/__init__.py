from google.cloud import datastore
import os.path
import json
import logging
import datetime
from future.utils import with_metaclass

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


_class_map = {}


# Register Model classes so we can convert an entity to the right class again
class ModelType(type):

    def __init__(cls, name, bases, dct):
        super(ModelType, cls).__init__(name, bases, dct)
        _class_map[cls.__name__] = cls


# https://python-future.org/compatible_idioms.html#metaclasses
class Model(with_metaclass(ModelType, object)):
    #__metaclass__ = ModelType
    #_client = get_client()
    _kind = 'DummyModel'
    _exclude_from_indexes = None
    _auto_now_add = None
    _auto_now = None
    _entity = None

    #def __init__(self, parent=None, key_name=None, _app=None, _from_entity=False, **kwargs):
    def __init__(self, _from_entity=False, **kwargs):
        #_from_entity = kwargs.pop('_from_entity', False)
        if _from_entity:
            self._entity = _from_entity
        else:
            self._init_entity(**kwargs)
        #for key in list(kwargs.keys()):
        #    self._entity[key] = kwargs[key]

    def _init_entity(self, **kwargs):
        parent = kwargs.pop('parent', None)
        key_name = kwargs.pop('key_name', None)
        _app = kwargs.pop('_app', None)
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
        if key != '_entity' and self._entity:
            self._entity[key] = value
            return
        super(Model, self).__setattr__(key, value)

    def __getattribute__(self, key):
        if key != '_entity' and self._entity and key in self._entity:
            return self._entity[key]
        return super(Model, self).__getattribute__(key)

    def key(self):
        if self._entity and hasattr(self._entity, 'key'):
            return self._entity.key
        logging.warning('No key for %s' % self)

    def is_saved(self):
        if not self.key() or self.key().is_partial:
            return False
        return True

    def put(self, *args, **kwargs):
        if self._auto_now:
            for attr in self._auto_now:
                self._entity[attr] = datetime.datetime.utcnow()
        return get_client().put(self._entity)

    def delete(self):
        return get_client().delete(self._entity.key)

    @classmethod
    def from_entity(cls, entity):
        return cls(_from_entity=entity)

    @classmethod
    def class_name(cls):
        return cls.__name__

    #@classmethod
    #def gql(cls, *args, **kwargs):
    #    return GqlQuery(*args, **kwargs)

    @classmethod
    def query(cls, **kwargs):
        # CHECKME: possibly overridden in PolyModel
        query = get_client().query(kind=cls._kind, **kwargs)
        return query

    @classmethod
    def get(cls, key):
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
    def get_count(cls, limit=1000, offset=0, **kwargs):
        query = cls.query(**kwargs)
        query.keys_only()
        result = len(list(query.fetch(limit, offset)))
        return result

    @classmethod
    def properties(cls):
        return []

    @classmethod
    def kind(cls):
        return cls._kind


#class GqlQuery(list):
#
#    def __init__(self, query_string=None, *args, **kwargs):
#        print(query_string, args, kwargs)
#        pass
#
#    def get(self):
#        pass


#class DummyProperty(object):
#
#    def __init__(self, *args, **kwargs):
#        pass
#
#    def __str__(self):
#        if hasattr(self, 'path'):
#            return self.path


#StringProperty = DummyProperty
#IntegerProperty = DummyProperty
#DateTimeProperty = DummyProperty
#ReferenceProperty = DummyProperty
#BlobProperty = DummyProperty
#UserProperty = DummyProperty
#BooleanProperty = DummyProperty


#class ReferencePropertyResolveError(Exception):
#    pass
#
