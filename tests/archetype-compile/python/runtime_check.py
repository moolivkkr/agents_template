"""Import a unit's modules (and run its smoke script) in a clean interpreter; write a JSON report.

Usage: runtime_check.py <unit_dir> <spec-json> <result-path>
spec = {"imports": [module, ...], "smoke": "<python source>"}
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import traceback
import warnings


def frames(exc: BaseException) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    seen: set[int] = set()
    e: BaseException | None = exc
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        for fr in traceback.extract_tb(e.__traceback__):
            out.append({"file": fr.filename, "line": fr.lineno or 0, "code": (fr.line or "").strip()})
        e = e.__cause__ or e.__context__
    return out


def main() -> None:
    unit_dir, spec_json, result_path = sys.argv[1], sys.argv[2], sys.argv[3]
    spec = json.loads(spec_json)
    os.chdir(unit_dir)
    sys.path.insert(0, unit_dir)
    report: dict[str, list[object]] = {"errors": [], "warnings": [], "imported": []}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for mod in spec["imports"]:
            try:
                importlib.import_module(mod)
                report["imported"].append(mod)
            except BaseException as exc:  # noqa: BLE001 — every failure is reported
                report["errors"].append(
                    {"what": f"import {mod}", "type": type(exc).__name__, "message": str(exc)[:500], "frames": frames(exc)}
                )
        if spec.get("smoke") and not report["errors"]:
            try:
                exec(compile(spec["smoke"], "<smoke>", "exec"), {"__name__": "__smoke__"})
            except BaseException as exc:  # noqa: BLE001
                report["errors"].append(
                    {"what": "smoke", "type": type(exc).__name__, "message": str(exc)[:500], "frames": frames(exc)}
                )
    for w in caught:
        report["warnings"].append(
            {"category": w.category.__name__, "message": str(w.message)[:300], "filename": w.filename, "lineno": w.lineno}
        )
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(report, f)


if __name__ == "__main__":
    main()
