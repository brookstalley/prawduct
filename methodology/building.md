# Building: Turning Plans Into Working Software

Building is where plans meet reality. The artifacts tell you what to build; the principles tell you how to behave while building it. Your job is to translate specifications into working, tested, maintainable code — and to surface honestly when the specs are wrong or incomplete.

## The Build Cycle

For each chunk in the build plan:

**Read the spec.** Read the chunk's entry in `.prawduct/artifacts/build-plan.md` and any referenced artifacts in that directory. Understand what this chunk delivers, what its acceptance criteria are, and what it depends on. If anything is ambiguous, flag it before building — don't guess silently.

**Write tests.** Tests come first or alongside implementation, not after. Tests are your specification made executable. They define the behavior you're implementing. If you can't write the test, you don't understand the requirement well enough to implement it.

Test at the right level:
- **Unit tests** for individual functions and logic
- **Integration tests** for component interactions, data flow, state transitions
- **End-to-end tests** for critical user flows and acceptance criteria

Depth is proportionate to risk. A personal utility needs basic happy-path and critical-error coverage. A financial platform needs comprehensive edge case and failure mode coverage.

**Implement.** Write the code that makes the tests pass. Follow the project's coding conventions and preferences (if captured during discovery). Prefer simplicity — the right amount of abstraction is the minimum needed for the current chunk. Don't build for hypothetical future requirements.

**Verify.** Two layers:

- *Code verification:* Run all tests — not just the ones you wrote, but the full suite. A new chunk shouldn't break existing chunks. Check that acceptance criteria are met. Check that the implementation matches the spec.
- *Product verification:* Confirm the product works as its users or consumers would experience it. Tests verify code behavior; product verification confirms the actual experience. What this means depends on what you're building — use your knowledge of the product's structural characteristics (Principle 20). Launch it, call it, run it, inspect its output. Use the tools available to you.

Scale verification to chunk significance. Scaffold → "it starts." Data layer → "queries return expected results." Feature delivering user-visible behavior → "I exercised it directly and it works." Not every chunk needs exhaustive verification.

When you can't verify directly, say what you can't verify and why. Tell the user what to check. Don't claim verification you didn't perform (Principle 5).

**Request Critic review.** This step is mandatory — do not skip it, defer it, or self-review instead. After completing a chunk, invoke the Critic agent as a separate agent (via the Task tool). The Critic runs in its own context, providing genuine independence — it hasn't seen your reasoning. Tell it to read `agents/critic/SKILL.md` (or `.prawduct/critic-review.md` in product repos) and review the changes. The stop hook will block session end if you skip this step.

**Resolve findings.** Fix blocking findings before proceeding. Address warnings. Document any notes or disagreements with rationale.

**Reflect.** The Critic just gave you independent feedback. This is the highest-signal moment for learning. Before moving on: What did the Critic catch that you missed? Does it match a pattern in `learnings.md`? If the finding reveals a blind spot, capture it now — don't wait for session end. If there's nothing to capture, that's fine. The point is to check, not to force a lesson.

**Update state.** Record what was built, what tests were added, and any issues discovered. Update `project-state.yaml` so the next session has accurate context.

## Working With Specs

Specs are guides, not scripture. Implementation always reveals things the spec didn't anticipate. When this happens:

**If the spec is wrong** (the specified behavior wouldn't actually work), flag it. Propose the fix. Update the spec to match reality. Don't silently deviate — that creates Documentation Fiction (Principle 3).

**If the spec is ambiguous** (multiple reasonable interpretations), pick the most likely interpretation, implement it, and note the ambiguity. Don't block on getting clarification for every minor ambiguity — use judgment and move forward.

**If the spec is incomplete** (a case it doesn't cover), surface it. For edge cases that don't affect the core flow, make a reasonable choice and document it. For significant gaps, escalate to the user.

**If you can't implement something**, say so explicitly. Never silently drop a requirement (Principle 2). "I can't implement X because Y — here's what I suggest instead" is always better than quiet omission.

## Test Discipline

Tests are the most important artifact you produce during building. They're contracts that define correct behavior, and they protect against regression as the codebase grows.

**Tests are behavioral.** Test what the code does, not how it does it. Test inputs and outputs, state transitions, error conditions. Don't test implementation details — they change when you refactor, and brittle tests that break on refactoring provide false signal.

**Tests are independent.** Each test should be self-contained — no shared mutable state, no dependency on test execution order, cleanup after itself. Flaky tests are worse than no tests because they teach you to ignore test failures.

**Tests never weaken.** Test count doesn't decrease. Assertion depth doesn't decrease. If a test needs to change because behavior changed, update it explicitly — don't delete it and call it cleanup. This is Principle 1 (Tests Are Contracts), and it's a bright line.

**Test coverage is proportionate.** A family utility doesn't need 95% code coverage. A payment system does. Match coverage to risk. But every product needs at least: happy path through core flows, error handling for likely failures, and edge cases for anything involving money, data, or safety.

## The Critic

After each chunk, invoke the Critic agent in a separate context. The Critic checks:

- **Scope**: Did the change stay within what was planned?
- **Proportionality**: Is the change weight-appropriate? Over-engineering?
- **Coherence**: Are artifacts still consistent with each other and with the code?
- **Learning**: Does the change preserve the system's ability to learn and observe?
- **Spec compliance** (during builds): Does the implementation match the specification?
- **Test integrity** (during builds): Are tests present, passing, and meaningful?

See `agents/critic/SKILL.md` for the complete check definitions and invocation protocol.

**Blocking findings** must be resolved before moving to the next chunk. **Warnings** should be addressed but don't block. **Notes** are informational.

If the Critic finds something you disagree with, think carefully before dismissing it. The Critic is independent for a reason — it catches blind spots the builder can't see. If you still disagree after reflection, document why and proceed.

## Common Traps

**Test corruption**: Weakening tests to make them pass. This is the single most dangerous pattern in software development. It passes now, breaks later, and erodes trust in the test suite. Fix the code, never the test. (If the test is genuinely wrong, update it with an explanation of why the expected behavior changed.)

**Silent requirement dropping**: Implementing 9 of 10 requirements and hoping nobody notices the missing one. They will. Flag it.

**Gold plating**: Adding features the spec didn't ask for. "While I'm in here, I'll also add..." is scope creep. Do what was asked (Principle 11).

**Test-last**: Writing all the code, then writing tests that pass against the existing implementation. This tests what the code does, not what it should do. Tests written after implementation rarely catch bugs — they just document existing behavior, including bugs.

**Ignoring the Critic**: Dismissing findings without genuine reflection. The Critic exists because self-review doesn't work. If you find yourself routinely disagreeing with the Critic, something is wrong — either the Critic's checks need updating (propose amendments) or your building practices need adjusting.

**Verification theater**: Claiming verification without actually exercising the product. "I verified it works" without evidence is worse than "I couldn't verify this — here's what to check." Honest confidence (Principle 5).

**Pacing blindness during builds**: Asking implementation questions when the user is waiting for progress. During building, the user's primary signal is usually "show me something working." Decide autonomously on minor implementation details — naming, internal structure, error message wording — unless you're genuinely blocked or the choice has user-visible consequences. Save questions for decisions that would be expensive to reverse.
