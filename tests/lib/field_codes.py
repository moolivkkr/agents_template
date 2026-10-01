#!/usr/bin/env python3
"""field_codes.py — every lower_snake details[].code a skill sample puts on the wire is in the closed set
in api/response-envelope.md (§`code` values). A validator's own vocabulary (too_small, min_value, Size,
length, …) must be mapped onto that set before it reaches a client.

  python3 tests/lib/field_codes.py [--lang go|python|typescript|rust|java|ui] [--root DIR]
Exit 1 when a sample uses a code outside the set. It reads codes in wire-building contexts only:
`code: "x"` / `"code": "x"` / `code="x"`, validation-error constructors, (code, "message") tables, and
`: "x"` for the known non-catalog validator words.
"""
import argparse, glob, os, re, sys

ap = argparse.ArgumentParser()
ap.add_argument("--lang")
ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
a = ap.parse_args()
ROOT = os.path.abspath(a.root)

env = open(os.path.join(ROOT, ".claude/skills/api/response-envelope.md"), encoding="utf-8").read()
CATALOG = set(re.findall(r"^\s*\|\s*`([a-z_]+)`(?:\s*/\s*`([a-z_]+)`)?\s*\|", env, re.M) and
              [c for pair in re.findall(r"^\s*\|\s*`([a-z_]+)`(?:\s*/\s*`([a-z_]+)`)?\s*\|", env, re.M) for c in pair if c])
# Third-party vocabularies the samples mock or receive, never send as their own field codes.
EXTERNAL = {"card_declined"}  # Stripe error code in testing/external-service-mocks.md

PATS = [
    re.compile(r'''\b[Cc]ode["']?\s*[:=]\s*["']([a-z][a-z0-9_]*)["']'''),  # lower_snake only: UPPER_SNAKE is error.code
    re.compile(r'''(?:[Vv]alidation(?:Error|FailedError|Exception)?|NewValidationError|[Ff]ield_?[Ee]rror(?:::new)?|validation_error)\s*\(\s*[^,()]+,\s*["']([a-z][a-z0-9_]*)["']'''),
    re.compile(r'''(?:^|[(=>]|Entry\()\s*["']([a-z][a-z0-9_]*)["']\s*,\s*["'](?:This |Enter |Choose |Select |That )'''),
    re.compile(r'''(?:[:?]|=>)\s*["'](invalid_reference|too_small|too_big|too_large|min_value|max_value|min_length|max_length|invalid_length|invalid_choice|invalid|taken|already_taken|missing|min|max)["']\s*[,;)}\]\n]'''),
]
SKIP_LINE = re.compile(r"ConflictException\(|NotFoundException\(|invalidArgument\(|case\s+[\"']")
NON_CODE = {"sql", "bash", "sh", "shell", "yaml", "yml", "text", "markdown", "md", "http", "ini", "toml", "dockerfile", "proto", "protobuf", "hcl", "ngql", "xml", "gitignore", "dockerignore", "scala", "groovy", "kotlin", "css", "html", "graphql"}
LANGS = {"go": ("go",), "python": ("python", "py"), "typescript": ("typescript", "ts", "tsx", "javascript", "js", "jsx"),
         "rust": ("rust", "rs"), "java": ("java",), "ui": ("tsx", "ts", "typescript", "vue", "svelte", "javascript", "jsx", "json")}


def blocks(text):
    fence = None
    for i, line in enumerate(text.split("\n"), 1):
        m = re.match(r"^\s*(`{3,})(\S*)", line)
        if fence is None and m:
            fence, lang = m.group(1), m.group(2).lower()
            continue
        if fence is not None and re.match(r"^\s*" + fence + r"\s*$", line):
            fence = None
            continue
        if fence is not None:
            yield i, lang, line


bad = set()
files = glob.glob(os.path.join(ROOT, ".claude/skills/**/*.md"), recursive=True) + glob.glob(os.path.join(ROOT, ".claude/agents/templates/*.tmpl"))
for f in sorted(files):
    rel = os.path.relpath(f, ROOT)
    for i, lang, line in blocks(open(f, encoding="utf-8").read()):
        if lang in NON_CODE or not lang:
            continue
        if a.lang == "ui":  # UI = the files UI agents copy from, whatever the fence language
            if not re.match(r"\.claude/(skills/(ui/|frameworks/(react|nextjs|vue|svelte|angular|tanstack-query|react-native)|testing/(msw|playwright|react-native-testing-library|detox|appium-mobile))|agents/templates/(ui_|mobile_))", rel):
                continue
        elif a.lang and lang not in LANGS[a.lang]:
            continue
        s = line.strip()
        if s.startswith(("//", "#", "*", "--", "/*")) or SKIP_LINE.search(line):
            continue
        for p in PATS:
            for m in p.finditer(line):
                c = m.group(1)
                if c not in CATALOG and c not in EXTERNAL:
                    bad.add(f"{rel}:{i}: {c!r} not in the details[].code set — {s[:100]}")
for b in sorted(bad):
    print(b)
print(f"field_codes: {len(bad)} code(s) outside {{{', '.join(sorted(CATALOG))}}}", file=sys.stderr)
sys.exit(1 if bad else 0)
