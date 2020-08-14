#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# (c) 2010 Martin Wendt; see CloudDAV http://clouddav.googlecode.com/
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
#
# The original source for this module was taken from gaedav:
# (c) 2009 Haoyu Bai (http://gaedav.google.com/).
"""
Implement cache mechanism.
"""
import logging
import threading
from builtins import object

from cachelib import MemcachedCache, RedisCache, SimpleCache

try:
    memcache3 = MemcachedCache()
    # memcache3 = RedisCache()
except Exception as e:
    logging.info(e)
    memcache3 = SimpleCache()

memcache3._stats = {
    "byte_hits": 0,
    "bytes": 0,
    "hits": 0,
    "items": 0,
    "misses": 0,
    "oldest_item_age": 0,
    # keep track of operations other than get (= hits + misses)
    "set": 0,
    "set_multi": 0,
    "delete": 0,
    "get_list": 0,
    "set_list": 0,
    "del_list": 0,
}


def memcache_reset(mycache=memcache3):
    for key in list(mycache._stats.keys()):
        mycache._stats[key] = 0
    return mycache.clear()


def memcache_get_stats(mycache=memcache3):
    return mycache._stats


memcache3.reset = memcache_reset
memcache3.get_stats = memcache_get_stats


# ===============================================================================
# NamespacedCache
# ===============================================================================
class NamespacedCache(object):
    def __init__(self, namespace):
        if hasattr(threading, "get_ident"):
            id = threading.get_ident()
        else:
            id = threading._get_ident()
        logging.debug("NamespacedCache.__init__, thread=%s", id)
        self.namespace = namespace
        self.stop_cache = False
        return

    def __del__(self):
        if hasattr(threading, "get_ident"):
            id = threading.get_ident()
        else:
            id = threading._get_ident()
        logging.debug("NamespacedCache.__del__, thread=%s", id)

    def _add_namespace(self, key):
        if self.namespace is not None:
            key = "%s:%s" % (self.namespace, key)
        return key

    def get(self, key):
        if self.stop_cache:
            return
        key = self._add_namespace(key)
        result = memcache3.get(key)
        if result is not None:
            memcache3._stats["hits"] += 1
            logging.debug("Cache HIT: %r.%r" % (self.namespace, key))
        else:
            memcache3._stats["misses"] += 1
            logging.debug("Cache MISS: %r.%r" % (self.namespace, key))
        return result

    def set(self, key, value, time=0):
        if self.stop_cache:
            return
        logging.debug("Cache add: %r.%r = %r" % (self.namespace, key, value))
        key = self._add_namespace(key)
        memcache3._stats["set"] += 1
        return memcache3.set(key, value, timeout=time)

    def set_multi(self, mapping, time=0, key_prefix=""):
        if self.stop_cache:
            return []
        new_mapping = {}
        for key, value in list(mapping.items()):
            logging.debug("Cache add multi: %r.%r = %r" % (self.namespace, key, value))
            if key_prefix:
                key = key_prefix + key
            key = self._add_namespace(key)
            new_mapping[key] = value
        memcache3._stats["set_multi"] += 1
        # this returns True on success or False on failure, but set_multi expects a list of failed keys back
        result = memcache3.set_many(new_mapping, timeout=time)
        if result:
            return []
        return ["failed"]

    def delete(self, key):
        if self.stop_cache:
            return
        logging.debug("Cache delete: %r.%r" % (self.namespace, key))
        key = self._add_namespace(key)
        memcache3._stats["delete"] += 1
        return memcache3.delete(key)

    def get_list(self, key):
        if self.stop_cache:
            return
        key = "list:" + self._add_namespace(key)
        memcache3._stats["get_list"] += 1
        result = memcache3.get(key)
        if result is not None:
            memcache3._stats["hits"] += len(result)
        return result

    def set_list(self, key, value, time=0):
        if self.stop_cache:
            return
        key = "list:" + self._add_namespace(key)
        memcache3._stats["set_list"] += 1
        if value is not None:
            memcache3._stats["misses"] += len(value)
        return memcache3.set(key, value, timeout=time)

    def del_list(self, key):
        if self.stop_cache:
            return
        key = "list:" + self._add_namespace(key)
        memcache3._stats["del_list"] += 1
        return memcache3.delete(key)


# ===============================================================================
#
# ===============================================================================
logging.debug("import cache.py")
cached_doc = NamespacedCache("doc")
