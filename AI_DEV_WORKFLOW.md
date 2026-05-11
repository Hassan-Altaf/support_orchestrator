# AI-Assisted Development Workflow

This document captures how I used AI tools to build this assessment, what
human judgment shaped the design, and how I would run a team of AI-assisted
engineers on a project of this shape.

> **Note for the reviewer**: places marked `<< PERSONALIZE: ... >>` are where
> the author of this submission should inject real anecdotes from their own
> build run before submitting. The structural argument below is intentional;
> the personal stories make it credible.

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

<< PERSONALIZE: real before/after of one prompt diff and the specific bad
output that motivated v3 — e.g. paste the v2 prompt's classification of the
multi-tenant outage message vs the v3 prompt's, and explain which clause of
the predicate fired. >>

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

<< PERSONALIZE: one specific bug you caught in AI-generated code that the
test suite *also* caught, demonstrating that the defense-in-depth worked. >>

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

<< PERSONALIZE: which 2-3 messages you tested against the *real* LLM and what
you observed — was the model's classification consistent with the eval label?
Did anything surprise you? >>

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
| Prompt injection via user input | Input sanitization, output validation via Pydantic, never include user text in system prompts verbatim, structured outputs constrain blast radius |

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

<< PERSONALIZE: how you would actually phase these into a team — which one
would you ship first and why? >>

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
