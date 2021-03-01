#!/usr/bin/env python3
#
# Use the Firestore FS as filesystem for FS2DAVProvider()
#


def create_app(source_fs, config=None):
    from wsgidav.wsgidav_app import WsgiDAVApp

    from mapper.dav_provider_from_fs import FS2DAVProvider

    dav_provider = FS2DAVProvider(source_fs)

    config = config or {}
    config["provider_mapping"] = {"/": dav_provider}
    # allow anonymous access or use domain controller
    config["simple_dc"] = {"user_mapping": {"*": True}}
    config["verbose"] = 3

    return WsgiDAVApp(config)


def run_wsgi_app(app, port=8080):
    # https://stackoverflow.com/questions/3889054/allow-hop-by-hop-headers-in-django-proxy-middleware
    import wsgiref.util
    from wsgiref.simple_server import make_server

    # apparently WsgiDAV sends Connection: close when you want to download an entity (hop-by-hop header)
    wsgiref.util._hoppish = {
        # 'connection':1,
        "keep-alive": 1,
        "proxy-authenticate": 1,
        "proxy-authorization": 1,
        "te": 1,
        "trailers": 1,
        "transfer-encoding": 1,
        "upgrade": 1,
    }.__contains__

    with make_server("", port, app) as httpd:
        print("Serving HTTP on port %s..." % port)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Goodbye...")


def main():
    from fire.firestore_fs import FirestoreFS

    # Open the PyFilesystem2 filesystem as source
    fire_fs = FirestoreFS("/")

    # Create the WsgiDAV app with the source FS filesystem
    app = create_app(fire_fs)

    # Run the WsgiDAV app with your preferred WSGI server
    run_wsgi_app(app)


if __name__ == "__main__":
    main()
