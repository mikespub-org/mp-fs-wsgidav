#
# Copyright (c) 2019-2020 Mike's Pub, see https://github.com/mikespub-org
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

import os.path
import json


PAGE_SIZE = 10
COLL_CONFIG = {}
config_file = os.path.join(os.path.dirname(__file__), "config.json")
# with open(config_file, "w") as fp:
#     json.dump(COLL_CONFIG, fp, indent=2)
with open(config_file, "r") as fp:
    COLL_CONFIG = json.load(fp)


for coll in COLL_CONFIG:
    truncate_list = COLL_CONFIG[coll].get("truncate", [])
    truncate_list.extend(COLL_CONFIG[coll].get("pickled", []))
    truncate_list.extend(COLL_CONFIG[coll].get("image", []))
    if len(truncate_list) > 0:
        COLL_CONFIG[coll]["truncate_list"] = truncate_list
