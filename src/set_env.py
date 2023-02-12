import os
import yaml

# os.environ["USER_IS_ADMIN"] = "1"
# os.environ["USER_EMAIL"] = "test@example.com"

# os.environ["DATASTORE_DATASET"] = "None"
# os.environ["DATASTORE_EMULATOR_HOST"] = "localhost:8081"
# os.environ["DATASTORE_EMULATOR_HOST_PATH"] = "localhost:8081/datastore"
# os.environ["DATASTORE_HOST"] = "http://localhost:8081"
# os.environ["DATASTORE_PROJECT_ID"] = "None"
cred_file = "../datastore-admin.cred.json"
# cred_file = "../firestore-admin.cred.json"
if os.path.isfile(cred_file):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_file
    # os.environ["PROXY_PREFIX"] = "/test"

with open("app.yaml") as fp:
    info = yaml.safe_load(fp)
    if "env_variables" not in info:
        info["env_variables"] = {}
    for key, value in list(info["env_variables"].items()):
        # print(key, value)
        os.environ[key] = value
