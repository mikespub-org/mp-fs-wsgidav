# Mike's Pub - PyFilesystem2 and WsgiDAV Building Blocks

## Project Status ##
The master branch here provides the following building blocks for [WsgiDAV](https://wsgidav.readthedocs.io/) 3.0.x and Python 3.7+ with current Google Cloud services as back-end.
  * Datastore DAV Provider for a virtual filesystem built on Google [Cloud Firestore in Datastore mode](https://cloud.google.com/datastore/docs/)
  * Firebase Domain Controller to validate id tokens with Google Cloud [Identity Platform](https://cloud.google.com/identity-platform/docs/) (Firebase Authentication)
  * Cachelib Lock Manager to support in-memory locks using [cachelib](https://github.com/pallets/cachelib) (either memcache, redis or in-memory)
  * Property Manager partially integrated with the DAV Provider (?)
  * Firestore DAV Provider for a virtual filesystem built on Google [Cloud Firestore in native mode](https://cloud.google.com/firestore/docs/)

In addition, the following new filesystem providers are available for [PyFilestem2](https://docs.pyfilesystem.org/):
  * [Datastore FS](https://github.com/mikespub-org/mp-fs-wsgidav/blob/master/src/btfs/datastore_fs.py) for basic support of Google Cloud Firestore in Datastore mode as filesystem for [PyFilestem2](https://docs.pyfilesystem.org/)
  * [Datastore DB](https://github.com/mikespub-org/mp-fs-wsgidav/blob/master/src/btfs/datastore_db.py) for a read-only database explorer of Google Cloud Firestore in Datastore mode with [PyFilestem2](https://docs.pyfilesystem.org/)
  * Firestore FS for basic support of Google Cloud Firestore in native mode as filesystem for [PyFilestem2](https://docs.pyfilesystem.org/)
  * [Firestore DB](https://github.com/mikespub-org/mp-fs-wsgidav/blob/master/src/fire/firestore_db.py) for a read-only database explorer of Google Cloud Firestore in native mode with [PyFilestem2](https://docs.pyfilesystem.org/)

![Datastore Diagram](https://github.com/mikespub-org/mp-fs-wsgidav/raw/master/src/static/diagram.jpg)

And finally, you can now **swap PyFilesystem2 filesystems and WsgiDAV DAV providers** and use them in both environments:
  * [DAVProvider2FS](https://github.com/mikespub-org/mp-fs-wsgidav/blob/master/src/mapper/fs_from_dav_provider.py) for basic support of WsgiDAV DAV providers as filesystem for PyFilesystem2
  * [FS2DAVProvider](https://github.com/mikespub-org/mp-fs-wsgidav/blob/master/src/mapper/dav_provider_from_fs.py) for basic support of PyFilesystem2 filesystems as DAV provider for WsgiDAV

![Swap Diagram](https://github.com/mikespub-org/mp-fs-wsgidav/raw/master/src/static/diagram2.jpg)

A list of [custom PyFilesystem2 filesystems](https://www.pyfilesystem.org/page/index-of-filesystems/) is available [here](https://www.pyfilesystem.org/page/index-of-filesystems/), and
a list of [custom WsgiDAV DAV providers](https://wsgidav.readthedocs.io/en/latest/user_guide_custom_providers.html) is available [here](https://wsgidav.readthedocs.io/en/latest/user_guide_custom_providers.html).

The purpose here is **not** to provide a production-ready version for use on Google Cloud, but to experiment with various newer back-end services and explore the differences with older versions. And of course have fun while doing it :-)

## Installation ##

You can either clone the [public repo](https://github.com/mikespub-org/mp-fs-wsgidav):
```
    $ git clone https://github.com/mikespub-org/mp-fs-wsgidav.git
```

Or download the [zip file](https://github.com/mikespub-org/mp-fs-wsgidav/archive/master.zip):
```
    $ wget https://github.com/mikespub-org/mp-fs-wsgidav/archive/master.zip
```

## Usage ##

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
    dav_fs.listdir("/")
```

### Try out WsgiDAV on Google Cloud Platform ###

If you want to try out the Datastore or Firestore DAV provider, the Firebase domain controller etc., you can use this project and deploy it to App Engine.

1. Create a Google Cloud App Engine project
2. Create a Google Cloud Datastore or Firestore database in the same project
3. Install Google Cloud Identity Platform from the Marketplace and configure an identity provider (e.g. Google)
4. Rename the [src/app.yaml.template file](https://github.com/mikespub-org/mp-fs-wsgidav/raw/master/src/app.yaml.template) to app.yaml and update the FIREBASE_PROJECT_ID and FIREBASE_API_KEY environment variables
5. Deploy the project to App Engine with the gcloud tool
6. Go to the homepage of your newly deployed project, login using the /auth/ link and define yourself as admin using the /_admin link
7. Remove anonymous read-write access in the WsgiDAV config file and redeploy the project to App Engine

### Use the Datastore DAV provider or Datastore FS filesystem ###

If you want to use the Datastore DAV provider / FS filesystem yourself, you'll need to copy the [src/btfs/](https://github.com/mikespub-org/mp-fs-wsgidav/tree/master/src/btfs) directory to your project.

### Use the Firestore DAV provider or Firestore FS filesystem ###

If you want to use the Firestore DAV provider / FS filesystem yourself, you'll need to copy the [src/fire/](https://github.com/mikespub-org/mp-fs-wsgidav/tree/master/src/fire) directory to your project.

## Original CloudDAV Project ##

The original version of [CloudDAV](https://github.com/mar10/clouddav) from 2010 was meant to run on Google App Engine with Python 2.5 and [WsgiDAV](https://github.com/mar10/wsgidav) 0.5.0

It provided the following [architecture building blocks](https://wsgidav.readthedocs.io/en/latest/reference_guide_architecture.html):
  * Big Table DAV Provider for a virtual filesystem built on App Engine Datastore
  * Google Domain Controller to provide basic authentication (username/password) with Google Login
  * Memcache Lock Manager to support in-memory locks using App Engine Memcache
  * Property Manager partially integrated with the DAV Provider

The current version at https://github.com/mar10/clouddav and here in the [python27_base](https://github.com/mikespub-org/mp-fs-wsgidav/tree/python27_base) branch from 2019-12 was ported to "work" with Python 2.7 and WsgiDAV 3.0.x - it remains in alpha.

For more details see [History](https://github.com/mikespub-org/mp-fs-wsgidav/blob/master/HISTORY.md).
