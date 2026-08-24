# Evidence-First Security for Autonomous Agents

**An agent's identity, authorization decision, or audit log is only as trustworthy as the evidence connecting it to what the agent actually caused to happen.**

The industry is converging fast on an agent control plane: give agents first-class
identities, constrain their authority, mediate sensitive actions, record execution,
govern access over time. NIST is scoping agent identification, authorization, and
non-repudiation; cloud providers expose agent-identity constructs and mediate tool
actions with deterministic policy outside agent code; OpenTelemetry and OCSF are
standardizing the records everything downstream consumes.

This work sits one layer beneath those controls, on the problem they all depend on and
none of them is the answer to: the **evidence gap** between an agent's identity and
what it actually caused. Identity can be correct while causality is wrong. A framework
trace can say a tool ran when the side effect never occurred. A cloud log can prove a
credential changed a resource while never explaining which agent, delegation, or
untrusted input set it in motion. Normalization can stay syntactically valid while
dropping the provenance security needs.

> **The model may stay probabilistic. The security boundary around it should become more provable than the model itself.**

**The standards change this work argues for is filed as
[`ocsf/ocsf-schema#1738`](https://github.com/ocsf/ocsf-schema/issues/1738)** —
an optional `caused_by` on the `ai_operation` profile, so that a resource
owner's record of a change can name the agent tool call it is attributed to.
Filed without a co-sponsor; anyone who owns a resource-side audit record and
would have to populate the attribute is exactly who it needs.

---

## What is in this repository

| File | What it is |
|---|---|
| [`evidence-first-agent-security.pdf`](evidence-first-agent-security.pdf) | The argument, the measured results, and the standards change they motivate. Read this first. |
| [`EXHIBIT-A.md`](EXHIBIT-A.md) | Two real records from one run, arguments redacted: a tool call and the platform's record of the change it caused, with the join visibly absent. |
| [`vendor-matrix.md`](vendor-matrix.md) | Ten vendor products across six layers, every cell sourced to a dated document, every unanswered question marked *not established* rather than inferred. |
| [`schemas/agent-trace-schema/`](schemas/agent-trace-schema/) | The evidence envelope: specification, JSON Schema, a dependency-free validator, and fixtures. |
| [OCSF issue #1738](https://github.com/ocsf/ocsf-schema/issues/1738) | The schema change this work proposes, filed 24 August 2026. |
| [`PROVENANCE.md`](PROVENANCE.md) | Commit hashes and dates proving the pre-registration existed before the runs. |
| [`WITHHELD.md`](WITHHELD.md) | What is deliberately not published, and a SHA-256 manifest of it so the withheld tree can be shown unaltered later. |

## Why "AI vs. AI" is the wrong fight

AI belongs in defense — for triage, correlation, anomaly discovery, investigation. The
mistake is making a *second probabilistic model* the final arbiter of a fact that
stronger evidence could establish. An attacker can probe an agent until one attempt
lands; a defender often needs a reliable account of *every* high-impact action. Meeting
a cheap, imprecise offense with an equally probabilistic defense is the wrong side of
that asymmetry.

The alternative is not a cleverer model. It is to **mediate authority at observable
boundaries** and make the resulting actions carry enough independently verifiable
provenance that the enterprise never has to trust the agent's own explanation — and to
*measure*, reproducibly, where that provenance holds and where it breaks. To be explicit:
this is not "AI detecting AI." The instruments are deterministic; the agent is the
subject of measurement, never the measurer.

## The missing primitive: action provenance

A security-sensitive agent action is a causal chain:

```
principal → delegation → agent identity → runtime instance → input → authorization → tool → side effect
```

Every arrow is a claim of causality. The goal isn't to pretend every edge is directly
observable — it's to state **what class of evidence supports each edge** and how much
uncertainty remains. Five classes, in ascending strength:

| Class | Meaning | Example |
|---|---|---|
| **Claimed** | The agent or framework asserts the operation occurred | a tool-call span |
| **Observed** | An independent sensor sees behavior consistent with the claim | process / network telemetry |
| **Authoritative** | The system owning the resource records the state change | a cloud audit log |
| **Attested** | An observer cryptographically binds its identity to the record | a signed evidence entry |
| **Inferred** | The link is reconstructed from correlation, not directly recorded | time-window stitching |

## Four instruments, and the experiment that made them agree

Four instruments were built, each measuring a different failure mode in the
action-evidence chain. Separately, each produced a finding. The step that mattered was
forcing all four to describe the same event at the same time — because an instrument
that is never contradicted is never tested.

| Stage | Question it answers | What the joint run showed |
|---|---|---|
| **Ground truth** | Is defense evaluation reproducible against a known attack? | Yes, and single-run evaluation misreports the hard vector outright. |
| **Corroboration** | Does an independent observer confirm the claim? | Yes for occurrence; never for causation — the observer says so itself. |
| **Standardization** | What survives the path to a security schema? | Most of it. The residue is small, specific, and namable. |
| **Capability vs. reality** | Does standing authority match what was exercised? | Partly — and where a credential cannot distinguish two resources, nothing downstream can either. |

The instruments themselves are not published. They share one coupling — a versioned
evidence envelope over OpenTelemetry, vendored per repository, the file format being the
only dependency — and that envelope **is** published here, because it is the contract a
reader would need to implement against or argue with.

## Making fidelity falsifiable

A single "AI safety score" would hide exactly the distinctions this work exposes.
Fidelity is a **vector**, reported per action class and per observer:

| Metric | What it means |
|---|---|
| Capture coverage | fraction of ground-truth actions that produced usable records |
| Attribution precision / recall | when evidence names Agent A, how often A was responsible — and of A's actions, how many were attributed to it |
| Causal completeness | fraction of expected edges reconstructable from input through side effect |
| Delegation completeness | ability to reconstruct human→agent and agent→agent authority lineage |
| Independent corroboration | fraction of important claims supported outside the asserting component's trust domain |
| Normalization retention | fraction of security-relevant evidence preserved through transformation |
| Integrity / attestation | whether origin and post-generation integrity can be verified |

## The experiment, and what it cost to run it honestly

A legitimate principal gives an agent a benign task. Fulfilling it requires reading a
record containing attacker-supplied text. That text is relayed onward, and a second
agent takes an action — using a tool it is genuinely permitted to use, with a credential
that is genuinely valid, against a resource it is genuinely allowed to reach. **The only
thing wrong is why.** Run under four control regimes, with parameters and expected
results registered before the run, and scored exactly once.

Two campaigns have now run under that protocol. Three rules made the results worth
reading, and each cost a finding:

* **Parameters fixed and registered before the run.** Sample size, the confidence
  criterion, and the expected outcome of every arm were committed first — and several of
  those expectations were wrong, which is the only reason the results mean anything.
* **Scored exactly once**, with no arm extended after results were seen.
* **The prettiest finding gets audited hardest.** One campaign was voided outright when
  an external reviewer showed an observer had never been invoked — and the discarded
  verdict was the *favourable* one. A later arm was discarded when the best-looking
  control result turned out to be an artifact of the measuring instrument rather than
  the control.

The results, the surviving gap, and the minimal standards change that would close it are
in the PDF.

---

*Status legend: **Finding** — project-reported, scoped to what was tested, not
independently audited.*

**Method, environment, fleet topology, scenario construction, payload text, defense
implementation internals and reproduction steps are deliberately withheld.** See
[`WITHHELD.md`](WITHHELD.md), which also carries a SHA-256 manifest of the withheld tree
so that what was held back can later be shown to be unaltered.
