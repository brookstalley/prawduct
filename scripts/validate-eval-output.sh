#!/bin/bash
# Mechanical validation for evaluation output
# Usage: ./scripts/validate-eval-output.sh /tmp/eval-{scenario}/ {scenario-name}
#
# Checks:
# 1. project-state.yaml schema compliance
# 2. Artifact presence and frontmatter structure
# 3. Observation file exists in framework repo
#
# Exit codes:
# 0 = all checks pass
# 1 = validation failures found

set -e

PROJECT_DIR="$1"
SCENARIO_NAME="$2"
FRAMEWORK_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -z "$PROJECT_DIR" ] || [ -z "$SCENARIO_NAME" ]; then
    echo "Usage: $0 <project-directory> <scenario-name>"
    echo "Example: $0 /tmp/eval-background-data-pipeline background-data-pipeline"
    exit 1
fi

if [ ! -d "$PROJECT_DIR" ]; then
    echo "ERROR: Project directory does not exist: $PROJECT_DIR"
    exit 1
fi

echo "=== Mechanical Validation for $SCENARIO_NAME ==="
echo "Project directory: $PROJECT_DIR"
echo "Framework directory: $FRAMEWORK_DIR"
echo ""

# Track failures
FAILURES=0

# Check 1: project-state.yaml exists
echo "[1/5] Checking project-state.yaml exists..."
if [ ! -f "$PROJECT_DIR/project-state.yaml" ]; then
    echo "  ✗ FAIL: project-state.yaml not found"
    FAILURES=$((FAILURES + 1))
else
    echo "  ✓ PASS: project-state.yaml exists"
fi

# Check 2: project-state.yaml schema validation
echo "[2/5] Validating project-state.yaml schema..."
if command -v python3 &> /dev/null; then
    if [ -f "$FRAMEWORK_DIR/scripts/validate-schema.py" ]; then
        if python3 "$FRAMEWORK_DIR/scripts/validate-schema.py" "$PROJECT_DIR/project-state.yaml"; then
            echo "  ✓ PASS: Schema validation passed"
        else
            echo "  ✗ FAIL: Schema validation failed"
            FAILURES=$((FAILURES + 1))
        fi
    else
        echo "  ⊘ SKIP: validate-schema.py not found"
    fi
else
    echo "  ⊘ SKIP: Python 3 not available"
fi

# Check 3: Artifacts directory exists
echo "[3/5] Checking artifacts directory..."
if [ ! -d "$PROJECT_DIR/artifacts" ]; then
    echo "  ✗ FAIL: artifacts/ directory not found"
    FAILURES=$((FAILURES + 1))
else
    ARTIFACT_COUNT=$(find "$PROJECT_DIR/artifacts" -type f -name "*.md" -o -name "*.yaml" | wc -l | tr -d ' ')
    echo "  ✓ PASS: artifacts/ directory exists with $ARTIFACT_COUNT files"

    # Check for minimum artifacts (7 universal required)
    if [ "$ARTIFACT_COUNT" -lt 7 ]; then
        echo "  ⚠ WARNING: Expected at least 7 universal artifacts, found $ARTIFACT_COUNT"
    fi
fi

# Check 4: Artifact frontmatter validation
echo "[4/5] Validating artifact frontmatter..."
if command -v python3 &> /dev/null && [ -f "$FRAMEWORK_DIR/scripts/check-artifacts.py" ]; then
    if python3 "$FRAMEWORK_DIR/scripts/check-artifacts.py" "$PROJECT_DIR/artifacts"; then
        echo "  ✓ PASS: Artifact frontmatter validation passed"
    else
        echo "  ✗ FAIL: Artifact frontmatter validation failed"
        FAILURES=$((FAILURES + 1))
    fi
else
    echo "  ⊘ SKIP: Python 3 or check-artifacts.py not available"
fi

# Check 5: Observation file exists (CRITICAL)
echo "[5/5] Checking observation file exists..."
DATE=$(date +%Y-%m-%d)
OBSERVATION_FILE="$FRAMEWORK_DIR/framework-observations/${DATE}-${SCENARIO_NAME}-eval.yaml"

if [ -f "$OBSERVATION_FILE" ]; then
    echo "  ✓ PASS: Observation file exists: $OBSERVATION_FILE"

    # Check observation file has content (not empty)
    if [ ! -s "$OBSERVATION_FILE" ]; then
        echo "  ⚠ WARNING: Observation file is empty"
    fi
else
    echo "  ✗ CRITICAL FAIL: Observation file not found: $OBSERVATION_FILE"
    echo "  This indicates the observation capture system failed during eval."
    echo "  Manual action required:"
    echo "    1. Create observation file documenting the capture failure"
    echo "    2. Investigate why automatic capture didn't work"
    echo "    3. Mark as severity: blocking, type: process_friction"
    FAILURES=$((FAILURES + 1))
fi

echo ""
echo "=== Validation Summary ==="
if [ $FAILURES -eq 0 ]; then
    echo "✓ All mechanical validations PASSED"
    exit 0
else
    echo "✗ $FAILURES validation failure(s) found"
    echo "Review failures above before proceeding with rubric evaluation."
    exit 1
fi
