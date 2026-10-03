// Reports built by the real client (plugin/lib/contribution.py: to_step,
// then canonical_bytes), with the exact bytes Python wrote for each. Produced
// by the python3 command in collector/README.md § Tests.

export const PYTHON_REPORTS = [
  {
    report: {
      schema: 1, iso_year: 2026, iso_week: 39, plugin_major: 3, plugin_minor: 7, dev: false,
      sessions: "10-49", scopes: "1-9", reviews: "10-49",
    },
    bytes:
      '{"dev":false,"iso_week":39,"iso_year":2026,"plugin_major":3,"plugin_minor":7,"reviews":"10-49","schema":1,"scopes":"1-9","sessions":"10-49"}',
  },
  {
    report: {
      schema: 1, iso_year: 2026, iso_week: 39, plugin_major: 3, plugin_minor: 7, dev: true,
      sessions: "200+", scopes: "50-199", reviews: "0",
      rounds_per_scope_median: 2.5, rounds_per_scope_p90: 3, estimated_only_review_share: 0.35,
      red_test_run_share: 0.35, stops_blocked_per_session: 0.3,
    },
    bytes:
      '{"dev":true,"estimated_only_review_share":0.35,"iso_week":39,"iso_year":2026,"plugin_major":3,"plugin_minor":7,"red_test_run_share":0.35,"reviews":"0","rounds_per_scope_median":2.5,"rounds_per_scope_p90":3,"schema":1,"scopes":"50-199","sessions":"200+","stops_blocked_per_session":0.3}',
  },
  {
    report: {
      schema: 1, iso_year: 2025, iso_week: 1, plugin_major: 0, plugin_minor: 0, dev: false,
      sessions: "10-49", scopes: "1-9", reviews: "10-49",
      review_minutes_median: 13, review_minutes_per_scope_median: 41, blocking_per_review: 1.3,
      warning_per_review: 0.3, note_per_review: 7.1, blocking_acted_on_rate: 1, warning_acted_on_rate: 0.75,
      note_acted_on_rate: 0, blocking_fixed_per_scope: 0.1, warning_fixed_per_scope: 3,
      empty_verify_round_share: 0.15, rereview_same_interval_share: 0.05, rereview_same_head_share: 0.95,
      guard_refusals_per_session: 100,
    },
    bytes:
      '{"blocking_acted_on_rate":1,"blocking_fixed_per_scope":0.1,"blocking_per_review":1.3,"dev":false,"empty_verify_round_share":0.15,"guard_refusals_per_session":100,"iso_week":1,"iso_year":2025,"note_acted_on_rate":0,"note_per_review":7.1,"plugin_major":0,"plugin_minor":0,"rereview_same_head_share":0.95,"rereview_same_interval_share":0.05,"review_minutes_median":13,"review_minutes_per_scope_median":41,"reviews":"10-49","schema":1,"scopes":"1-9","sessions":"10-49","warning_acted_on_rate":0.75,"warning_fixed_per_scope":3,"warning_per_review":0.3}',
  },
];

// A minimal valid report, as raw JSON text, with one field replaced or added.
export function reportText(overrides = {}, drop = []) {
  const base = { ...PYTHON_REPORTS[0].report, ...overrides };
  for (const key of drop) delete base[key];
  return JSON.stringify(base);
}
