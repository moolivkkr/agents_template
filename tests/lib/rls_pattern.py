#!/usr/bin/env python3
"""rls_pattern.py — print the archetype RLS block (decision D-001) exactly as the skill documents it.

The block is the ```sql fence under "## Row-Level Security" in .claude/skills/databases/postgres.md that
defines app_grant_migrator(): the helper every first migration creates, then a tenant table's ENABLE +
FORCE ROW LEVEL SECURITY, tenant policy and migrator-only policy. tests/eks-db-roles.sh and
tests/k8s-db-roles.sh run this text against real PostgreSQL 17, so the tests prove the documented SQL,
not a copy of it. Exit 1 if the block is missing or no longer defines the helper.
"""
import pathlib
import re
import sys

DOC = pathlib.Path(__file__).resolve().parents[2] / ".claude/skills/databases/postgres.md"


def rls_block(text: str) -> str:
    section = text.split("## Row-Level Security", 1)
    if len(section) != 2:
        raise SystemExit(f"rls_pattern: no '## Row-Level Security' section in {DOC}")
    for block in re.findall(r"```sql\n(.*?)```", section[1].split("\n## ", 1)[0], re.S):
        if "FUNCTION app_grant_migrator(tbl regclass)" in block and "SELECT app_grant_migrator(" in block:
            return block
    raise SystemExit(f"rls_pattern: the Row-Level Security section of {DOC} has no sql block defining and calling app_grant_migrator()")


if __name__ == "__main__":
    sys.stdout.write(rls_block(DOC.read_text()))
