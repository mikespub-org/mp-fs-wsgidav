## PyFilesystem2 and WsgiDAV Building Blocks for Google Cloud Firestore in Datastore mode

  * Datastore DAV Provider for a virtual filesystem built on Google [Cloud Firestore in Datastore mode](https://cloud.google.com/datastore/docs/) for WsgiDAV
  * Cachelib Cache Manager to support in-memory cache using [cachelib](https://github.com/pallets/cachelib) (either memcache, redis or in-memory)
  * [Datastore FS](https://github.com/mikespub-org/mp-fs-wsgidav/blob/master/src/data/datastore_fs.py) for basic support of Google Cloud Firestore in Datastore mode as filesystem for [PyFilestem2](https://docs.pyfilesystem.org/)
  * [Datastore DB](https://github.com/mikespub-org/mp-fs-wsgidav/blob/master/src/data/datastore_db.py) for a read-only database explorer of Google Cloud Firestore in Datastore mode with [PyFilestem2](https://docs.pyfilesystem.org/)

### Use the Datastore DAV provider, Datastore FS filesystem or Datastore DB explorer ###

If you want to use the Datastore DAV provider / FS filesystem / DB explorer yourself, you'll need to copy the [src/data/](https://github.com/mikespub-org/mp-fs-wsgidav/tree/master/src/data) directory to your project.

Configure the service account credentials to use:

```
    $ export GOOGLE_APPLICATION_CREDENTIALS="~/datastore-user.cred.json"
```

Example using DatastoreDB() as read-only database explorer via command line:

```
    $ python3 -m data.datastore_db [<kind> [<id> [<propname>]]]
```

Example using DatastoreDB() as read-only database explorer in PyFilesystem2:

```
    from .data.datastore_db import DatastoreDB
    data_db = DatastoreDB()
    data_db.listdir("/")
```

Example using DatastoreFS() as filesystem in PyFilesystem2:

```
    from .data.datastore_fs import DatastoreFS
    data_fs = DatastoreFS("/")
    data_fs.listdir("/")
```

Example using DatastoreDAVProvider() as DAV provider in WsgiDAV:

```
    from wsgidav.wsgidav_app import WsgiDAVApp
    from .data.datastore_dav import DatastoreDAVProvider
    
    dav_provider = DatastoreDAVProvider()
    config = {"provider_mapping": {"/": dav_provider}}
    config["simple_dc"] = {"user_mapping": {"*": True}}  # allow anonymous access or use domain controller
    
    app = WsgiDAVApp(config)
    # run_wsgi_app(app)
```

### Try other combinations ###

You can also combine DatastoreDB() with FS2DAVProvider() to provide a browser/WebDAV interface to your Datastore entities - see try_db2dav.py.
Or try DatastoreDAVProvider() with DAVProvider2FS() as a slower alternative to DatastoreFS() - see try_dav2fs.py.
Or some other combination you can think of, like migrating from Datastore to Firestore via PyFilesystem2...

