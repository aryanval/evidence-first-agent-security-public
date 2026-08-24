# Agent Evidence Envelope

**A data contract, not a library.** One JSONL record per agent action, carrying the
security properties that make the action's provenance checkable: who is asserting
it, how strong the evidence is, which trust boundary it came from, what the causal
link to its parent actually means, and what the observer already knew it could not
see.

This directory is **canonical**. The tool repos in the portfolio vendor it by
**copying the folder**, not by importing it. That is the entire coordination
mechanism between them: they agree on this record shape and on nothing else.

Current version: **0.2** (see `VERSION`). The schema still accepts 0.1 records.

- **`SPEC.md`** — the normative document. Read this one.
- **`agent-trace-schema.json`** — JSON Schema, draft 2020-12.
- **`VERSION`** — envelope version and the pinned OpenTelemetry semantic-convention
  version, plus the provenance of that pin.
- **`validate.py`** — dependency-free validator: schema plus the cross-line rules
  JSON Schema cannot express.
- **`*.jsonl`** — fixtures, described below.

```
python3 validate.py *.jsonl          # stdlib only, Python 3.8+
```

## What it adds on top of OpenTelemetry

**It does not replace OTel, and it does not replace OCSF.**

OpenTelemetry is the execution substrate. The GenAI semantic conventions already
model an agent run as a span tree — `invoke_agent`, `chat`, `execute_tool`, plus
retrieval, plan and memory work — with MCP folded into the same vocabulary.
Building a parallel trace ecosystem would be the wrong move.

What OTel gives you is an execution record. What it does not give you is proof
that the recorded action caused the external side effect, or any way to say how
much of the record is self-reported. Those are security properties, and the
envelope is where they live — **eight of them**, carried both as `evidence.*` span
attributes and as this sidecar record:

`observer_identity` · `evidence_class` · `source_trust_domain` · `causal_link` ·
`reconstruction_method` · `ground_truth_label` · `integrity_status` ·
`declared_blind_spots`

`evidence_class` is the core of it: **CLAIMED**, **OBSERVED**, **AUTHORITATIVE**,
**ATTESTED**, **INFERRED** — attached not just to records but to each *edge* of
the chain

```
principal → delegation → agent identity → runtime instance → input
          → authorization → tool → side effect
```

so that a chain of self-reported records can never read as proof downstream.

OCSF sits on the other side: it is the security representation this feeds into.
The envelope's job is to make sure the evidence class and the causal edge survive
that transformation instead of being normalized away — which is a measurable
question, and one of the things the portfolio measures rather than assumes.

The GenAI conventions are **pre-stable**. `VERSION` pins the version this is built
against, records which operation names are actually pinned and which are not, and
states plainly that the pin was taken from working notes rather than re-fetched
from upstream. The contract does not exempt itself from its own doctrine.

## Fixtures

| File | Version | What it shows |
|---|---|---|
| `benign-run.jsonl` | 0.1 | The original corpus, unmodified. Still validates. |
| `attack-run.jsonl` | 0.1 | The original confused-deputy run, unmodified. Still validates. |
| `fully-corroborated.jsonl` | 0.2 | One run witnessed by **five trust domains** — framework, tool gateway, host kernel, IdP, cloud audit — with `OBSERVED` and `AUTHORITATIVE` edges, a hash-chained sensor and one `ATTESTED` signed seal. |
| `claimed-only.jsonl` | 0.2 | **The same attack** with only in-process instrumentation: every chain edge `CLAIMED`, `declared_blind_spots` populated throughout, the side effect never witnessed, and the verdict downgraded to `medium` because a tampered agent could have produced that exact record set. |

The last two are a matched pair on scenario `gt-injection-delegation-01`. Diffing
them is the point: the attack is identical and what can be *proven* about it is
not. Two details worth noticing —

- Even in the fully corroborated run, the `input_to_authorization` edge stays
  `CLAIMED`. No observer outside the agent process can show that the retrieved
  content is what drove the authorization request. "Fully corroborated" never
  means every edge is proven, and the finding reports
  `weakest_supporting_class: CLAIMED` because of it.
- The cloud audit record arrives with `lag_ms: 41000`. Authoritative evidence
  routinely lands after the moment a detection had to fire.

## Vendoring

Copy the whole folder into the consuming repo at `schemas/agent-trace-schema/`
and record the version you speak in that repo's README. Changes happen **here
first**; the version bumps; repos re-sync when they choose to.

**Repos on 0.1 need to re-sync this folder to pick up 0.2.** They keep working
until they do: 0.2 removed and retyped nothing, and the 0.1 fixtures in this
directory validate against the 0.2 schema untouched — which is the test of that
claim rather than the assertion of it. Two rules did get *tighter* (`data` is now
required where a `kind` defines a payload, and digests are pattern-checked), so
run `validate.py` over a stored 0.1 corpus before assuming it passes clean;
`SPEC.md` §8 has the detail. The upgrade path for stored 0.1 records is
in `SPEC.md` §8, including the one thing it cannot recover: a 0.1 record has no
trust domain, so an upgraded record is never counted as corroborating anything.

No imports, no shared package, no cross-repo dependency. If this folder and a
vendored copy disagree, this folder is right.
