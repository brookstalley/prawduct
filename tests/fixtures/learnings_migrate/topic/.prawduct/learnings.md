# Learnings

Concise rules. See `learnings-detail.md` for root cause analysis.

## Eval & Model Bake-offs
- **Judges hallucinate.** Verify a verdict against the transcript before trusting it. [detail](learnings-detail.md#judges-hallucinate)
- **n=1 is noise on a coin-flip metric.** Re-run before you believe a single-run reversal.

## Pydantic v2
- **No `@dataclass` at boundaries.** Anything crossing API/IPC/storage must be Pydantic.
- **Whitespace-significant fields use plain `BaseModel`.** The shared base sets `str_strip_whitespace=True`.
- **Every `*_simple` serializer round-trips through its source model.** Missing required fields fail at construction. → detail.
