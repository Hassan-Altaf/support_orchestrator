# AI-Assisted Development Workflow

This document captures how I used AI tools to build this assessment, what
human judgment shaped the design, and how I would run a team of AI-assisted
engineers on a project of this shape.

---

## 1. AI tools used

### Claude Code (Anthropic) — primary code-generation environment

Used end-to-end for: the FastAPI scaffold, all five LangGraph node
implementations, the Protocol-based provider abstraction, Pydantic domain
models, the test suite scaffold, Docker multi-stage build, GitHub Actions CI,
the demo + eval scripts, and the prompts.

Chosen over generic ChatGPT because Claude Code (a) operates against the actual
filesystem and runs commands, so I could verify each stage end-to-end rather
than copy-paste-and-pray, (b) holds a long context that survives the build
without me re-priming, and (c) is itself an Anthropic-trained model — useful
sanity-check when working with Anthropic's SDK.

### Claude (web chat) — architecture review and prompt critique

Used to challenge initial designs and produce the ARCHITECTURE.md rationale.
Specifically: I asked it to argue *against* my proposed topology (the
`customer_response → escalation` direction, before I flipped it) and produce
the strongest case for the alternative. The exercise surfaced the "the reply
needs to reflect escalation status" argument that's now in ARCHITECTURE.md §5.

### Cursor / IDE Copilot — inline edits

Used selectively for boilerplate fills: repetitive `Field(min_length=...,
max_length=...)` decorators, `# noqa` comments, similar test cases. Disabled
for prompt text and for any code in `app/orchestration/` so I'd genuinely
engage with the orchestration logic rather than auto-accept its first guess.

### What I did *not* use

- **Autonomous agents** (Auto-GPT-style multi-step planners) for the build
  itself. The take-home is graded on engineering judgement; using an autonomous
  agent to make architectural decisions defeats the purpose.
- **Code search SaaS** like Cody / Sourcegraph. Project is too small to need it.

---

## 2. AI coding process

### What was AI-generated end-to-end

- FastAPI app factory + lifespan + middleware
- Pydantic models from the spec table
- LangGraph wiring boilerplate (StateGraph + node registration + conditional
  edge)
- Test fixtures and the conftest builder-factory pattern
- Dockerfile multi-stage + docker-compose + CI workflow
- Initial prompt drafts for each node

### What was manually edited / decided (human judgment)

- **Graph topology** — specifically: `customer_response` is downstream of
  `escalation` on the yes branch (not parallel). Reason in ARCHITECTURE.md §5.
- **Safe-fallback values** — every node's fallback was hand-tuned. The
  extractor's `_fallback_for(raw_message)` pads short messages to satisfy the
  `min_length=10` constraint on `issue_summary`; without that, a 2-char input
  ("hi") would make the fallback itself fail validation. Caught by the test
  `tests/test_nodes.py::TestExtractorNode::test_fallback_pads_short_message`.
- **Protocol over ABC for `LLMProvider`** — Claude Code's first draft used an
  abstract base class. I rejected and re-prompted for the structural-typing
  approach because (a) it makes mocks trivial and (b) it's idiomatic in modern
  async Python.
- **Retry strategy** — Claude Code's first draft was naive (retry the same
  prompt). I flagged this as failing the senior-signal bar and re-prompted for
  feedback-augmented retry. The current `call_with_retry` is the result.
- **mypy config** relaxed from `--strict` to `disallow_untyped_defs` — strict
  mode fights endlessly with `pydantic-settings` and `langgraph` stubs in ways
  that consume time without improving the codebase.
- **`extra="forbid"` on every LLM-output model** — defensive against
  hallucinated keys. Adds belt-and-suspenders to the provider-level strict
  schema constraint.
- **The decision to type `TraceEntry.outcome` as `Literal[...]`** instead of a
  free `str` — caught a typo I'd written in an early node implementation
  (`outcome="retried"` instead of `"retry"`) at mypy time rather than
  runtime.

### How prompts evolved

- **v1**: verbose, multi-paragraph role descriptions. First runs produced
  over-confident outputs that ignored the priority-vs-urgency distinction.
- **v2**: tightened to **role → task → output fields → 1-2 few-shot examples →
  "no commentary"** structure. Cleaner outputs, but inconsistent escalation
  flagging across similar messages.
- **v3** *(current)*: added an explicit 4-clause OR predicate to the
  `escalation_required` definition. This eliminated the inconsistency entirely
  on the local eval set.

**Concrete v2 → v3 diff — the escalation predicate**

The v2 prompt described escalation as: *"true when the issue is severe enough
to need on-call attention or VIP signals are present"*. Running the local eval
on this version, two messages produced inconsistent flags:

- `eval_07_intermittent_audio` ("audio dropouts on inbound calls, maybe once
  every 20 calls") was flagged `escalation_required=true` with reasoning
  *"audio quality is a high-impact issue"* — wrong. It's a `medium`-priority
  bug, not an outage, no VIP signals.
- `eval_10_data_concern` ("call recordings from a different tenant showed up
  in our portal") was flagged `escalation_required=false` with reasoning
  *"customer can use the support flow"* — wrong. This is a data-integrity
  breach that must escalate regardless of priority.

v3 replaced the soft definition with a hard 4-clause OR predicate
(visible in [`app/prompts/classify.py`](app/prompts/classify.py)):

```
escalation_required: true ONLY if any of the following hold:
    * priority is "critical"
    * message describes a multi-customer outage signal
    * message describes a security or data-integrity concern
    * message contains a named-account or VIP signal
```

After v3, both messages classify correctly: the intermittent-audio case fails
all four clauses → `false`; the cross-tenant recording case matches clause 3
(data-integrity concern) → `true`. The predicate also doubled as the test
contract — `tests/test_graph.py::test_critical_bug_takes_escalation_path`
and `test_billing_question_skips_escalation` lock in this routing behavior.

### How incorrect AI outputs were handled

- Claude Code's first scaffold included a single-prompt design. **Rejected and
  re-prompted with explicit `LangGraph state machine` requirement.**
- The test scaffolds had import errors on first generation (incorrect module
  paths into `app.orchestration.nodes`). **Pasted the actual repo tree back
  and re-prompted with that as fixed context.**
- LangGraph version drift: the first generated wiring used a pre-1.0 API
  surface. **Pinned `langgraph>=1.0,<2.0` in `pyproject.toml` and regenerated
  the affected files.**
- The OpenAI provider's structured-output path was generated with
  `client.beta.chat.completions.parse()`. I checked the installed
  `openai==1.109.1` SDK directly and confirmed `client.chat.completions.parse()`
  (no `beta.`) is the GA path. Updated the code with a comment.
- The Anthropic provider initially didn't narrow `response.content`'s union
  type, so mypy flagged 10 errors on `block.input`. Fixed by importing
  `ToolUseBlock` and using `isinstance(block, ToolUseBlock)` for proper
  narrowing.

**Concrete defense-in-depth catch — the extractor fallback short-message bug**

While writing the extractor node's fallback (Stage 6), I asked Claude Code to
produce a safe default for when the LLM call fails. The first draft was:

```python
ExtractedInfo(
    product_area="unknown",
    issue_summary=raw_message[:200],   # ← bug
    urgency=Urgency.NORMAL,
    suggested_tags=["unclassified"],
)
```

This looks fine for typical inputs, but for a 2-character message like `"hi"`
the slice produces `"hi"` — which fails the `min_length=10` constraint on
`ExtractedInfo.issue_summary` that I had tightened in Stage 3. The fallback
*itself* would have raised `ValidationError`, defeating the whole point of a
safe fallback (the pipeline would crash on tiny inputs).

Two layers of defense caught this:

1. **The Stage 3 Pydantic constraint** — without `min_length=10` on the
   summary field, the bug would have silently shipped an empty-ish summary
   into the API response.
2. **The Stage 6 test
   `tests/test_nodes.py::TestExtractorNode::test_fallback_pads_short_message`**
   — `initial_state("hi", "req-3")` → expects the fallback to satisfy the
   constraint. The test failed on the first run, forcing the fix:

```python
snippet = raw_message.strip()[:200] if raw_message.strip() else "no content provided"
if len(snippet) < 10:
    snippet = (snippet + " (auto-fallback)").ljust(10)
```

The same pattern recurred in the `internal_summary` fallback for a different
field bound — same fix idiom.

**The senior takeaway**: tightened Pydantic bounds aren't just user-facing
contracts; they're tripwires that catch the AI's silent assumptions about
input shape.

---

## 3. Validation process

### Schema-level

- **Pydantic validation on every node output** — the LLM's response is parsed
  into the target model, and validation failure triggers retry-with-feedback.
- **Tight field bounds** (`min_length`, `max_length`, `ge`, `le`) on every LLM-
  populated field. These bounds are *also* the contract communicated to the
  LLM in the prompt — so the model knows the constraint, and the validator
  enforces it.
- **`extra="forbid"` on every LLM-output model** — hallucinated keys fail
  parsing rather than silently leaking into the API response.

### Test-level

- **Unit tests per node** with a `MockProvider` returning canned outputs
  (`tests/test_nodes.py`). Each node has happy / retry / fallback / provider-
  exception cases.
- **Integration tests for the full graph** with the 5 scenario fixtures
  (`tests/test_graph.py`).
- **HTTP-level tests via FastAPI `TestClient`** (`tests/test_api.py`) including
  every validation case, the request-id middleware (generated AND client-
  supplied), and the recovered-error path.
- **Focused retry-behaviour tests** (`tests/test_validation_retry.py`)
  including a `SpyProvider` that asserts the prior `ValidationError` is fed
  back into the user prompt on retry — the senior-signal behaviour.
- **Coverage gate at 80% in CI** (currently 87% overall, 100% on
  `app/orchestration/`, ~95% on `app/api/`).

### Eval harness

`scripts/eval.py` runs `tests/fixtures/eval_set.json` (10 labelled messages)
through the compiled graph and writes `samples/eval_report.md` with overall
accuracy, per-category precision/recall/F1, a confusion matrix, and average
confidence split by correct-vs-wrong predictions. This is the mechanism for
catching prompt regressions — every prompt change should pass the eval before
merging.

### Recording / replay

`RecordingProvider` wraps any provider and writes each `<system, user, model,
temperature> → response` pair to `tests/fixtures/recordings/<hash>.json` in
`record` mode, then returns those responses from disk in `replay` mode. This
gives us deterministic regression tests against captured real LLM outputs
without spending tokens in CI.

### Manual end-to-end

Ran `make demo-mock` against all 5 sample messages — verified all five paths
through the graph including the conditional-edge routing.

**What I observed against a real LLM (Gemini 2.0 Flash, free tier)**

Three of the five sample messages drove the first real-LLM end-to-end run:

1. **`critical_bug_deadline`** — *"Mobile app crashes for all supervisors,
   board demo in 2 hours."* — Gemini classified this as
   `technical_bug / critical / escalation_required=true`, matching the eval
   label exactly. Confidence: 0.92. The customer reply correctly avoided
   promising a fix timeline (the rule in `customer_response.py`).
2. **`billing_question`** — *"got billed twice for our March subscription."*
   Classified as `billing / medium / escalation=false`, matching the label.
   Surprise: the extractor produced `urgency=NORMAL` even though the
   customer didn't say "urgent" — calibration on tone-vs-urgency was correct.
3. **`multi_tenant_outage`** — *"Inbound calls aren't connecting for ANY of
   our tenants."* Classified as `outage / critical / escalation=true`,
   `severity_level=5`, routed to `voice-platform`. Trace: 5 nodes,
   `outcome=ok` on all of them.

**The real surprise — a recoverable production-grade bug.** The very first
real-LLM run **failed all four LLM calls** with `400 INVALID_ARGUMENT:
Unknown name "additional_properties"`. Two facts converged:

- Pydantic emits `additionalProperties: false` whenever a model declares
  `extra="forbid"` — which every LLM-output model in this codebase does, by
  design (Stage 3 defense-in-depth).
- Gemini's `response_schema` API parses a strict subset of OpenAPI that
  rejects `additionalProperties` (and `$ref` / `$defs`, which we also emit
  for enums).

The graph's safe-fallback layer turned what would have been a 500-error
demolition into a successful HTTP 200 with `recovered_errors` populated and
every `trace.outcome=fallback` — exactly the survivable failure mode the
architecture targets. **The bug was visible because of structured
observability, fixable in 20 lines** (`_pydantic_to_gemini_schema()` in
`app/llm/gemini_provider.py` walks the Pydantic schema, inlines `$ref`s, and
strips Gemini-incompatible keys), and **proved the LLM provider abstraction
worked**: I added a fourth provider without touching nodes, prompts,
state, graph, or tests. Pydantic re-validation on the client side stayed —
so a deviating Gemini response still triggers retry-with-feedback like
OpenAI/Anthropic.

---

## 4. Team scaling — running a team of AI-assisted engineers

### Code-review strategy

- **PR labels**: `ai-generated` vs `human-authored`. AI-generated PRs touching
  domain logic, prompts, or security require **two senior reviewers**.
  Boilerplate AI code (scaffolds, config, repetitive tests) ships with peer
  review.
- **Every PR description must answer three questions**:
  1. What did the AI generate?
  2. What did you change manually, and why?
  3. What did you verify (which tests, which manual scenarios)?
- **Junior engineers cannot self-approve AI-generated code** for the first 90
  days, regardless of test coverage.

### Quality gates in CI (all blocking)

- `ruff check` + `ruff format --check`
- `mypy app` with `disallow_untyped_defs`
- `pytest --cov-fail-under=80`
- **Eval-harness regression check on prompt changes** — any drop in accuracy
  on any category blocks the PR
- Dependency vulnerability scan (`pip-audit`)
- Secret scanner (`gitleaks`) on pre-commit and CI
- Docker build smoke-test

### Prompt registry as version-controlled code

Prompts live in `app/prompts/*.py` — not embedded in node code, not in a
database. Changes go through normal PR review. The diff shows the prompt
change in context, and the eval-harness regression check enforces quality.

For a larger team, the next step is a prompts-as-data registry with semantic
versioning and tenant-level A/B routing, but for now keeping prompts in code
is the right friction level.

### Risks and controls

| Risk | Control |
|---|---|
| AI confidently produces wrong code | Mandatory test coverage + manual end-to-end verification on critical paths + retry-with-feedback runtime safety net + safe fallbacks on every node |
| Hallucinated APIs or non-existent libraries | Typecheck + actual import in CI catches these before merge |
| Silent drift in LLM behavior | Recording/replay snapshots in CI; pin model version (`gpt-4o-mini`, not `gpt-4o`); regression eval-harness blocks merges that drop accuracy |
| Credentials in commits | `gitleaks` pre-commit hook + `.env` in `.gitignore` (with `!.env.example` escape) + `detect-private-key` pre-commit hook |
| Over-reliance on AI eroding fundamentals | Pairing rotations; juniors solo-implement one feature per sprint without AI; quarterly "no-AI day" exercises |
| Prompt injection via user input | Delimiter sanitization in `build_user_prompt` (any `>>>` in the raw message is collapsed so the customer can't break out of the `<<<...>>>` envelope), output validation via Pydantic, user text is only ever embedded in the *user* message — never spliced into the system prompt, structured outputs constrain blast radius |

### Onboarding new AI-assisted contributors

90-day "AI-reviewed" period — every merge gets a senior pass regardless of
contributor seniority. After 90 days, normal review rules apply. The point is
not to gatekeep but to make sure the contributor builds the *judgement* of
when AI is wrong before they're trusted to ship unsupervised.

### Cost & latency controls

- **Cheaper model for deterministic tasks** (`gpt-4o-mini` for classify /
  extract / escalation / summary; reserve the bigger model for
  `customer_response` if generation quality becomes the bottleneck).
- **Cache classification outputs by message hash** — identical message ⇒
  identical category. Low risk, high payoff for FAQ-style traffic.
- **Parallel-execution opportunity** for `extract` after `classify` — the two
  are independent. LangGraph supports fan-out; left as the most obvious
  optimisation for a v2.

**My phasing for a team of 4-6 AI-assisted engineers**

**Week 1 — ship the eval-harness regression gate before anything else.**
This is the single highest-leverage control. Without it, every other quality
gate (linting, type-checking, test coverage) catches *code* regressions but
silently passes *prompt* regressions — and prompt regressions are where AI
teams quietly degrade in production. Even a 20-message labeled set on a
single category is enough to start; the labeled set grows organically as
production tickets are sampled and reviewed.

**Week 2 — wire up `pin model version` discipline.** Move `OPENAI_MODEL`
and `GEMINI_MODEL` from `gpt-4o-mini` / `gemini-2.0-flash` (aliases that
quietly shift) to dated pins (`gpt-4o-mini-2024-07-18` style). Add a
weekly cron that runs the eval harness against the latest non-pinned alias
and posts a Slack diff if accuracy moved. This catches OpenAI/Google
quietly retraining the underlying model — which has happened to me and is
the most insidious silent-drift mode.

**Week 3 — caching layer for classifier on message hash.** Single-line
LRU cache in the classifier node keyed on `sha256(raw_message)`. The
support inbox is full of FAQ-shaped repeats; caching takes 30-40% of
classify calls off the LLM bill while staying safe (identical input ⇒
identical category is a low-risk equivalence).

The other controls (per-tenant rate limits, async background processing,
DLQ, persistent ticket store) wait until production traffic justifies them
or compliance demands them. Shipping them on day one is over-engineering
for a system that doesn't yet have proof-of-load. The eval gate + pinned
models + cheap caching cover 80% of the operational risk for 10% of the
code volume.

---

## A closing note on judgement

The reason a single-prompt design is forbidden by the brief is that a senior
architect's job is not to maximise what the model can do in one shot — it's to
break the problem into pieces where the model's failures are *survivable*. Every
choice in this codebase — multi-step graph, retry-with-feedback, safe fallbacks,
extra="forbid", Pydantic bounds doubling as prompt contracts, the recording
provider, the eval harness — is in service of that one principle: when the AI
gets it wrong, the system still ships a usable answer, and we can tell exactly
which sub-decision failed.
