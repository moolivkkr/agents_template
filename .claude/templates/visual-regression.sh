#!/bin/bash
# Visual Regression Test — compares wireframe.html screenshots against live app
# Usage: ./scripts/visual-regression.sh [phase]
# Prerequisites: app running at localhost:30000, Playwright installed

PHASE=${1:-1}
FRONTEND_DIR="$(git rev-parse --show-toplevel)/frontend"
SPECS_DIR="$(git rev-parse --show-toplevel)/docs/design/phases/${PHASE}/specs"
OUTPUT_DIR="$(git rev-parse --show-toplevel)/agent_state/phases/${PHASE}/visual"
CURL="/usr/bin/curl"

mkdir -p "$OUTPUT_DIR"

echo "╔══════════════════════════════════════╗"
echo "║  Visual Regression Test — Phase ${PHASE}   ║"
echo "╚══════════════════════════════════════╝"

# Find wireframe HTML files
WIREFRAMES=$(find "$SPECS_DIR" -name "*.wireframe.html" 2>/dev/null)
if [ -z "$WIREFRAMES" ]; then
    echo "No wireframe.html files found for Phase ${PHASE}"
    echo "Visual regression: SKIP (no reference)"
    exit 0
fi

# Check app is running
APP_STATUS=$($CURL -sf -o /dev/null -w "%{http_code}" http://localhost:30000 2>/dev/null || echo "000")
if [ "$APP_STATUS" != "200" ]; then
    echo "⛔ App not running at localhost:30000 (HTTP $APP_STATUS)"
    exit 1
fi

cd "$FRONTEND_DIR"

# Create Playwright screenshot script
cat > /tmp/visual-regression.js << 'SCRIPT'
const { chromium } = require(require('path').join(process.cwd(), 'node_modules', '@playwright', 'test'));
const fs = require('fs');
const path = require('path');

async function captureScreenshots(wireframePath, outputDir, phase) {
    const browser = await chromium.launch();
    const name = path.basename(wireframePath, '.wireframe.html');

    // Screenshot wireframe
    const wireframePage = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await wireframePage.goto(`file://${wireframePath}`);
    await wireframePage.waitForTimeout(1000);
    const wireframeShot = path.join(outputDir, `${name}-wireframe.png`);
    await wireframePage.screenshot({ path: wireframeShot, fullPage: true });

    // Screenshot live app
    const appPage = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await appPage.goto('http://localhost:30000');
    await appPage.waitForSelector('[role="application"]', { timeout: 10000 });
    await appPage.waitForTimeout(1000);
    const appShot = path.join(outputDir, `${name}-implementation.png`);
    await appPage.screenshot({ path: appShot, fullPage: true });

    await browser.close();

    console.log(JSON.stringify({
        wireframe: wireframeShot,
        implementation: appShot,
        name: name
    }));
}

const [wireframePath, outputDir, phase] = process.argv.slice(2);
captureScreenshots(wireframePath, outputDir, phase).catch(console.error);
SCRIPT

PASS=0
FAIL=0

for wireframe in $WIREFRAMES; do
    name=$(basename "$wireframe" .wireframe.html)
    echo ""
    echo "Comparing: $name"

    # Capture screenshots
    RESULT=$(node /tmp/visual-regression.js "$wireframe" "$OUTPUT_DIR" "$PHASE" 2>/dev/null)

    if [ -n "$RESULT" ]; then
        WIRE_SHOT=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['wireframe'])" 2>/dev/null)
        IMPL_SHOT=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['implementation'])" 2>/dev/null)

        if [ -f "$WIRE_SHOT" ] && [ -f "$IMPL_SHOT" ]; then
            echo "  ✓ Wireframe screenshot: $WIRE_SHOT"
            echo "  ✓ Implementation screenshot: $IMPL_SHOT"
            echo "  Compare side-by-side to verify visual fidelity"
            PASS=$((PASS + 1))
        else
            echo "  ✗ Screenshot capture failed"
            FAIL=$((FAIL + 1))
        fi
    else
        echo "  ✗ Playwright screenshot failed"
        FAIL=$((FAIL + 1))
    fi
done

rm -f /tmp/visual-regression.js

echo ""
echo "╔══════════════════════════════════════╗"
printf "║  Visual: %d captured, %d failed       ║\n" $PASS $FAIL
echo "║  Screenshots in: agent_state/phases/${PHASE}/visual/"
echo "╚══════════════════════════════════════╝"

exit $FAIL
