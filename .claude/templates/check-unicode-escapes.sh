#!/bin/bash
# Pre-commit check: no unicode escape sequences in JSX/TSX source files
# Catches \u00F7, \u2212, \u226A etc. that render as literal text instead of symbols
# Use literal characters: ÷ × − ≪ ≫ instead

REPO_ROOT=$(git rev-parse --show-toplevel)
ERRORS=0
while IFS= read -r file; do
    file="${REPO_ROOT}/${file}"
    # Skip test files, node_modules, dist
    case "$file" in *.test.*|*node_modules*|*dist*|*.config.*) continue ;; esac
    
    # Check for \uXXXX in label="..." or string props
    MATCHES=$(grep -n '\\u[0-9A-Fa-f]' "$file" 2>/dev/null | grep -v '// ' | grep -v '\* ')
    if [ -n "$MATCHES" ]; then
        echo "⛔ Unicode escape sequences found in $file:"
        echo "$MATCHES"
        echo "   Fix: replace \\uXXXX with the actual character (÷ × − ≪ ≫ etc.)"
        echo ""
        ERRORS=$((ERRORS + 1))
    fi
done < <(cd "$(git rev-parse --show-toplevel)" && git diff --cached --name-only --diff-filter=ACM -- '*.tsx' '*.ts')

if [ $ERRORS -gt 0 ]; then
    echo "⛔ $ERRORS file(s) contain unicode escape sequences."
    echo "   Use literal Unicode characters in UI strings."
    exit 1
fi
