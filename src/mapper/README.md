## PyFilesystem2 and WsgiDAV Building Blocks

You can now **swap PyFilesystem2 filesystems and WsgiDAV DAV providers** and use them in both environments:
  * [DAVProvider2FS](https://github.com/mikespub-org/mp-fs-wsgidav/blob/master/src/mapper/fs_from_dav_provider.py) for basic support of WsgiDAV DAV providers as filesystem for PyFilesystem2
  * [FS2DAVProvider](https://github.com/mikespub-org/mp-fs-wsgidav/blob/master/src/mapper/dav_provider_from_fs.py) for basic support of PyFilesystem2 filesystems as DAV provider for WsgiDAV

![Swap Diagram](https://github.com/mikespub-org/mp-fs-wsgidav/raw/master/src/static/diagram2.jpg)

A list of [custom PyFilesystem2 filesystems](https://www.pyfilesystem.org/page/index-of-filesystems/) is available [here](https://www.pyfilesystem.org/page/index-of-filesystems/), and
a list of [custom WsgiDAV DAV providers](https://wsgidav.readthedocs.io/en/latest/user_guide_custom_providers.html) is available [here](https://wsgidav.readthedocs.io/en/latest/user_guide_custom_providers.html).

### Use a PyFilesytem2 filesystem as DAV provider for WsgiDAV ###

Copy the [src/mapper/dav_provider_from_fs.py file](https://github.com/mikespub-org/mp-fs-wsgidav/raw/master/src/mapper/dav_provider_from_fs.py) to your project, and import FS2DAVProvider.

Example using FS2DAVProvider() as DAV provider in WsgiDAV:

```
    from wsgidav.wsgidav_app import WsgiDAVApp
    from .dav_provider_from_fs import FS2DAVProvider
    from fs.osfs import OSFS
    
    source_fs = OSFS("/tmp")
    dav_provider = FS2DAVProvider(source_fs)
    config = {"provider_mapping": {"/": dav_provider}}
    config["simple_dc"] = {"user_mapping": {"*": True}}  # allow anonymous access or use domain controller
    
    app = WsgiDAVApp(config)
    # run_wsgi_app(app)
```

### Use a WsgiDAV DAV provider as filesystem for PyFilesystem2 ###

Copy the [src/mapper/fs_from_dav_provider.py file](https://github.com/mikespub-org/mp-fs-wsgidav/raw/master/src/mapper/fs_from_dav_provider.py) to your project, and import DAVProvider2FS.

Example using DAVProvider2FS() as filesystem in PyFilesystem2:

```
    from .fs_from_dav_provider import DAVProvider2FS
    from wsgidav.fs_dav_provider import FilesystemProvider
    
    dav_provider = FilesystemProvider("/tmp")
    dav_fs = DAVProvider2FS(dav_provider)
    # dav_fs.environ["wsgidav.auth.user_name"] = "tester"
    # dav_fs.environ["wsgidav.auth.roles"] = ["admin"]
    dav_fs.listdir("/")
```

### Try other combinations ###

You can also combine DatastoreDB() or FirestoreDB() with FS2DAVProvider() to provide a browser/WebDAV interface to your Datastore entities or Firestore documents - see try_db2dav.py.
Or try DatastoreDAVProvider() with DAVProvider2FS() as a slower alternative to DatastoreFS() - see try_dav2fs.py.
Or some other combination you can think of, like migrating from Datastore to Firestore via PyFilesystem2...

