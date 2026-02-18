#!/usr/bin/env python3
"""
compact-project-state.py — Mechanical compaction of growing project-state.yaml sections.

Implements the LIFECYCLE rules defined in templates/project-state.yaml:
  - change_log: >10 entries → keep 10 most recent + summary block
  - build_plan.chunks: all complete → compact to {id, name, status}
  - build_state.reviews: all findings resolved/deferred → compact to {chunk_id, summary, deferred_items}
  - review_findings.entries: resolved → compact to {stage, lens, summary, deferred_count}
  - iteration_state.feedback_cycles: >10 completed → compact completed to {feedback (first sentence), classification, status}

Uses section-based rewriting to preserve YAML comments (PyYAML round-trip drops them).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import date

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip3 install pyyaml", file=sys.stderr)
    sys.exit(1)


def parse_full_state(content):
    """Parse the entire YAML content for structured access."""
    return yaml.safe_load(content) or {}


def first_sentence(text):
    """Extract first sentence from a string."""
    if not text:
        return ""
    text = str(text).strip()
    match = re.match(r'^(.*?[.!?])(?:\s|$)', text)
    if match:
        return match.group(1)
    if len(text) > 80:
        return text[:77] + "..."
    return text


# --- Section extraction and replacement ---

def find_section_bounds(lines, section_key, parent_key=None):
    """Find the start and end line indices for a YAML section.

    Returns (start, end) where start is the key line and end is one past
    the last content line, or None if not found.
    """
    start = None
    key_indent = None

    if parent_key:
        parent_line = None
        parent_indent = None
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith(f"{parent_key}:"):
                indent = len(line) - len(stripped)
                parent_line = i
                parent_indent = indent
                break
        if parent_line is None:
            return None

        for i in range(parent_line + 1, len(lines)):
            stripped = lines[i].lstrip()
            if not stripped or stripped.startswith('#'):
                continue
            indent = len(lines[i]) - len(stripped)
            if indent <= parent_indent and stripped and not stripped.startswith('#'):
                break
            if stripped.startswith(f"{section_key}:"):
                start = i
                key_indent = indent
                break
    else:
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith(f"{section_key}:"):
                indent = len(line) - len(stripped)
                if indent == 0:
                    start = i
                    key_indent = 0
                    break

    if start is None:
        return None

    # Check for inline content (e.g., "key: []")
    key_line = lines[start]
    after_colon = key_line.split(':', 1)[1].strip() if ':' in key_line else ''
    if after_colon and not after_colon.startswith('#'):
        return (start, start + 1)

    # Find end: next mapping key at same or lesser indent.
    # List items (lines starting with '- ') at the key's indent level are content
    # of this section (yaml.dump places them at the same indent as the key).
    end = start + 1
    for i in range(start + 1, len(lines)):
        stripped = lines[i].lstrip()
        if not stripped or stripped.startswith('#'):
            end = i + 1
            continue
        indent = len(lines[i]) - len(stripped)
        if indent < key_indent:
            break
        if indent == key_indent and not stripped.startswith('- '):
            break
        end = i + 1

    return (start, end)


def replace_section_content(lines, bounds, key_line, new_yaml_content):
    """Replace section content, preserving LIFECYCLE comments.

    Returns a new lines list with each replacement line as a separate element
    (critical for subsequent find_section_bounds calls to work correctly).
    """
    start, end = bounds

    lifecycle_comments = []
    in_lifecycle_block = False
    for i in range(start, min(end, len(lines))):
        stripped = lines[i].strip()
        if 'LIFECYCLE' in stripped and stripped.startswith('#'):
            in_lifecycle_block = True
            lifecycle_comments.append(lines[i].rstrip() + '\n')
        elif in_lifecycle_block and stripped.startswith('#'):
            lifecycle_comments.append(lines[i].rstrip() + '\n')
        else:
            in_lifecycle_block = False

    replacement = [key_line + '\n']
    for lc in lifecycle_comments:
        replacement.append(lc)

    if new_yaml_content is not None:
        if not new_yaml_content.endswith('\n'):
            new_yaml_content += '\n'
        # Split into individual lines to preserve line-by-line structure
        replacement.extend(new_yaml_content.splitlines(True))

    return lines[:start] + replacement + lines[end:]


def render_yaml_list(items, indent_str="  "):
    """Render a list of dicts as indented YAML."""
    rendered = yaml.dump(items, default_flow_style=False, allow_unicode=True,
                         sort_keys=False, width=120)
    indented = ""
    for line in rendered.splitlines(True):
        indented += indent_str + line
    return indented


# --- Compaction rules ---

def compact_change_log(data, lines, dry_run=False, verbose=False):
    """Compact change_log when >10 entries."""
    entries = data.get('change_log', []) or []
    if len(entries) <= 10:
        if verbose:
            print(f"  change_log: {len(entries)} entries (threshold: 10) — no compaction needed")
        return lines, False

    recent = entries[-10:]
    older = entries[:-10]

    preserved_directional = []
    compactable = []
    for entry in older:
        if entry.get('classification') == 'directional':
            preserved_directional.append(entry)
        else:
            compactable.append(entry)

    summary_entry = None
    if compactable:
        dates = [str(e.get('date', '?')) for e in compactable]
        date_range = f"{min(dates)} to {max(dates)}" if len(dates) > 1 else dates[0]
        classifications = {}
        for e in compactable:
            c = e.get('classification', 'unknown')
            classifications[c] = classifications.get(c, 0) + 1
        class_summary = ", ".join(f"{v} {k}" for k, v in sorted(classifications.items()))

        whats = [first_sentence(e.get('what', '')) for e in compactable]
        what_summary = "; ".join(whats[:5])
        if len(whats) > 5:
            what_summary += f"; and {len(whats) - 5} more"

        summary_entry = {
            'what': f"Summary: {len(compactable)} entries compacted ({date_range})",
            'why': f"{class_summary} covering: {what_summary}",
            'blast_radius': "compacted",
            'classification': 'cosmetic',
            'date': date.today().isoformat(),
        }

    compacted = []
    if summary_entry:
        compacted.append(summary_entry)
    compacted.extend(preserved_directional)
    compacted.extend(recent)

    # If compaction wouldn't reduce entry count, nothing to do
    # (e.g., many directional entries preserved + summary already condensed)
    if len(compacted) >= len(entries):
        if verbose:
            print(f"  change_log: {len(entries)} entries — compaction cannot reduce further "
                  f"({len(preserved_directional)} directional preserved)")
        return lines, False

    if verbose:
        print(f"  change_log: {len(entries)} entries → {len(compacted)} "
              f"({len(preserved_directional)} directional preserved, "
              f"{len(compactable)} condensed to summary, 10 recent kept)")

    if dry_run:
        return lines, True

    bounds = find_section_bounds(lines, 'change_log')
    if bounds is None:
        print("  Warning: could not find change_log section in file", file=sys.stderr)
        return lines, False

    lines = replace_section_content(lines, bounds, "change_log:",
                                    render_yaml_list(compacted))
    return lines, True


def compact_chunks(data, lines, dry_run=False, verbose=False):
    """Compact build_plan.chunks when all are complete."""
    bp = data.get('build_plan', {}) or {}
    chunks = bp.get('chunks', []) or []

    if not chunks:
        if verbose:
            print("  build_plan.chunks: empty — no compaction needed")
        return lines, False

    all_complete = all(c.get('status') == 'complete' for c in chunks)
    if not all_complete:
        if verbose:
            complete = sum(1 for c in chunks if c.get('status') == 'complete')
            print(f"  build_plan.chunks: {complete}/{len(chunks)} complete — "
                  f"compaction requires all complete")
        return lines, False

    compacted = [{'id': c.get('id'), 'name': c.get('name'), 'status': 'complete'}
                 for c in chunks]

    if verbose:
        print(f"  build_plan.chunks: {len(chunks)} complete chunks → "
              f"compacted to {{id, name, status}}")

    if dry_run:
        return lines, True

    bounds = find_section_bounds(lines, 'chunks', parent_key='build_plan')
    if bounds is None:
        print("  Warning: could not find build_plan.chunks section in file", file=sys.stderr)
        return lines, False

    lines = replace_section_content(lines, bounds, "  chunks:",
                                    render_yaml_list(compacted, "    "))
    return lines, True


def compact_reviews(data, lines, dry_run=False, verbose=False):
    """Compact build_state.reviews when all findings resolved/deferred."""
    bs = data.get('build_state', {}) or {}
    reviews = bs.get('reviews', []) or []

    if not reviews:
        if verbose:
            print("  build_state.reviews: empty — no compaction needed")
        return lines, False

    compacted = []
    preserved = []
    for review in reviews:
        findings = review.get('findings', [])
        all_resolved = all(
            f.get('status') in ('resolved', 'deferred')
            for f in findings
        )
        if all_resolved:
            deferred = [f for f in findings if f.get('status') == 'deferred']
            compacted.append({
                'chunk_id': review.get('chunk_id'),
                'summary': f"{len(findings)} findings ({len(findings) - len(deferred)} resolved, {len(deferred)} deferred)",
                'deferred_items': [f.get('description', '') for f in deferred] if deferred else [],
            })
        else:
            preserved.append(review)

    if not compacted:
        if verbose:
            print(f"  build_state.reviews: {len(reviews)} reviews, none fully resolved — no compaction")
        return lines, False

    result = compacted + preserved

    if verbose:
        print(f"  build_state.reviews: {len(reviews)} reviews → {len(compacted)} compacted, "
              f"{len(preserved)} preserved (have open findings)")

    if dry_run:
        return lines, True

    bounds = find_section_bounds(lines, 'reviews', parent_key='build_state')
    if bounds is None:
        print("  Warning: could not find build_state.reviews section in file", file=sys.stderr)
        return lines, False

    lines = replace_section_content(lines, bounds, "  reviews:",
                                    render_yaml_list(result, "    "))
    return lines, True


def compact_review_findings(data, lines, dry_run=False, verbose=False):
    """Compact review_findings.entries: resolved → summary, deferred preserved."""
    rf = data.get('review_findings', {}) or {}
    entries = rf.get('entries', []) or []

    if not entries:
        if verbose:
            print("  review_findings.entries: empty — no compaction needed")
        return lines, False

    compacted = []
    preserved = []
    for entry in entries:
        findings = entry.get('findings', [])
        has_deferred = any(f.get('status') == 'deferred' for f in findings)
        all_terminal = all(
            f.get('status') in ('resolved', 'deferred')
            for f in findings
        )

        if all_terminal and not has_deferred:
            compacted.append({
                'stage': entry.get('stage'),
                'lens': entry.get('lens'),
                'summary': f"{len(findings)} findings, all resolved",
                'deferred_count': 0,
            })
        else:
            preserved.append(entry)

    if not compacted:
        if verbose:
            print(f"  review_findings.entries: {len(entries)} entries, "
                  f"none fully resolved — no compaction")
        return lines, False

    result = compacted + preserved

    if verbose:
        print(f"  review_findings.entries: {len(entries)} entries → "
              f"{len(compacted)} compacted, {len(preserved)} preserved")

    if dry_run:
        return lines, True

    bounds = find_section_bounds(lines, 'entries', parent_key='review_findings')
    if bounds is None:
        print("  Warning: could not find review_findings.entries section in file", file=sys.stderr)
        return lines, False

    lines = replace_section_content(lines, bounds, "  entries:",
                                    render_yaml_list(result, "    "))
    return lines, True


def compact_feedback_cycles(data, lines, dry_run=False, verbose=False):
    """Compact iteration_state.feedback_cycles when >10 completed."""
    it = data.get('iteration_state', {}) or {}
    cycles = it.get('feedback_cycles', []) or []

    completed = [c for c in cycles if c.get('status') == 'complete']
    active = [c for c in cycles if c.get('status') != 'complete']

    if len(completed) <= 10:
        if verbose:
            print(f"  iteration_state.feedback_cycles: {len(completed)} completed "
                  f"(threshold: 10) — no compaction needed")
        return lines, False

    compacted = [
        {
            'feedback': first_sentence(c.get('feedback', '')),
            'classification': c.get('classification'),
            'status': 'complete',
        }
        for c in completed
    ]

    result = compacted + active

    if verbose:
        print(f"  iteration_state.feedback_cycles: {len(completed)} completed → compacted, "
              f"{len(active)} active preserved")

    if dry_run:
        return lines, True

    bounds = find_section_bounds(lines, 'feedback_cycles', parent_key='iteration_state')
    if bounds is None:
        print("  Warning: could not find iteration_state.feedback_cycles section", file=sys.stderr)
        return lines, False

    lines = replace_section_content(lines, bounds, "  feedback_cycles:",
                                    render_yaml_list(result, "    "))
    return lines, True


# --- Main ---

SECTION_COMPACTORS = {
    'change_log': compact_change_log,
    'chunks': compact_chunks,
    'reviews': compact_reviews,
    'review_findings': compact_review_findings,
    'feedback_cycles': compact_feedback_cycles,
}


def main():
    parser = argparse.ArgumentParser(
        description="Compact growing project-state.yaml sections per LIFECYCLE rules."
    )
    parser.add_argument('file', nargs='?', default=None,
                        help="Path to project-state.yaml (default: repo root)")
    parser.add_argument('--dry-run', action='store_true',
                        help="Show what would change without writing")
    parser.add_argument('--check', action='store_true',
                        help="Exit 1 if compaction needed, 0 if not")
    parser.add_argument('--section', action='append', dest='sections',
                        choices=list(SECTION_COMPACTORS.keys()),
                        help="Compact only specified section(s) (repeatable)")
    parser.add_argument('--verbose', action='store_true',
                        help="Show detailed before/after for each section")

    args = parser.parse_args()

    if args.file:
        state_file = args.file
    else:
        # Use shared product root resolution
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            result = subprocess.run(
                [os.path.join(script_dir, 'resolve-product-root.sh')],
                capture_output=True, text=True, check=True
            )
            product_root = result.stdout.strip()
            state_file = os.path.join(product_root, 'project-state.yaml')
        except (subprocess.CalledProcessError, FileNotFoundError):
            state_file = 'project-state.yaml'

    if not os.path.isfile(state_file):
        print(f"Error: File not found: {state_file}", file=sys.stderr)
        sys.exit(1)

    with open(state_file) as f:
        content = f.read()

    data = parse_full_state(content)
    lines = content.splitlines(True)

    sections = args.sections or list(SECTION_COMPACTORS.keys())

    any_compacted = False
    if args.dry_run or args.verbose or args.check:
        print(f"Analyzing: {state_file}")
        print(f"  Total lines: {len(lines)}")
        print()

    for section in sections:
        compactor = SECTION_COMPACTORS[section]
        lines, compacted = compactor(data, lines, dry_run=(args.dry_run or args.check),
                                     verbose=(args.verbose or args.dry_run or args.check))
        if compacted:
            any_compacted = True

    if args.check:
        if any_compacted:
            print("\nCompaction needed.")
            sys.exit(1)
        else:
            print("\nNo compaction needed.")
            sys.exit(0)

    if args.dry_run:
        if any_compacted:
            print("\nDry run complete. Run without --dry-run to apply changes.")
        else:
            print("\nNo sections need compaction.")
        sys.exit(0)

    if any_compacted:
        with open(state_file, 'w') as f:
            f.writelines(lines)
        print(f"Compacted: {state_file}")
    else:
        if args.verbose:
            print("No sections need compaction.")


if __name__ == '__main__':
    main()
