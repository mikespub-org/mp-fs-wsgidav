#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

import json
import os.path

# from btfs import sessions
# from btfs.auth import AuthorizedUser
from .model import Chunk, Dir, File, Path

PAGE_SIZE = 10
KNOWN_MODELS = {
    "Path": Path,
    "Dir": Dir,
    "File": File,
    "Chunk": Chunk,
    # "AuthorizedUser": AuthorizedUser,
    # "AuthSession": sessions.AuthSession,
}
LIST_CONFIG = {}
config_file = os.path.join(os.path.dirname(__file__), "config.json")
# with open(config_file, "w") as fp:
#     json.dump(LIST_CONFIG, fp, indent=2)
with open(config_file) as fp:
    LIST_CONFIG = json.load(fp)


for kind in LIST_CONFIG:
    truncate_list = LIST_CONFIG[kind].get("truncate", [])
    truncate_list.extend(LIST_CONFIG[kind].get("pickled", []))
    truncate_list.extend(LIST_CONFIG[kind].get("image", []))
    if len(truncate_list) > 0:
        LIST_CONFIG[kind]["truncate_list"] = truncate_list


def get_list_config(kind, what, default=[]):
    # if "/" in kind:
    #     kind = kind.split("/")[-1]
    if kind in LIST_CONFIG:
        return LIST_CONFIG[kind].get(what, default)
    return default
