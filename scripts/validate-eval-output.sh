#!/bin/bash
# Mechanical validation for evaluation output
# Usage: ./scripts/validate-eval-output.sh /tmp/eval-{scenario}/ {scenario-name}
#
# Checks:
# 1. project-state.yaml exists
# 2. project-state.yaml schema compliance
# 3. Artifacts directory exists with minimum files
# 4. Artifact frontmatter validation
# 5. Framework reflection entries in change_log (Tier 1 BLOCKING)
# 6. Observation file exists (Tier 2 INFO — only for substantive findings)
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
echo "[1/6] Checking project-state.yaml exists..."
if [ ! -f "$PROJECT_DIR/project-state.yaml" ]; then
    echo "  ✗ FAIL: project-state.yaml not found"
    FAILURES=$((FAILURES + 1))
else
    echo "  ✓ PASS: project-state.yaml exists"
fi

# Check 2: project-state.yaml schema validation
echo "[2/6] Validating project-state.yaml schema..."
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
echo "[3/6] Checking artifacts directory..."
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
echo "[4/6] Validating artifact frontmatter..."
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

# Check 5: Framework reflection in change_log (Tier 1 BLOCKING)
echo "[5/6] Checking change_log for framework reflection entries..."
if [ -f "$PROJECT_DIR/project-state.yaml" ]; then
    REFLECTION_COUNT=$(grep -c "Framework reflection" "$PROJECT_DIR/project-state.yaml" 2>/dev/null || echo 0)
    if [ "$REFLECTION_COUNT" -gt 0 ]; then
        echo "  ✓ PASS: Found $REFLECTION_COUNT framework reflection entries in change_log"
    else
        echo "  ✗ FAIL: No 'Framework reflection' entries found in change_log"
        echo "  The Orchestrator must record a reflection at every stage transition."
        FAILURES=$((FAILURES + 1))
    fi
else
    echo "  ⊘ SKIP: project-state.yaml not available"
fi

# Check 6: Observation file (Tier 2 WARNING — only required if substantive findings exist)
echo "[6/6] Checking for observation file..."
DATE=$(date +%Y-%m-%d)
OBSERVATION_FILE="$FRAMEWORK_DIR/framework-observations/${DATE}-${SCENARIO_NAME}-eval.yaml"

if [ -f "$OBSERVATION_FILE" ]; then
    echo "  ✓ PASS: Observation file exists: $OBSERVATION_FILE"

    # Check observation file has content (not empty)
    if [ ! -s "$OBSERVATION_FILE" ]; then
        echo "  ⚠ WARNING: Observation file is empty"
    fi
else
    echo "  ⊘ INFO: No observation file at $OBSERVATION_FILE"
    echo "  (Observation files are only required for substantive findings.)"
    echo "  If the eval revealed framework issues, create one manually."
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
