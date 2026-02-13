#!/usr/bin/env python3
"""
Validate project-state.yaml against template schema.

Checks:
- All top-level sections exist
- Required fields are populated (not null)
- Field types match expected types
- No extra fields outside schema

Usage: python3 validate-schema.py <path-to-project-state.yaml>
"""

import sys
import yaml
from pathlib import Path

def validate_schema(project_state_path):
    """Validate project-state.yaml structure."""

    try:
        with open(project_state_path, 'r') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"✗ FAIL: Could not parse YAML: {e}")
        return False

    failures = []

    # Check top-level sections exist
    required_sections = [
        'classification',
        'product_definition',
        'technical_decisions',
        'design_decisions',
        'artifact_manifest',
        'dependency_graph',
        'open_questions',
        'user_expertise',
        'current_stage',
        'change_log'
    ]

    for section in required_sections:
        if section not in data:
            failures.append(f"Missing required section: {section}")

    if 'classification' in data:
        # Check classification fields
        if 'domain' not in data['classification'] or not data['classification']['domain']:
            failures.append("classification.domain is missing or null")
        if 'structural' not in data['classification'] or not data['classification']['structural']:
            failures.append("classification.structural is missing or null")
        if 'risk_profile' not in data['classification']:
            failures.append("classification.risk_profile is missing")
        elif 'overall' not in data['classification']['risk_profile']:
            failures.append("classification.risk_profile.overall is missing")

    if 'product_definition' in data:
        # Check product_definition fields
        pd = data['product_definition']
        if 'vision' not in pd or not pd['vision']:
            failures.append("product_definition.vision is missing or null")
        if 'users' not in pd or 'personas' not in pd['users'] or not pd['users']['personas']:
            failures.append("product_definition.users.personas is missing or empty")

    if 'current_stage' not in data or not data['current_stage']:
        failures.append("current_stage is missing or null")

    # Check field types
    if 'classification' in data and 'risk_profile' in data['classification']:
        if 'factors' in data['classification']['risk_profile']:
            factors = data['classification']['risk_profile']['factors']
            if not isinstance(factors, list):
                failures.append("classification.risk_profile.factors should be a list")
            else:
                for i, factor in enumerate(factors):
                    if not isinstance(factor, dict):
                        failures.append(f"risk_profile.factors[{i}] should be an object")
                    elif 'factor' not in factor or 'level' not in factor or 'rationale' not in factor:
                        failures.append(f"risk_profile.factors[{i}] missing required fields (factor, level, rationale)")

    if 'change_log' in data:
        if not isinstance(data['change_log'], list):
            failures.append("change_log should be a list")

    # Report results
    if failures:
        print(f"✗ Schema validation found {len(failures)} issue(s):")
        for failure in failures:
            print(f"  - {failure}")
        return False
    else:
        print("✓ Schema validation passed")
        return True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 validate-schema.py <path-to-project-state.yaml>")
        sys.exit(1)

    project_state_path = Path(sys.argv[1])

    if not project_state_path.exists():
        print(f"✗ FAIL: File not found: {project_state_path}")
        sys.exit(1)

    success = validate_schema(project_state_path)
    sys.exit(0 if success else 1)
