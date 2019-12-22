# -*- coding: iso-8859-1 -*-
import logging
import threading
from builtins import object

from cachelib import MemcachedCache, RedisCache, SimpleCache

# (c) 2010 Martin Wendt; see CloudDAV http://clouddav.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
#
# The original source for this module was taken from gaedav:
# (c) 2009 Haoyu Bai (http://gaedav.google.com/).
"""
Implement cache mechanism.
"""

"""
With Python 2.7 this defaults to the standard App Engine Memcache service.
With Python 3.7 you'll need to specify the Memcache or Redis server(s)...

TODO: make this configurable
"""
try:
    memcache3 = MemcachedCache()
    #memcache3 = RedisCache()
except Exception as e:
    logging.info(e)
    memcache3 = SimpleCache()

memcache3._stats = {
    'byte_hits': 0,
    'bytes': 0,
    'hits': 0,
    'items': 0,
    'misses': 0,
    'oldest_item_age': 0,
    # keep track of operations other than get (= hits + misses)
    'set': 0,
    'set_multi': 0,
    'delete': 0,
    'get_list': 0,
    'set_list': 0,
    'del_list': 0
}

def memcache_reset(mycache=memcache3):
    for key in list(mycache._stats.keys()):
        mycache._stats[key] = 0
    return mycache.clear()

def memcache_get_stats(mycache=memcache3):
    return mycache._stats

memcache3.reset = memcache_reset
memcache3.get_stats = memcache_get_stats

CACHED_NONE = "{cached-none}"

#def sessioncached(f):
#    """
#    The cache only live in one session.
#    """
#    cache_dict = dict()  # used by the inner function
#    def cached_func(*args, **kwargs):
#        t = (args, kwargs.items())
#        try:
#            hash(t)
#            key = t
#        except TypeError:
#            try:
#                import pickle
#                key = pickle.dumps(t)
#            except pickle.PicklingError:
#                logging.warn("Cache FAIL: can't hash %s(args=%s, kwargs=%s)", repr(f), repr(args), repr(kwargs))
#                return f(*args, **kwargs)
#        if cache_dict.get(key) is not None:
#            logging.info("Cache HIT: %s(args=%s, kwargs=%s)", repr(f), repr(args), repr(kwargs))
#            return cache_dict[key]
#        logging.info("Cache MISS: %s(args=%s, kwargs=%s)", repr(f), repr(args), repr(kwargs))
#        value = f(*args, **kwargs)
#        cache_dict[key]=value
#        return value
#    try:
#        cached_func.func_name = f.func_name
#    except AttributeError:
#        # for class method which has no func_name
#        pass
#    return cached_func

# TODO Maybe more faster if we apply sessioncache to memcache.

#===============================================================================
# ExtendedCache
#===============================================================================
#class ExtendedCache(object):
#    """
#    Wrapper for google.appengine.api.memcache that provides additional
#    features:
#    
#    - Applies a name space to all keys 
#    - Adds a per-request caching by using a WSGI `environ` dictionary
#    - Invokes callbacks on cache miss to access the datastore
#    - Also caches 'None' results
#    """
#    def __init__(self, namespace, get_func=None, set_func=None):
#        self.namespace = namespace
#        self.get_func = get_func
#        self.set_func = set_func
#        return
#
#
#    def _namespaced(self, s):
#        return "wsgidav.%s.%s" % (self.namespace, s)
#    
#    
#    def get(self, key, environ):
#        try:
#            # The environ dictionary can cache None values
#            nskey = self._namespaced(key)
#            result = environ[nskey] 
#            logging.debug("Request-Cache HIT: %s" % nskey)
#            return result 
#        except KeyError:
#            pass
#
#        result = memcache.get(key, namespace=self.namespace)
#        if result == CACHED_NONE:
#            environ[nskey] = None
#            logging.debug("Memcache HIT: %r.%r (cached-None)" % (self.namespace, key))
#            return None 
#        elif result is not None:
#            environ[nskey] = result
#            logging.debug("Memcache HIT: %r.%r" % (self.namespace, key))
#            return result
#        logging.debug("Memcache MISS: %r.%r" % (self.namespace, key))
#
#        if self.get_func:
#            result = self.get_func(key)
#            self.set(key, result, environ)
#
#        return result
#
#
#    def set(self, key, value, environ, time=0):
#        # The environ dictionary can cache None values
#        environ[self._namespaced(key)] = value
#        # memcache.get cannot return None, so we escape it
#        if value is None:
#            value = CACHED_NONE
#        return memcache.set(key, value, namespace=self.namespace, time=time)
#
#
#    def set_multi(self, mapping, environ, time=0, key_prefix=''):
#        m2 = mapping.copy()
#        for key, value in mapping.items():
#            # add to request-cache
#            environ[self._namespaced(key)] = value
#            # escape 'None' for memcache
#            if value is None:
#                m2[key] = CACHED_NONE
#            else:
#                m2[key] = value
#        
#        return memcache.set_multi(mapping, namespace=self.namespace, time=time, 
#                                  key_prefix=key_prefix)
#
#
#    def delete(self, key, environ):
#        try:
#            del environ[self._namespaced(key)] 
#        except KeyError:
#            pass
#        return memcache.delete(key, namespace=self.namespace)


#===============================================================================
# NamespacedCache
#===============================================================================
class NamespacedCache(object):
    def __init__(self, namespace):
        if hasattr(threading, 'get_ident'):
            id = threading.get_ident()
        else:
            id = threading._get_ident()
        logging.debug("NamespacedCache.__init__, thread=%s", id)
        self.namespace = namespace
        return

    
    def __del__(self):
        if hasattr(threading, 'get_ident'):
            id = threading.get_ident()
        else:
            id = threading._get_ident()
        logging.debug("NamespacedCache.__del__, thread=%s", id)


    def _add_namespace(self, key):
        if self.namespace is not None:
            key = '%s:%s' % (self.namespace, key)
        return key

    def get(self, key):
        key = self._add_namespace(key)
        result = memcache3.get(key)
        if result is not None:
            memcache3._stats['hits'] += 1
            logging.debug("Cache HIT: %r.%r" % (self.namespace, key))
        else:
            memcache3._stats['misses'] += 1
            logging.debug("Cache MISS: %r.%r" % (self.namespace, key))
        return result


    def set(self, key, value, time=0):
        logging.debug("Cache add: %r.%r = %r" % (self.namespace, key, value))
        key = self._add_namespace(key)
        memcache3._stats['set'] += 1
        return memcache3.set(key, value, timeout=time)


    def set_multi(self, mapping, time=0, key_prefix=''):
        new_mapping = {}
        for key, value in list(mapping.items()):
            logging.debug("Cache add multi: %r.%r = %r" % (self.namespace, key, value))
            if key_prefix:
                key = key_prefix + key
            key = self._add_namespace(key)
            new_mapping[key] = value
        memcache3._stats['set_multi'] += 1
        # this returns True on success or False on failure, but set_multi expects a list of failed keys back
        result = memcache3.set_many(new_mapping, timeout=time)
        if result:
            return []
        return ['failed']

    def delete(self, key):
        logging.debug("Cache delete: %r.%r" % (self.namespace, key))
        key = self._add_namespace(key)
        memcache3._stats['delete'] += 1
        return memcache3.delete(key)

    def get_list(self, key):
        key = 'list:' + self._add_namespace(key)
        memcache3._stats['get_list'] += 1
        result = memcache3.get(key)
        if result is not None:
            memcache3._stats['hits'] += len(result)
        return result

    def set_list(self, key, value, time=0):
        key = 'list:' + self._add_namespace(key)
        memcache3._stats['set_list'] += 1
        if value is not None:
            memcache3._stats['misses'] += len(value)
        return memcache3.set(key, value, timeout=time)

    def del_list(self, key):
        key = 'list:' + self._add_namespace(key)
        memcache3._stats['del_list'] += 1
        return memcache3.delete(key)


#===============================================================================
# 
#===============================================================================
logging.debug("import cache.py")
#cached_dir = NamespacedCache('dir')
#cached_file = NamespacedCache('file')
#cached_content = NamespacedCache('content')
cached_resource = NamespacedCache('resource')
cached_lock = NamespacedCache('lock')
cached_model = NamespacedCache('model')
#cached_lockpath = NamespacedCache('lockpath')
