# https://wsgidav.readthedocs.io/en/latest/development.html#test-test-test
print("""
    You can run the full set of tests from the WsgiDAV tests/ directory
    with the Firestore DAV Provider, simply by:
    1. copying this fire/ directory next to the tests/ directory
    2. adapting the tests/util.py file to use the right DAV provider:

    if provider is None:
        # provider = FilesystemProvider(share_path)
        from fire.firestore_dav import FirestoreDAVProvider
        provider = FirestoreDAVProvider(anon_role="editor")  # assign "editor" role to anon to support all tests

    Note: the litmus tests will also succeed, but they may take a long time...
""")
