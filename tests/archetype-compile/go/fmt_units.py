#!/usr/bin/env python3
"""Rewrite units.json in its canonical layout: one line per file entry and per stub, the rest
indented. Run after editing units.json by hand or by script; the content is unchanged."""
import json
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "units.json")


def dump(v, ind=0):
    pad = "  " * ind
    if isinstance(v, dict):
        if "path" in v:  # a file entry: one line
            return json.dumps(v, ensure_ascii=False)
        items = [f"{pad}  {json.dumps(k, ensure_ascii=False)}: {dump(x, ind + 1)}" for k, x in v.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(v, list):
        if all(not isinstance(x, (dict, list)) for x in v) and len(json.dumps(v, ensure_ascii=False)) < 90:
            return json.dumps(v, ensure_ascii=False)
        items = [f"{pad}  {dump(x, ind + 1)}" for x in v]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    return json.dumps(v, ensure_ascii=False)


def main(mutate=None):
    cfg = json.load(open(P, encoding="utf-8"))
    if mutate:
        mutate(cfg)
    text = dump(cfg) + "\n"
    assert json.loads(text) == cfg
    open(P, "w", encoding="utf-8").write(text)


if __name__ == "__main__":
    main()
