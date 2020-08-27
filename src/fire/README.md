## PyFilesystem2 and WsgiDAV Building Blocks for Google Cloud Firestore in native mode

  * Firestore DAV Provider for a virtual filesystem built on Google [Cloud Firestore in native mode](https://cloud.google.com/firestore/docs/) for WsgiDAV
  * [Firestore FS](https://github.com/mikespub-org/mp-fs-wsgidav/blob/master/src/fire/firestore_fs.py) for basic support of Google Cloud Firestore in native mode as filesystem for [PyFilestem2](https://docs.pyfilesystem.org/)
  * [Firestore DB](https://github.com/mikespub-org/mp-fs-wsgidav/blob/master/src/fire/firestore_db.py) for a read-only database explorer of Google Cloud Firestore in native mode with [PyFilestem2](https://docs.pyfilesystem.org/)

### Use the Firestore DAV provider, Firestore FS filesystem or Firestore DB explorer ###

If you want to use the Firestore DAV provider / FS filesystem / DB explorer yourself, you'll need to copy the [src/fire/](https://github.com/mikespub-org/mp-fs-wsgidav/tree/master/src/fire) directory to your project.

Configure the service account credentials to use:

```
    $ export GOOGLE_APPLICATION_CREDENTIALS="~/firestore-user.cred.json"
```

Example using Flask view functions as read-only database explorer via browser:

```
    $ python3 -m fire.views
```

Example using FirestoreDB() as read-only database explorer via command line:

```
    $ python3 -m fire.firestore_db [<coll> [<id> [<coll> [<id> [...]]]]]
    $ python3 -m fire.firestore_db <coll>[/<id>[/<coll>]] <id>[<propname>]
```

Example using FirestoreDB() as read-only database explorer in PyFilesystem2:

```
    from .fire.firestore_db import FirestoreDB
    fire_db = FirestoreDB()
    fire_db.listdir("/")
```

Example using FirestoreFS() as filesystem in PyFilesystem2:

```
    from .fire.firestore_fs import FirestoreFS
    fire_fs = FirestoreFS("/")
    fire_fs.listdir("/")
```

Example using FirestoreDAVProvider() as DAV provider in WsgiDAV:

```
    from wsgidav.wsgidav_app import WsgiDAVApp
    from .fire.firestore_dav import FirestoreDAVProvider
    
    dav_provider = FirestoreDAVProvider()
    config = {"provider_mapping": {"/": dav_provider}}
    config["simple_dc"] = {"user_mapping": {"*": True}}  # allow anonymous access or use domain controller
    
    app = WsgiDAVApp(config)
    # run_wsgi_app(app)
```

### Try other combinations ###

You can also combine FirestoreDB() with FS2DAVProvider() to provide a browser/WebDAV interface to your Firestore documents - see try_db2dav.py.

Or try FirestoreDAVProvider() with DAVProvider2FS() as a slower alternative to FirestoreFS() - see try_dav2fs.py.

Or some other combination you can think of, like migrating from Datastore to Firestore via PyFilesystem2...

