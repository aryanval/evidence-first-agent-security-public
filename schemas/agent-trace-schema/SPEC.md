# Agent Evidence Envelope — v0.2

*(v0.1 was "Agent Trace Schema". Same directory, same vendoring model, wider job:
it is no longer a trace format, it is an evidence envelope over one.)*

The shared data contract for the agent-security portfolio. It is the **only**
coupling between the repos: they agree on this record shape, not on each other's
code. No shared library, no cross-repo imports.

## What changed conceptually in 0.2

v0.1 answered *what happened, and did the agent or a sensor say so.* That is a
two-value question, and it is not enough to support a security claim.

v0.2 answers a harder one: **for each edge in the chain between a principal and a
side effect, what class of evidence supports it, who is asserting it, from which
trust domain, and what did that observer already know it could not see.** The
execution record itself moves onto OpenTelemetry; this contract becomes the
envelope around it.

The design constraint throughout: *never let a chain of self-reported records read
as proof.* Weak evidence is not rejected — it is labelled, and it stays labelled
through every downstream transformation.

---

## 1. Execution substrate: OpenTelemetry GenAI spans

The envelope does not define a trace format. The GenAI semantic conventions
already model an agent run as a span tree, and MCP folds into the same
vocabulary. Inventing a parallel trace ecosystem would be the wrong move; the
right one is to carry evidence *on* OTel.

**The pinned convention version lives in `VERSION`.** Read it before implementing
anything in this file. The GenAI conventions are **pre-stable (development)**:
attribute names, operation names and span shapes may be renamed or removed
between semconv releases without a major-version signal. `VERSION` also records
that the pin was taken from working notes rather than re-fetched from upstream —
the pin's own `pin_evidence_class` is `CLAIMED`. This contract does not exempt
itself from its own doctrine.

### Span → envelope `kind`

| OTel operation (`gen_ai.operation.name`) | envelope `kind` | pinned? |
|---|---|---|
| `invoke_agent`, `create_agent` | `agent_run_start` / `agent_run_end` | yes |
| `chat`, `generate_content`, `text_completion` | `model_call` | yes |
| `execute_tool` | `tool_call` | yes |
| `embeddings` | `retrieval` (as the embedding step of one) | yes |
| *retrieval* | `retrieval` | **no — see below** |
| *plan* | `plan` | **no** |
| *memory* | `memory` | **no** |
| — (no span; agent-to-agent hop) | `delegation` | n/a |
| — (no span; witnessed outside the process) | `token_event`, `process_spawn`, `network_egress`, `file_write` | n/a |
| — (derived) | `security_finding` | n/a |

`retrieval`, `plan` and `memory` exist as envelope kinds because the portfolio
needs to reason about them — untrusted input arrives at `retrieval`, goal hijack
shows up as a `plan` revision, and `memory` is how injected content survives
across runs. **Their OTel span names are not pinned.** Treat `otel.operation_name`
on those records as best-effort until the conventions land them; the envelope
`kind` is the stable name.

Records with no span at all are normal and important: a kernel-observed process
spawn or a cloud audit row has no `otel` object. Those are exactly the records
that corroborate the ones that do.

### Binding a record to its span

`otel.trace_id` + `otel.span_id` is the join key between this JSONL stream and
the OTLP stream. `run_id` / `span_id` / `parent_span_id` remain the envelope's own
identifiers and remain required — they work for spanless records, and they let a
consumer reconstruct a run without an OTLP backend at all.

---

## 2. The action-provenance chain

Every envelope record describes one node in, or one edge of, this chain:

```
principal → delegation → agent identity → runtime instance → input
          → authorization → tool → side effect
```

Every arrow is a claim of causality. The goal is not to pretend each is directly
observable — it is to state **what class of evidence supports each edge** and how
much uncertainty remains.

### Where each node lives in the record

| Chain node | Carried by |
|---|---|
| principal | `data.principal` on `agent_run_start` (`id`, `type`, `auth_method`, `delegation_depth`) |
| delegation | `kind: delegation` — `from_agent`, `to_agent`, `on_behalf_of`, `delegation_ref` |
| agent identity | `agent.identity_ref` (IAM role ARN, Entra SP id, broker subject) |
| runtime instance | `agent.instance_id` — the process/container/session the identity ran in |
| input | `kind: retrieval` with `data.content_trust`; `model_call.prompt_digest`; `memory` reads |
| authorization | `kind: token_event` — `op`, `subject`, `audience`, `scopes`, `jti`, `decision` |
| tool | `kind: tool_call` — `tool`, `args_digest`, `mediated_by` |
| side effect | `process_spawn`, `network_egress`, `file_write`, or any record with `data.authoritative_ref` |

`agent.identity_ref` without `agent.instance_id` is a common and consequential
gap: two concurrent runs under one identity cannot be told apart, so attribution
degrades from "this agent did it" to "something running as this identity did it."

### Edges

`causal_link.edge` names which arrow a parent link represents:

| `edge` value | joins |
|---|---|
| `principal_to_delegation` | principal → delegation |
| `delegation_to_agent_identity` | delegation → agent identity |
| `agent_identity_to_runtime_instance` | agent identity → runtime instance |
| `runtime_instance_to_input` | runtime instance → input |
| `input_to_authorization` | input → authorization |
| `authorization_to_tool` | authorization → tool |
| `tool_to_side_effect` | tool → side effect |
| `intra_run_sequence` | ordering *within* one stage — not a chain edge |
| `unspecified` | what a 0.1 record upgrades to |

**Every edge carries its own `evidence_class`, independent of the nodes it
joins.** This is the point of the whole design. A `tool_to_side_effect` edge can be
`CLAIMED` while both endpoints are `AUTHORITATIVE`: the cloud provider proves an
object was written and the framework proves a tool was invoked, and *nothing*
proves the second caused the first. Recording that edge as strong because its
endpoints are strong is the exact error this contract exists to prevent.

The sequence security cares about most is
`runtime_instance_to_input` (untrusted) → `input_to_authorization` →
`authorization_to_tool` → `tool_to_side_effect`: untrusted content reaching a
tool the agent was already authorized to use. Generic input sanitization does not
cover it, because the payload arrives in a tool *result* and drives an *allowed*
tool.

---

## 3. `evidence_class`

Five values, replacing 0.1's two:

| Class | Meaning | Typical source |
|---|---|---|
| `CLAIMED` | The agent or framework asserts the operation occurred | a tool-call span |
| `OBSERVED` | An independent sensor sees behaviour consistent with the claim | process / network telemetry, a tool gateway |
| `AUTHORITATIVE` | The system owning the resource records the state change | a cloud audit log, an IdP sign-in log |
| `ATTESTED` | An observer cryptographically binds its identity to the record | a signed evidence entry |
| `INFERRED` | The link is reconstructed from correlation, not directly recorded | time-window stitching |

**These are not a total order.** `CLAIMED → OBSERVED → AUTHORITATIVE` is ascending
strength *of origin*. `ATTESTED` is orthogonal — it describes integrity of the
*record*, not the origin of the *fact*. A signed record of a self-reported claim
is still a claim: emit `CLAIMED` and set `integrity_status`. Reserve `ATTESTED`
for when the binding of observer identity to record is the security property being
asserted. `INFERRED` is not weaker than `CLAIMED` on the same axis either — it is a
statement that *no one recorded this directly*.

Two rules that follow:

- **A detection verdict is never stronger than `INFERRED`.** A `security_finding`
  is a conclusion, not an observation. Its *inputs* carry the strength; the
  finding carries `weakest_supporting_class` so a chain of `CLAIMED` records
  cannot read as proof downstream.
- **`model_assisted` reconstruction never yields better than `INFERRED`.** The
  agent is the subject of measurement, never the measurer.

### 0.1 → 0.2 mapping

`evidence: "claimed"` → `CLAIMED`. `evidence: "observed"` → `OBSERVED`. The
lowercase field is retained and still validates; on a 0.2 record it may be
dual-written but must agree (rule E-6). The other three classes are new and have
no 0.1 spelling — which is the honest reading of 0.1: it could not express
authoritative, attested or inferred evidence at all.

---

## 4. The eight envelope properties

These are what OTel does not itself prove. Each is a span attribute *and* a field
in the sidecar record; the sidecar is authoritative where the two disagree,
because OTel attributes are flat primitives and lose structure.

| # | Property | Answers | Required when |
|---|---|---|---|
| 1 | `observer_identity` | Who is asserting this? | always (0.2) |
| 2 | `evidence_class` | How strong is it? | always (0.2) |
| 3 | `source_trust_domain` | From inside which boundary? | always (0.2) |
| 4 | `causal_link` | What does the parent edge mean, and how strong is *it*? | `parent_span_id` non-null |
| 5 | `reconstruction_method` | If not recorded, how was it arrived at? | `evidence_class: INFERRED` |
| 6 | `ground_truth_label` | What does the harness know the answer to be? | harness producers only |
| 7 | `integrity_status` | Can origin and post-hoc integrity be verified? | `evidence_class: ATTESTED` |
| 8 | `declared_blind_spots` | What does this observer know it cannot see? | first record per producer per run |

**1. `observer_identity`** — `{id, kind, version, key_id}`. `producer` (0.1)
answered "which component"; this answers "which *instance*, of what *type*, at
what *version*, signing with which key". `kind` is enumerated: `framework_sdk`,
`agent_sidecar`, `tool_gateway`, `host_sensor`, `kernel_sensor`, `network_proxy`,
`identity_provider`, `cloud_audit`, `static_analyzer`, `range_harness`,
`analysis_pipeline`, `human_analyst`.

**2. `evidence_class`** — section 3.

**3. `source_trust_domain`** — a free string, because domains are
deployment-specific, with a recommended vocabulary: `agent-process`,
`agent-host`, `host-kernel`, `network-edge`, `tool-gateway`,
`identity-provider`, `cloud-control-plane`, `range-harness`,
`analysis-pipeline`.

> **Corroboration rule:** two records corroborate each other **only if their
> `source_trust_domain` values differ.** A framework span and a sidecar in the
> same process agree by construction — that is not independent confirmation, and
> counting it as such inflates every corroboration metric downstream.

**4. `causal_link`** — `{parent_span_id, edge, evidence_class,
reconstruction_method, confidence, corroborated_by}`. `corroborated_by` lists
`span_id`s from a *different* trust domain that support this edge.

**5. `reconstruction_method`** — `{method, confidence, window_ms, notes}`.
`method` is one of `direct_record`, `propagated_context`,
`correlated_identifier`, `time_window`, `heuristic_match`, `model_assisted`,
`manual`. Recording *which* is what makes reconstruction fidelity measurable
instead of asserted: `propagated_context` and `correlated_identifier` survive
scrutiny, `time_window` degrades under concurrency, and the drop between them is
a number a conformance lab can report per runtime.

**6. `ground_truth_label`** — `{value, labeler, scenario_id, expected_outcome,
atlas_technique}`. Only a producer that *controls* the scenario may set it
(rule E-4). A detector writing its own ground truth is how evaluation harnesses
start grading their own homework.

**7. `integrity_status`** — `{status, algorithm, key_id, signature_ref,
prev_digest, verified_at, verified_by}`. `signed` means a signature exists;
`signed_verified` means a consumer checked it and it held, and only a verifier
may write it. `prev_digest` hash-chains an observer's records within a run, which
makes **record loss detectable** rather than silent — the failure mode that
fixtures pass and live execution exposes.

**8. `declared_blind_spots`** — array of `{area, reason, impact, affects_edges}`.
Recommended `area` tokens: `no_kernel_visibility`, `tls_payload_opaque`,
`no_cloud_audit_access`, `sampling_enabled`, `redacted_arguments`,
`pre_instrumentation_gap`, `no_child_process_attribution`, `cross_host_gap`.

> An **empty array is not "unknown"** — it is the positive claim *"no known blind
> spots"*, and it should be as hard to write as it sounds. Omitting the field on a
> producer's first 0.2 record in a run is a contract violation (rule E-3), not a
> default.

### Projection onto OTel span attributes

OTel attribute values are primitives or arrays of primitives, so nested objects
flatten to dotted keys and the structured detail survives only in the sidecar
record. Namespace: `evidence.*`.

| Property | Span attributes | Type |
|---|---|---|
| `observer_identity` | `evidence.observer.id`, `.kind`, `.version`, `.key_id` | string |
| `evidence_class` | `evidence.class` | string |
| `source_trust_domain` | `evidence.trust_domain` | string |
| `causal_link` | `evidence.causal.parent_span_id`, `.edge`, `.class`, `.confidence`, `.corroborated_by` | string, double, string[] |
| `reconstruction_method` | `evidence.reconstruction.method`, `.confidence`, `.window_ms` | string, double, int |
| `ground_truth_label` | `evidence.ground_truth.value`, `.scenario_id`, `.labeler` | string |
| `integrity_status` | `evidence.integrity.status`, `.algorithm`, `.key_id`, `.signature_ref`, `.prev_digest` | string |
| `declared_blind_spots` | `evidence.blind_spots` — `area` tokens only | string[] |

Blind-spot `reason` / `impact` / `affects_edges` and the full `causal_link` object
**do not survive** the projection. That is a known lossy edge of this design, and
it is the reason the sidecar record exists rather than shipping everything as
attributes.

Envelope fields that map onto *standard* GenAI attributes rather than
`evidence.*` — verify against the `VERSION` pin before relying on them:
`agent.id` → `gen_ai.agent.id`, `data.model` → `gen_ai.request.model`,
`data.tool` → `gen_ai.tool.name`, `data.input_tokens` →
`gen_ai.usage.input_tokens`, `data.output_tokens` → `gen_ai.usage.output_tokens`.

---

## 5. The format

Line-delimited JSON (**JSONL**): one record per line, append-only. Producers
append; consumers tail. A run is reconstructed by grouping on `run_id` and
walking `parent_span_id`. Full field definitions are in
`agent-trace-schema.json` (JSON Schema draft 2020-12).

Unconditionally required on every record: `schema_version`, `ts`, `producer`,
`run_id`, `span_id`, `kind`. On 0.2, additionally `evidence_class`,
`observer_identity` and `source_trust_domain`, plus the conditionally required
envelope properties in §4. On 0.1, additionally `evidence`.

`parent_span_id` is required in practice but nullable and not schema-required —
a root record legitimately has none, and a producer that emits it as `null`
rather than omitting it is stating "this is a root", which is information.
`agent`, `otel` and `data` are present when applicable; `data` is required only
where a `kind` defines a payload.

The schema stays deliberately within a conservative subset of draft 2020-12 —
`type`, `required`, `properties`, `additionalProperties`, `enum`, `const`,
`items`, `minItems`, `minLength`, `pattern`, `minimum`/`maximum`,
`format: date-time`, `allOf`, `anyOf`, `if`/`then`/`else`, and `$ref` to local
`$defs` — so it can be checked by a validator with no third-party dependencies.
`validate.py` in this directory is that validator, and it also enforces the
cross-line rules below, which JSON Schema cannot express. It reports any schema
keyword outside that subset rather than ignoring it, so the schema cannot drift
into constructs the validator silently fails to check.

### Normative cross-line rules

| Rule | Statement |
|---|---|
| **E-1** | `causal_link.parent_span_id` MUST equal the top-level `parent_span_id` when both are present. |
| **E-2** | A 0.2 record with a non-null `parent_span_id` MUST carry `causal_link`. *(schema-enforced)* |
| **E-3** | Every producer MUST carry `declared_blind_spots` on its first 0.2 record in a run. Later records may omit it; consumers treat the last-seen declaration for that observer as current. 0.1 records are exempt — the field does not exist in 0.1, and upgrading one substitutes the `pre_instrumentation_gap` declaration in §8. |
| **E-4** | `ground_truth_label` MUST only be set by an observer whose `kind` is `range_harness`. |
| **E-5** | `AUTHORITATIVE` requires `data.authoritative_ref`; `ATTESTED` requires `integrity_status.status` in `signed`/`signed_verified`; `INFERRED` requires `reconstruction_method`. *(schema-enforced)* |
| **E-6** | If both `evidence` and `evidence_class` are present they MUST agree (`claimed`↔`CLAIMED`, `observed`↔`OBSERVED`). |
| **E-7** | `span_id` MUST be unique within a `run_id`. |
| **E-8** | `parent_span_id`, when non-null, SHOULD resolve to a `span_id` in the same `run_id`. A dangling parent is reported as a warning, not an error: cross-run and cross-host parents are legitimate, and *silently* dropping them is worse than flagging them. |

---

## 6. Privacy / size rules (non-negotiable, unchanged from 0.1)

- Never put raw prompts or raw tool arguments in a record. Use `prompt_digest` /
  `args_digest` (algorithm-prefixed, e.g. `sha256:…`). `args_preview` is
  optional, truncated, and redactable.
- Digests over raw payloads keep the stream small and safe to publish, and let
  normalizer benchmark encoding without leaking content.
- Signatures never travel inline: `integrity_status.signature_ref` points at a
  detached signature or transparency-log entry.

---

## 7. How each repo uses it

| Repo | Role | Emits | Consumes |
|---|---|---|---|
| **attack range** | ground truth | `agent_run_start`/`end`, `retrieval`, `plan`, `model_call`, `tool_call`, `delegation`, `token_event`, `security_finding`; the only producer permitted to set `ground_truth_label` | — |
| **host sensor** | corroboration | `process_spawn`, `network_egress`, `file_write` (`OBSERVED`, `host-kernel`); `model_call`/`tool_call` (`CLAIMED`, via sidecar, `agent-process`) — and `declared_blind_spots` on both | — |
| **normalizer** | normalization | OCSF events + Sigma verdicts; scores per-field retention of the eight properties | all `kind`s, from **multiple** producers |
| **capability graph** | capability vs. reality | — | `agent.identity_ref`, `agent.instance_id`, `delegation`, `token_event` to confirm graph edges and mark them exercised |

The two trust domains the host sensor spans are the reason it can find anything: its
sidecar records are `agent-process`/`CLAIMED` and its host records are
`host-kernel`/`OBSERVED`, so the corroboration rule in §4 is satisfied and a
divergence between them is a real finding (`claim_observed_divergence`) rather
than an artifact of one component disagreeing with itself.

---

## 8. Compatibility and the 0.1 → 0.2 delta

`schema_version` is `"0.2"`. The schema accepts **both** `"0.1"` and `"0.2"`
lines, so a consumer upgrading to this file does not lose its existing corpus.
Additive fields within a version are allowed (consumers MUST ignore unknown
fields). Removing or retyping a field, or adding a `kind`, bumps the minor
version.

**Added**

- `evidence_class` (5 values) and the seven other envelope properties:
  `observer_identity`, `source_trust_domain`, `causal_link`,
  `reconstruction_method`, `ground_truth_label`, `integrity_status`,
  `declared_blind_spots`.
- `otel` binding object (`trace_id`, `span_id`, `parent_span_id`, `span_name`,
  `operation_name`, `semconv_version`).
- Kinds: `retrieval`, `plan`, `memory`.
- `agent.instance_id`.
- `data` additions: `principal` and `task_digest` on `agent_run_start`;
  `on_behalf_of` + `delegation_ref` on `delegation`; `on_behalf_of`, `jti`,
  `decision`, `op: deny` on `token_event`; `mediated_by` on `tool_call`; `pid`
  on `network_egress`; `weakest_supporting_class` on `security_finding`;
  `authoritative_ref` on `tool_call`, `token_event`, `file_write`.
- Digest fields are now pattern-checked (`^(sha256|sha512|blake3):[0-9a-f]{4,128}$`).
- Cross-line rules E-1 … E-8 and `validate.py`.

**Changed**

- `evidence` is no longer unconditionally required; it is required on `"0.1"`
  lines and **deprecated** on `"0.2"` lines in favour of `evidence_class`.
- `title` is now "Agent Evidence Envelope"; `$id` moves to `/v0.2/`.

**Tightened** — two changes that can reject a record 0.1 would have accepted:

- `data` is now *required* for every `kind` that declares required payload
  fields. In 0.1 those requirements sat under `properties.data`, so a record that
  omitted `data` entirely skipped them — a `tool_call` with no payload at all
  validated. That was a hole, not a feature.
- Digest fields are pattern-checked, so an unprefixed or non-hex digest now
  fails.

Both apply to 0.1 records too. The 0.1 fixtures in this directory validate
untouched, which is the evidence for that being a safe tightening on this corpus
and not a guarantee about every 0.1 record ever written; a repo re-syncing to 0.2
should run `validate.py` over its stored corpus before assuming otherwise.

**Removed** — nothing. No 0.1 field was deleted or retyped.

### Upgrading a 0.1 record to 0.2

Mechanical, and lossy in exactly one place — the upgrade cannot invent trust
domains or blind spots it never recorded:

| 0.2 field | Value on upgrade |
|---|---|
| `schema_version` | `"0.2"` |
| `evidence_class` | `upper(evidence)` |
| `observer_identity` | `{id: producer, kind: <mapped from producer>}` |
| `source_trust_domain` | `"unknown"` — **not** guessable from a 0.1 record |
| `causal_link` | `{parent_span_id, edge: "unspecified", evidence_class: <the record's own class>}` when `parent_span_id` is non-null |
| `declared_blind_spots` | `[{area: "pre_instrumentation_gap", reason: "upgraded from schema 0.1; blind spots were not declared", impact: "total"}]` |

An upgraded record must not be counted as corroborating anything: with
`source_trust_domain: "unknown"` the §4 corroboration rule cannot be satisfied.
That is the correct outcome, not a limitation to work around.

---

## 9. Fixtures

| File | Version | Demonstrates |
|---|---|---|
| `benign-run.jsonl` | 0.1 | Original 0.1 corpus, unmodified — validates against the 0.2 schema as `claimed`/`observed`. |
| `attack-run.jsonl` | 0.1 | Original 0.1 corpus, unmodified — confused-deputy run. |
| `fully-corroborated.jsonl` | 0.2 | The evidence chain witnessed across five trust domains — `agent-process`, `tool-gateway`, `host-kernel`, `identity-provider`, `cloud-control-plane` — with `OBSERVED` gateway and host records and `AUTHORITATIVE` IdP and cloud-audit records, plus a `range-harness` ground-truth label, a hash-chained sensor and one `ATTESTED` signed seal from `agent-host`. |
| `claimed-only.jsonl` | 0.2 | The *same attack* with only in-process instrumentation: every **chain** edge `CLAIMED`, `declared_blind_spots` populated throughout, no side-effect record at all, and the downstream verdict `INFERRED` by time-window stitching at confidence 0.41. |

The last two are a matched pair on scenario `gt-injection-delegation-01`: same
attack, same steps, two evidence postures. Diffing them is the demonstration —
the attack is identical, and what can be *proven* about it is not.

Validate with no third-party dependencies:

```
python3 validate.py *.jsonl
```
