#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

# from btfs import sessions
# from btfs.auth import AuthorizedUser
from .model import Chunk, Dir, File, Path
import os.path
import json


PAGE_SIZE = 10
KNOWN_MODELS = {
    "Path": Path,
    "Dir": Dir,
    "File": File,
    "Chunk": Chunk,
    # "AuthorizedUser": AuthorizedUser,
    # "AuthSession": sessions.AuthSession,
}
KIND_CONFIG = {}
config_file = os.path.join(os.path.dirname(__file__), "config.json")
# with open(config_file, "w") as fp:
#     json.dump(KIND_CONFIG, fp, indent=2)
with open(config_file, "r") as fp:
    KIND_CONFIG = json.load(fp)


for kind in KIND_CONFIG:
    truncate_list = KIND_CONFIG[kind].get("truncate", [])
    truncate_list.extend(KIND_CONFIG[kind].get("pickled", []))
    truncate_list.extend(KIND_CONFIG[kind].get("image", []))
    if len(truncate_list) > 0:
        KIND_CONFIG[kind]["truncate_list"] = truncate_list
