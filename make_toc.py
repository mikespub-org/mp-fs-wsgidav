#!/usr/bin/env python3
import re

output = "## Table of Contents ##\n"

with open("README.md") as fp:
    find = re.compile(r"^(##+)\s+(.+?)\s+#+$")
    for line in fp:
        m = find.match(line)
        if m:
            if m.group(2) == "Table of Contents":
                continue
            output += (
                "  " * (len(m.group(1)) - 1)
                + "* ["
                + m.group(2)
                + "](#"
                + m.group(2).lower().replace(",", "").replace(" ", "-")
                + ")\n"
            )
    output += "\n"

with open("toc.md", "w") as fp:
    fp.write(output)
