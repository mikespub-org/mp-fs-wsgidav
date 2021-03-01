#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

import json
import os.path

PAGE_SIZE = 10
LIST_CONFIG = {}
config_file = os.path.join(os.path.dirname(__file__), "config.json")
# with open(config_file, "w") as fp:
#     json.dump(LIST_CONFIG, fp, indent=2)
with open(config_file) as fp:
    LIST_CONFIG = json.load(fp)


for coll in LIST_CONFIG:
    truncate_list = LIST_CONFIG[coll].get("truncate", [])
    truncate_list.extend(LIST_CONFIG[coll].get("pickled", []))
    truncate_list.extend(LIST_CONFIG[coll].get("image", []))
    if len(truncate_list) > 0:
        LIST_CONFIG[coll]["truncate_list"] = truncate_list


def get_list_config(coll_id, what, default=[]):
    if "/" in coll_id:
        coll_id = coll_id.split("/")[-1]
    if coll_id in LIST_CONFIG:
        return LIST_CONFIG[coll_id].get(what, default)
    return default
