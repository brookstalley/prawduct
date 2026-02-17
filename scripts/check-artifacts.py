#!/usr/bin/env python3
"""
Check artifact files for proper frontmatter and structure.

Validates:
- Each .md file has YAML frontmatter
- Frontmatter includes required fields: artifact, version, depends_on, depended_on_by
- Artifact names match expected universal/shape-specific artifacts

Usage: python3 check-artifacts.py <path-to-artifacts-directory>
"""

from __future__ import annotations

import sys
import re
from pathlib import Path

def check_artifact_frontmatter(artifact_path):
    """Check if artifact has valid frontmatter."""

    try:
        with open(artifact_path, 'r') as f:
            content = f.read()
    except Exception as e:
        return False, f"Could not read file: {e}"

    # Check for YAML frontmatter (starts with ---)
    if not content.startswith('---\n'):
        return False, "Missing YAML frontmatter (should start with ---)"

    # Extract frontmatter
    parts = content.split('---\n', 2)
    if len(parts) < 3:
        return False, "Incomplete YAML frontmatter (missing closing ---)"

    frontmatter = parts[1]

    # Check required fields
    required_fields = ['artifact:', 'version:', 'depends_on:', 'depended_on_by:']
    missing_fields = []

    for field in required_fields:
        if field not in frontmatter:
            missing_fields.append(field.rstrip(':'))

    if missing_fields:
        return False, f"Missing required frontmatter fields: {', '.join(missing_fields)}"

    return True, "Valid frontmatter"

def check_artifacts(artifacts_dir):
    """Check all artifacts in directory."""

    artifacts_path = Path(artifacts_dir)

    if not artifacts_path.exists() or not artifacts_path.is_dir():
        print(f"✗ FAIL: Artifacts directory not found: {artifacts_dir}")
        return False

    # Find all .md and .yaml files
    artifact_files = list(artifacts_path.glob('*.md')) + list(artifacts_path.glob('*.yaml'))

    if not artifact_files:
        print(f"✗ FAIL: No artifact files found in {artifacts_dir}")
        return False

    failures = []

    for artifact_file in sorted(artifact_files):
        # Only check .md files for frontmatter (YAML files have different structure)
        if artifact_file.suffix == '.md':
            valid, message = check_artifact_frontmatter(artifact_file)
            if not valid:
                failures.append(f"{artifact_file.name}: {message}")

    # Check for minimum universal artifacts
    universal_artifacts = [
        'product-brief.md',
        'data-model.md',
        'security-model.md',
        'test-specifications.md',
        'nonfunctional-requirements.md',
        'operational-spec.md'
    ]

    # dependency-manifest can be .yaml or .md
    has_dependency_manifest = any(
        f.name in ['dependency-manifest.yaml', 'dependency-manifest.md']
        for f in artifact_files
    )

    if not has_dependency_manifest:
        failures.append("Missing universal artifact: dependency-manifest (expected .yaml or .md)")

    missing_universal = []
    for artifact_name in universal_artifacts:
        if not (artifacts_path / artifact_name).exists():
            missing_universal.append(artifact_name)

    if missing_universal:
        failures.append(f"Missing universal artifacts: {', '.join(missing_universal)}")

    # Report results
    print(f"Found {len(artifact_files)} artifact file(s)")

    if failures:
        print(f"✗ Artifact validation found {len(failures)} issue(s):")
        for failure in failures:
            print(f"  - {failure}")
        return False
    else:
        print("✓ All artifacts have valid structure")
        return True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 check-artifacts.py <path-to-artifacts-directory>")
        sys.exit(1)

    artifacts_dir = sys.argv[1]
    success = check_artifacts(artifacts_dir)
    sys.exit(0 if success else 1)
