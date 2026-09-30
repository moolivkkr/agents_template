#!/usr/bin/env python3
"""Copy the ```protobuf blocks of grpc-pattern.md into proto/ so buf can compile them.

The doc's common.proto uses Widget, WidgetStatus and google.protobuf.Timestamp without importing
them, which no protobuf compiler accepts; the missing imports are added here (harness-side only)
and reported as a doc finding.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.join(HERE, "..", "..", "..", "..", ".claude", "skills", "backend", "archetypes", "grpc-pattern.md")
MISSING_IMPORTS = {
    "yourapp/v1/common.proto": ['import "google/protobuf/timestamp.proto";', 'import "yourapp/v1/widget.proto";'],
}

text = open(DOC, encoding="utf-8").read()
for body in re.findall(r"```protobuf\n(.*?)\n```", text, re.S):
    m = re.match(r"//\s*proto/(\S+\.proto)", body)
    if not m:
        continue  # e.g. the grpc.health.v1 excerpt — not part of the widget API
    rel = m.group(1)
    extra = MISSING_IMPORTS.get(rel)
    if extra:
        body = body.replace("package yourapp.v1;\n", "package yourapp.v1;\n\n" + "\n".join(extra) + "\n", 1)
    out = os.path.join(HERE, "proto", rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(body + "\n")
    print("wrote", os.path.relpath(out, HERE))
