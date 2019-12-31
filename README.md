# CloudDAV - looking for a new name

## Fork Status ##
The original version of [CloudDAV](https://github.com/mar10/clouddav) from 2010 was meant to run on Google App Engine with Python 2.5 and [WsgiDAV](https://github.com/mar10/wsgidav) 0.5.0

It provided the following [building blocks](https://wsgidav.readthedocs.io/en/latest/reference_guide_architecture.html):
  * Big Table DAV Provider for a virtual filesystem built on App Engine Datastore
  * Google Domain Controller to provide basic authentication (username/password) with Google Login
  * Memcache Lock Manager to support in-memory locks using App Engine Memcache
  * Property Manager partially integrated with the DAV Provider

The current version at https://github.com/mar10/clouddav and here in the [python27_base](https://github.com/mikespub-org/mar10-clouddav/tree/python27_base) branch from 2019-12 was ported to "work" with Python 2.7 and WsgiDAV 3.0.x - it remains in alpha.

The master branch here continues the modernization and uses Python 3.7+ with more recent Google Cloud services as back-end.
  * Datastore DAV Provider for a virtual filesystem built on Google [Cloud Firestore in Datastore mode](https://cloud.google.com/datastore/docs/)
  * Firebase Domain Controller to validate id tokens with Google Cloud [Identity Platform](https://cloud.google.com/identity-platform/docs/) (Firebase Authentication)
  * Cachelib Lock Manager to support in-memory locks using [cachelib](https://github.com/pallets/cachelib) (either memcache, redis or in-memory)
  * Property Manager partially integrated with the DAV Provider (?)
  * Firestore DAV Provider for a virtual filesystem built on Google [Cloud Firestore in native mode](https://cloud.google.com/firestore/docs/)

In addition, the following new filesystem providers were created for [PyFilestem2](https://docs.pyfilesystem.org/):
  * [Datastore FS](https://github.com/mikespub-org/mar10-clouddav/blob/master/src/btfs/datastore_fs.py) for basic support of Google Cloud Firestore in Datastore mode as filesystem for [PyFilestem2](https://docs.pyfilesystem.org/)
  * [Datastore DB](https://github.com/mikespub-org/mar10-clouddav/blob/master/src/btfs/datastore_db.py) for a read-only database explorer of Google Cloud Firestore in Datastore mode with [PyFilestem2](https://docs.pyfilesystem.org/)
  * Firestore FS for basic support of Google Cloud Firestore in native mode as filesystem for [PyFilestem2](https://docs.pyfilesystem.org/)
  * [Firestore DB](https://github.com/mikespub-org/mar10-clouddav/blob/master/src/fire/firestore_db.py) for a read-only database explorer of Google Cloud Firestore in native mode with [PyFilestem2](https://docs.pyfilesystem.org/)

![Datastore Diagram](https://github.com/mikespub-org/mar10-clouddav/raw/master/src/static/diagram.jpg)

And finally, you can now swap PyFilesystem2 filesystems and WsgiDAV DAV providers and use them in both environments:
  * [DAVProvider2FS](https://github.com/mikespub-org/mar10-clouddav/blob/master/src/mapper/fs_from_dav_provider.py) for basic support of WsgiDAV DAV providers as filesystem for PyFilesystem2
  * [FS2DAVProvider](https://github.com/mikespub-org/mar10-clouddav/blob/master/src/mapper/dav_provider_from_fs.py) for basic support of PyFilesystem2 filesystems as DAV provider for WsgiDAV

The purpose here is **not** to provide a production-ready version for use on Google Cloud, but to experiment with various newer back-end services and explore the differences with older versions. And of course have fun while doing it :-)

## Original Description ##

See [History](https://github.com/mikespub-org/mar10-clouddav/blob/master/HISTORY.md)
