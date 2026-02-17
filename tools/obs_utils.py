"""
obs_utils.py — Shared observation utilities for framework tools.

Used by session-health-check.sh, observation-analysis.sh, and
update-observation-status.sh to eliminate duplicated YAML parsing,
file scanning, threshold logic, and pattern detection.
"""

from __future__ import annotations

import os
import glob
import yaml

# Tiered threshold categories
META_TYPES = frozenset({
    'process_friction', 'rubric_issue', 'skill_quality',
    'external_practice_drift', 'documentation_drift', 'structural_critique'
})
BUILD_TYPES = frozenset({
    'artifact_insufficiency', 'spec_ambiguity', 'deployment_friction',
    'critic_gap', 'integration_friction'
})

TERMINAL_STATUSES = frozenset({'acted_on', 'archived'})


def get_threshold(obs_type):
    if obs_type in META_TYPES:
        return 2
    elif obs_type in BUILD_TYPES:
        return 3
    return 4


def get_tier(obs_type):
    if obs_type in META_TYPES:
        return 'meta'
    if obs_type in BUILD_TYPES:
        return 'build'
    return 'product'


def find_observation_files(obs_dir):
    """Return sorted list of observation YAML files (excludes schema.yaml)."""
    files = sorted(glob.glob(os.path.join(obs_dir, '*.yaml')))
    return [f for f in files if not f.endswith('schema.yaml')]


def parse_observations(files):
    """Parse all observations from a list of YAML files.

    Returns list of dicts, each with keys from the observation entry
    plus '_file' (basename) and '_skills' (from parent document).
    """
    all_obs = []
    for f in files:
        try:
            with open(f) as fh:
                for data in yaml.safe_load_all(fh):
                    if not data or 'observations' not in data:
                        continue
                    skills = data.get('skills_affected', [])
                    timestamp = data.get('timestamp', '')
                    for obs in data.get('observations', []):
                        obs['_file'] = os.path.basename(f)
                        obs['_skills'] = skills
                        obs['_timestamp'] = timestamp
                        all_obs.append(obs)
        except Exception:
            continue
    return all_obs


def is_active(obs):
    """True if observation is not in a terminal status."""
    return obs.get('status', 'noted') not in TERMINAL_STATUSES


def group_by_type(observations, active_only=True):
    """Group observations by type. Returns dict of type -> list of obs."""
    from collections import defaultdict
    groups = defaultdict(list)
    for obs in observations:
        if active_only and not is_active(obs):
            continue
        groups[obs.get('type', 'unknown')].append(obs)
    return dict(groups)


def detect_patterns(observations):
    """Find observation types where active count >= tiered threshold.

    Returns list of dicts with: type, active_count, total_count, threshold,
    tier, skills, actions.
    """
    active_groups = group_by_type(observations, active_only=True)
    all_groups = group_by_type(observations, active_only=False)

    patterns = []
    for obs_type, active_obs in sorted(active_groups.items()):
        threshold = get_threshold(obs_type)
        if len(active_obs) >= threshold:
            skills = set()
            actions = []
            for obs in active_obs:
                if obs.get('proposed_action'):
                    actions.append(obs['proposed_action'])
                for s in obs.get('_skills', []):
                    skills.add(s)
            patterns.append({
                'type': obs_type,
                'active_count': len(active_obs),
                'total_count': len(all_groups.get(obs_type, [])),
                'threshold': threshold,
                'tier': get_tier(obs_type),
                'skills': sorted(skills),
                'actions': actions,
            })
    return patterns


def all_terminal(filepath):
    """Check if all observations in a file are in terminal status."""
    try:
        with open(filepath) as f:
            for doc in yaml.safe_load_all(f):
                if not doc or 'observations' not in doc:
                    continue
                for obs in doc.get('observations', []):
                    if is_active(obs):
                        return False
        return True
    except Exception:
        return False


def find_archivable(obs_dir):
    """Return list of observation files where all observations are terminal."""
    return [f for f in find_observation_files(obs_dir) if all_terminal(f)]
