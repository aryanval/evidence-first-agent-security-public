# PARITY — would a PANW-scale org lose this today?

**All sources fetched 2026-08-23.** Every claim here is reasoned from published
documentation. **No vendor product was deployed, configured, or tested.** Where a
document does not answer a question, that is recorded as *not established* rather
than inferred.

This file answers one question per edge: *does a named enterprise product's
record contain the field?* It is deliberately separate from the gap table, which
answers *does a standard define a home for it?* A field can be shipped by a
vendor and absent from every standard — and that combination is the most
important row in this document.

---

## Executive answer

**Partly, and the part that survives is narrower than the report first claimed.**

Microsoft ships more of this than I expected, including a production
implementation of a field I had classified as a gap. Palo Alto ships the
mediator architecture the design argues for. Neither, on published evidence,
binds an individual tool call to a **third-party resource owner's** record of the
side effect — which is what H1 claims, and which is why the claim survives in a
narrowed form rather than being withdrawn.

Ten vendors are now examined, across six layers — AI firewall, endpoint, cloud
posture, network broker, identity, and LLM observability. Two of the four added
on 2026-08-23 narrow the claim further, and both were fetched because they might:

- **Datadog** records the tool call as a first-class span kind, with a name and
  the LLM-generated call arguments. That is `data.tool` and `data.args_digest`
  shipping in a product, and it moves those rows off *not established*.
- **Okta Cross App Access** carries a delegation chain — `sub` for the human,
  a nestable `act` for each agent — **across an application boundary**, which is
  the boundary every other vendor's record stops at. It is the closest anything
  examined comes to crossing it.

Neither closes H1. Datadog's tool span records what the agent *called* and what
came back, which is the agent's account of the side effect and not the resource
owner's. Okta's chain propagates **who** across the boundary and never **which
call caused which recorded change** — its own audit event is an authorization
grant, not a record of the effect. The gap is still the binding, and it is still
at the boundary.

---

## 1. Palo Alto Networks — Prisma AIRS

### 1.1 What it is, architecturally

Prisma AIRS is an AI Runtime Firewall with an **API Intercept** and a **Prisma
AIRS MCP Server**. The MCP server "intercept[s] tool invocations, perform[s]
security analysis, and then return[s] a verdict on whether a threat was
detected", and "sits in the path of tool calls".

**This is the mediator archetype the design argues for**, and it is the right
architectural answer: a tool call witnessed at a boundary outside the agent's
process is OBSERVED, not CLAIMED, and does not depend on a compromised agent
choosing to report it. Palo Alto is not missing the problem. It is selling the
control layer.

Source: <https://docs.paloaltonetworks.com/content/techdocs/en_US/ai-runtime-security/activation-and-onboarding/prisma-airs-mcp-server-for-centralized-ai-agent-security/understanding-the-prisma-airs-mcp-server>

### 1.2 What the scan log records

Documented fields: `scan_id`, `report_id`, API Key, `Profile ID`, `Profile Name`,
`Application Name`, `Model Name`, prompt/response detection types, `verdict`,
action taken; and in the JSON example `timestamp`, `app_name`, `threat_type`,
`severity`, `user_ip`, `session_URL`.

The API *response* additionally carries `tr_id`, described as "a transaction ID
field included in the API request payload that helps track the request" — a
**caller-supplied** correlation identifier.

| question | answer on published evidence |
|---|---|
| caller-supplied correlation id in the **scan log**? | **not documented.** `tr_id` appears in the API response contract; the scan-log field list does not include it |
| individual **tool call** recorded (name, arguments)? | **not documented for API Intercept.** The MCP Server docs say logs "track tool invocations, security verdicts, and any detected threats", without specifying whether tool names or arguments are among the recorded fields |
| any field referencing a **third-party audit record**? | **absent.** `session_URL` links into Strata Cloud Manager; nothing references an external resource owner's log |

Sources:
<https://docs.paloaltonetworks.com/ai-runtime-security/administration/detect-and-alert-on-malicious-traffic/ai-runtime-security-intercept-scan-logs> ·
<https://pan.dev/prisma-airs/api/airuntimesecurity/usecases/>

### 1.3 Assessment

The mediator exists and tool invocations are logged. What is **not established
from public documentation** is whether a recorded invocation can be tied to the
record a third-party platform writes for the resulting side effect. That is not a
criticism of the product — it is the boundary the whole finding is about, and it
is a boundary no single vendor can close alone.

**Not established** is the honest verdict here, not *absent*. The AIRS API
Reference and SDK docs were not exhaustively read; a definitive claim would
require them.

---

## 2. Microsoft — Purview audit for Copilot and AI applications

This is the finding that most qualifies the report, and it goes against the
experiment's own interest.

### 2.1 `AccessedResources` is a real interaction-to-resource binding

A Purview `CopilotInteraction` audit record carries `AccessedResources`:
"References to all resources (files, documents, emails, etc.) which Copilot
accessed in response to the user's request", each with `ID`, `SiteUrl`,
`ListItemUniqueId`, `Type`, `Name`, `SensitivityLabelId`, **`Action`** ("read",
"create", "modify"), `PolicyDetails`, and **`Status`** ("success" or "failure").

That binds an AI interaction to the specific resources it touched, the action
performed on each, and whether it succeeded. **It is materially more than any
standard offers**, and more than I expected to find.

### 2.2 `XPIADetected` ships a field I had classified as a gap

`AccessedResources.XPIADetected` is "a boolean that denotes whether there was an
XPIA (Cross Prompt Injection Attack) detected from a particular resource which
Copilot accessed."

This is a per-resource untrusted-content marker in production. The gap table
classifies `data.content_trust` as CAPTURABLE-NOT-CAPTURED (ours) on the grounds
that OCSF #1640 only *proposes* `is_untrusted_content`. **Microsoft has shipped
the capability that proposal describes.** The row stands as "ours" — it is still
our producer that fails to emit it — but the parity answer for that field is
that a PANW-scale org on Microsoft 365 would **not** lose it.

### 2.3 Entra Agent ID carries identity and instance

The audit schema was extended with `auditActivityPerformer` (`agentType`,
`appId`, `blueprintId`), and `blueprintId` correlates "an agent identity
(instance) back to its blueprint (template)". Purview additionally states that
supported interactions include "agent-to-human, human-to-agent, **agent-to-tools**,
and agent-to-agent".

This corroborates the LAB-SCOPED verdicts on H2 (instance identity) and H3
(delegation initiator) from a second vendor.

### 2.4 The three limits that keep H1 alive

1. **Scope is the Microsoft estate.** Resource identifiers are M365-native —
   `fileId`, SharePoint `ListItemUniqueId`, Outlook message ID. A record written
   by a third-party SaaS platform, an S3 bucket or a partner API does not receive
   an `AccessedResources` entry. The golden attack's terminal action is a share to
   an **external** destination; that is precisely the case outside this boundary.
2. **Granularity is the interaction, not the tool call.** `AccessedResources`
   lists resources accessed "in response to the user's request" — per
   prompt/response pair. An interaction containing several tool calls does not
   separate which call touched which resource, which is the distinction H1 turns
   on.
3. **It is the AI platform's account, not the resource owner's independent one.**
   Copilot's host records what Copilot accessed. Within Microsoft 365 the host and
   the resource owner are the same organisation, so this is strong; it is not two
   trust domains agreeing.

Sources:
<https://learn.microsoft.com/en-us/purview/audit-copilot> ·
<https://learn.microsoft.com/en-us/entra/agent-id/sign-in-audit-logs-agents> ·
<https://learn.microsoft.com/en-us/purview/ai-agent-365>

---

## 3. Google — Vertex AI Agent Engine / Agent Builder

Agent execution logging is `stdout`/`stderr` routed to Cloud Logging under the log
IDs `reasoning_engine_stdout` and `reasoning_engine_stderr`, plus Python logging
and the Cloud Logging client. Entries carry severity, custom payload, and
**`trace`/`span` fields "for correlating across logs"**, plus labels. Agent
Builder audit logs use `discoveryengine.googleapis.com`; the Gemini Enterprise
Agent Platform uses `aiplatform.googleapis.com` with resource type
`audited_resource`.

| question | answer on published evidence |
|---|---|
| individual **tool call** recorded (name, arguments)? | **not documented.** The logging guide describes routing an agent's own output; no tool-call instrumentation is described |
| caller-supplied correlation id? | **partially.** `trace`/`span` exist and are explicitly for correlating across logs — but across *Cloud Logging* entries |
| link to the **resource owner's** audit record? | **not documented.** Nothing ties a trace/span to a Cloud Audit Log entry for the resource touched. The guide additionally notes Cloud Logging "is not supported for child resources" including sessions and memory bank |

Sources:
<https://docs.cloud.google.com/agent-builder/agent-engine/manage/logging> ·
<https://docs.cloud.google.com/gemini-enterprise-agent-platform/machine-learning/general/audit-logging>

Google has the *substrate* for correlation — trace and span are the right
primitives — and no documented use of it to bind an agent action to the audit
record of the resource that action changed.

## 4. Wiz — AI-SPM and the Runtime Sensor

Wiz discovers AI estate including **Model Context Protocol (MCP) connections**,
and its Runtime Sensor "captures every DNS query a workload makes, every active
connection to another container, database, or external service, in real time."
Runtime Monitoring watches for drift and suspicious behaviour, such as "an AI
workload hosting a rogue agent or attempting to communicate with a suspicious DNS
destination."

| question | answer on published evidence |
|---|---|
| individual **tool call** recorded? | **no.** The sensor's unit is the workload connection — DNS, socket, container-to-container — not the agent's tool invocation |
| link to the resource owner's record? | **no** |
| relevance | **This is the strongest available confirmation of the finding's shape from a second sensor class.** Wiz sees the *connection* the tool call produced. It does not see the tool call, and nothing joins the two |

Wiz's position here is the same as a kernel EDR's, and for the same structural
reason: a sensor watching the network or the process table observes the *effect*
with excellent fidelity and has no visibility into the agent-internal decision
that caused it. That is not a product limitation — it is what that vantage point
can see.

Source: <https://www.wiz.io/solutions/runtime-sensor> ·
<https://www.wiz.io/blog/wiz-ai-spm-secures-ai-agents>

## 5. CrowdStrike — Falcon AIDR and the endpoint sensor

Fetched 2026-08-23, closing a limit this document previously declared.

Falcon AIDR "maps relationships between users, prompts, models, agents, MCP
servers, and cloud workloads, including coding agents and desktop AI apps running
natively on the endpoint", and offers "comprehensive AI event logs containing full
prompt and response content, AI model versions, users, and more". Falcon Exposure
Management's AI Discovery "automatically discovers AI applications, agents, LLM
runtimes, MCP servers, and development tools running across endpoints".

| question | answer on published evidence |
|---|---|
| individual **tool call** recorded (name, arguments)? | **not established.** The product page, the launch blog and the press release all describe prompt/response content, model versions and users. None names a tool-call field. A secondary summary describes an MCP proxy through which "every agent tool call is observed and policy-enforced"; **no page I fetched carries that sentence**, so it is recorded here as unverified rather than quoted as vendor documentation |
| caller-supplied correlation id? | **not documented** |
| link to a **third-party** resource owner's record? | **not documented.** No fetched page mentions correlating an agent action with an external platform's audit record |

The endpoint-sensor property the report's P1-ceiling argument relies on is
unchanged, and Wiz corroborates it from a second sensor class: **a kernel or
network sensor closes the observation question and leaves the attribution
question untouched.** It sees `/bin/sh` under a Python pid, or a socket to a
destination, and has no way to ask which tool call asked for it. What has changed
is that CrowdStrike is no longer only an endpoint sensor in this analysis — AIDR
is an AI-layer product, and the honest verdict for its tool-call granularity is
*not established*, not *absent*.

Sources:
<https://www.crowdstrike.com/en-us/platform/falcon-aidr-ai-detection-and-response/> ·
<https://www.crowdstrike.com/en-us/blog/new-crowdstrike-innovations-secure-ai-agents-govern-shadow-ai/> ·
<https://www.crowdstrike.com/en-us/press-releases/crowdstrike-establishes-the-endpoint-as-the-epicenter-for-ai-security/>

Palo Alto Cortex was not separately fetched and is argued from the same class
property, as before.

---

## 6. Cisco — AI Defense

Cisco publishes MCP-specific runtime documentation: the AI Defense user guide
contains a **"MCP Runtime Guardrails"** page (last updated 2026-08-18) alongside
"Guardrails and Rules", "Policies", and AI Runtime Events.

**The documentation body could not be retrieved.** `securitydocs.cisco.com`
serves its `.dita` pages as a client-side-rendered shell — a fetch returns
navigation, login prompt and footer, no content — and `cisco.com`'s AI Defense
data sheet and AI Runtime pages both return HTTP 403 to a plain fetch. A search
index attributes to Cisco the claim that runtime protection "extends to MCP
traffic, inspecting agent actions and tool calls in real time", enabling detection
of "unauthorized tool usage, harmful action chains, memory poisoning attempts".
**That sentence was not obtained from a page I read**, and this document does not
treat search-index text as vendor documentation.

| question | answer on published evidence |
|---|---|
| individual **tool call** recorded? | **not established** — pages exist and were not retrievable |
| caller-supplied correlation id? | **not established** |
| link to a third-party resource owner's record? | **not established** |

Cisco is therefore the weakest-evidenced row in this document, and it is marked
that way rather than filled in from a snippet. On architecture alone it belongs
with Palo Alto in the mediator class; whether its record binds a call to an
external audit row is unknown to me.

Source (titles and dates only, body not retrieved):
<https://securitydocs.cisco.com/docs/ai-def/user/168860.dita>

---

## 7. Zscaler — AI Broker and AI Protect

Zscaler's AI Broker "sits inline on these communications, enforcing fine-grained
access controls across every agent interaction", explicitly covering "emerging
protocols like MCP (Model Context Protocol) and A2A (Agent-to-Agent)". The
integrated Agent Registry "gives your team a clear, governed view of what each
agent is permitted to access and enforces it in real time". On visibility the
strongest published claim is: "When an agent touches your data, you'll know
exactly who authorized it, what it accessed, and where that data went."

| question | answer on published evidence |
|---|---|
| individual **tool call** recorded? | **not established.** Inline inspection of MCP and A2A is claimed; no field list is published |
| caller-supplied correlation id? | **not documented** |
| link to a third-party resource owner's record? | **not documented.** "Where that data went" is the broker's own account of the egress it mediated, not the receiving platform's record of what it stored |

This is the same architectural position as Palo Alto's — a mediator in the path —
and the same documentary position: the vantage point is right, the record's
contents are not public. Available material is product marketing; Zscaler's
technical documentation portal was not reached.

Sources: <https://www.zscaler.com/blogs/product-insights/how-zscaler-secures-the-agentic-ai-era> ·
<https://www.zscaler.com/blogs/product-insights/ai-traffic-security-mcp-a2a-websockets>

---

## 8. Okta — Cross App Access (XAA), the identity layer

**This is the closest anything examined comes to crossing the boundary, and it is
the second finding in this document fetched specifically because it might demote
H1.**

XAA is an extension of OAuth/OIDC built on token exchange. Okta's position: both
"the human (the `sub` claim) and the agent (the `act` claim) both travel in the
token", the `act` claim is **nestable**, so "if Service B then calls Service C on
behalf of the user, the delegation chain grows". Okta describes this as
maintaining "a chain rather than a single principal", extending "agent to agent to
service, so authority narrows at every hop", and preserving "the lineage of
custody, preventing identity erasure". The IdP emits "explicit, structured events
(`app.oauth2.token.grant.id_jag`) tied to an immutable transaction identifier".
The developer documentation adds that "the resource authorization server validates
the ID-JAG and issues a short-lived, scoped access token", with "audit logging for
every XAA request".

| question | answer on published evidence |
|---|---|
| individual **tool call** recorded? | **no.** The unit is a token grant / authorization request, not a tool invocation |
| caller-supplied correlation id crossing a vendor boundary? | **yes, for identity.** The `act` chain and the ID-JAG travel from requesting app to resource app — a genuinely cross-domain propagation |
| link to the resource owner's record of the **side effect**? | **no.** The IdP records that authority was granted. What the resource app then did, and which of several calls did it, is not in that record; Okta's material does not specify what the resource app logs |

**Why this does not demote H1, stated against our own interest.** XAA is the
strongest counter-candidate in this document, because it is the only mechanism
examined that deliberately crosses an organisational boundary carrying
caller-supplied context. But it carries **who**, not **what caused what**. Two
tool calls made under the same ID-JAG are indistinguishable in the resource app's
record; the chain narrows authority, it does not attribute a specific recorded
state change to a specific invocation. H1 asks for the second thing.

This does strengthen the delegation rows considerably: an org on Okta XAA would
**not** lose the delegation initiator, and would keep it across a vendor boundary
rather than only within one estate — better than the AWS STS `sourceIdentity`
answer already recorded.

Sources: <https://www.okta.com/blog/ai/okta-securing-ai-agent-identity/> ·
<https://developer.okta.com/docs/concepts/xaa/>

---

## 9. Datadog — LLM/Agent Observability, the telemetry layer

Not a security vendor, included because it is the layer that most directly
records the field H1's neighbours ask for, and because the parity question is
"would an org lose this", not "would a security product supply it".

Agent Observability defines seven span kinds, of which **`tool` is one**:
a tool span represents "a call to a program or service where the call arguments
are generated by an LLM". A trace is "a root workflow span with nested LLM, task,
tool, embedding, and retrieval spans". Tool spans take `name`, `session_id` and
`ml_app`, and are enriched via `LLMObs.annotate()` with `input_data`,
`output_data`, `metadata`, `metrics`, `tags` and `cost_tags`. `LLMObs.export_span()`
extracts "span and trace IDs" for joining evaluations. For MCP specifically, an
SDK setting "adds an argument to every MCP server tool requesting that the calling
model describe why it chose to call the tool. The intent is recorded on the tool
span."

| question | answer on published evidence |
|---|---|
| individual **tool call** recorded (name, arguments)? | **yes.** `name` plus `input_data` — the LLM-generated call arguments — on a first-class `tool` span kind |
| caller-supplied correlation id? | **within the trace.** span/trace ids join spans to each other and to evaluations; no documented mechanism propagates a caller-supplied id **to** the external service |
| link to the resource owner's record? | **no.** `output_data` is what the tool returned to the agent. That is the agent's account of the side effect, from inside the agent's own process |

**This moves two rows off "not established".** `data.tool` and `data.args_digest`
have a shipping home in a widely deployed product. It also sharpens H1 rather than
weakening it: Datadog records the call *and* its result and still cannot bind
either to the platform's own row, because both ends of its record are on the
agent's side of the boundary. The richest tool-call telemetry examined is still
single-domain.

Sources: <https://docs.datadoghq.com/llm_observability/terms/> ·
<https://docs.datadoghq.com/llm_observability/instrumentation/sdk/>

---

## 10. AWS

Covered in the report's own citations rather than repeated here: CloudTrail
eventVersion 1.11 generates every identifier itself and carries no caller-supplied
causal reference, while STS `sourceIdentity` propagates a delegation initiator
across role chaining. Bedrock AgentCore's authorization surface is modelled by the
portfolio's static-analysis instrument; its runtime records were not examined for
this document.

---

## 11. Per-edge parity verdicts

| edge / field | gap class | would a PANW-scale org lose it today? |
|---|---|---|
| `tool_to_side_effect` → `authoritative_ref.caused_by_span` / `.caused_by_method` | **STRUCTURAL** | **Yes, across a vendor boundary.** No, for resources inside Microsoft 365, where `AccessedResources` binds interaction→resource. Not established for AIRS, Cisco, Zscaler |
| `causal_link.edge`, `causal_link.evidence_class` (×7 edges) | EXTENSION CANDIDATE | **Yes.** No vendor record examined carries an edge's *meaning* or an evidence class attached to the edge rather than its endpoints |
| `agent.instance_id` | CAPTURABLE (cost) | **No.** Entra `blueprintId` correlates instance→blueprint; OCSF `ai_agent.instance_uid` defines it |
| `principal_to_delegation` (×4), `data.delegation_ref`, `data.decision`, `data.jti` | LAB-SCOPED | **No, and less so than previously recorded.** AWS STS `sourceIdentity` propagates the initiator across role chaining; **Okta XAA's nestable `act` claim propagates the whole chain across an application boundary**, which is strictly more than the AWS answer |
| `data.content_trust` | CAPTURABLE (ours) | **No, on Microsoft 365.** `AccessedResources.XPIADetected` ships this per resource |
| `data.tool`, `data.args_digest` | CAPTURABLE (cost) | **No, on an LLM-observability stack.** Datadog's `tool` span carries `name` and `input_data` — the LLM-generated call arguments. Changed from *not established* on 2026-08-23 |
| `data.mediated_by` | CAPTURABLE (cost) | **Not established.** Four vendors sit in the path (AIRS, Cisco, Zscaler, CrowdStrike's claimed MCP proxy); none publishes whether the mediator's identity is a field on the record |

---

## 12. What this does to the verdict

**H1 is not withdrawn, but it is narrower than §2 of the report states**, and the
report should be read with this file beside it:

> Nothing binds an individual tool call to a **third-party resource owner's**
> record of the side effect. Within a single vendor's estate — Microsoft 365
> specifically — an interaction-level binding to accessed resources exists today
> and is richer than any standard provides.

The gap is therefore **at the boundary, not inside it**. Each vendor can and does
reconstruct causality within its own estate; nothing lets that reconstruction
cross into the audit log of a system a different company owns. That is what a
standard is for, and it is why the minimal change proposed in the report targets
OCSF rather than any product.

**This is a better result than the one it replaces.** "Here is the gap, here is
who has already closed part of it, and here is what the standard still needs so
it works across vendors" is a defensible position. "Nobody has noticed this"
would not have been, and would have been false.

---

## 13. Declared limits of this document

- Documentation only. Nothing was deployed, and no product's actual log output
  was inspected. A vendor may record fields its public docs omit.
- The AIRS API Reference and SDK docs were not read exhaustively; §1 is marked
  *not established* rather than *absent* for that reason.
- Google, Wiz: documentation read on 2026-08-23; no product deployed.
- **Cisco could not be read at all.** `securitydocs.cisco.com` renders its pages
  client-side and `cisco.com`'s AI Defense pages return HTTP 403 to a fetch. The
  §6 row rests on page titles and dates only. A claim about MCP tool-call
  inspection circulates in search-index text; it is excluded here because I did
  not obtain it from a page.
- **Zscaler is evidenced by product marketing only.** Its technical
  documentation portal was not reached; no field list was found.
- **CrowdStrike** was fetched for this revision, closing the previous version's
  declared gap. Cortex was not, and remains argued from class delivery semantics.
  The "every agent tool call is observed" MCP-proxy claim appears in a secondary
  summary and in none of the three CrowdStrike pages fetched.
- **Datadog** is documented from its concepts page and SDK reference; no
  deployment, and the OTel-instrumentation path was not separately read.
- **Okta** is documented from one vendor blog and the XAA concepts page. The
  developer docs do not enumerate ID-JAG claim names; `sub` and `act` are quoted
  from the blog. What a resource app logs after validating an ID-JAG is
  unspecified in both, and is the question that would matter most.
- Bedrock AgentCore runtime records were not examined.
- Microsoft's `AccessedResources` was read from the Purview schema table, not
  observed in a live tenant.
- Fetched 2026-08-23. Vendor documentation changes; a claim here is defensible
  for as long as its source says what it says and no longer.

---

## 14. The grid

One row per vendor, one column per question. **Every cell is documentation-derived
and dated 2026-08-23.** "Not established" means the published documentation does
not answer, and is deliberately distinguished from "absent".

| vendor / layer | records the tool call? | caller-supplied correlation id? | links to a **third-party** resource owner's record? |
|---|---|---|---|
| **Palo Alto** Prisma AIRS (MCP Server) | **yes** — intercepts tool invocations; field detail not documented | `tr_id` in the API contract; not in the documented scan-log fields | **no** |
| **Microsoft** Purview + Entra Agent ID | interaction-level, with `AccessedResources` per resource | agent/blueprint identity, not per call | **within M365 only** — richest of any examined |
| **Google** Vertex AI Agent Engine | not documented | `trace`/`span`, across Cloud Logging | not documented |
| **Wiz** Runtime Sensor / AI-SPM | **no** — unit is the workload connection | n/a | **no** |
| **CrowdStrike** Falcon AIDR + sensor | **not established** at AI layer; **no** at endpoint layer — unit is the process | not documented | not documented |
| **Cisco** AI Defense | **not established** — docs not retrievable | not established | not established |
| **Zscaler** AI Broker / AI Protect | **not established** — inline on MCP and A2A, no field list | not documented | **no** — its own account of the egress it mediated |
| **Okta** Cross App Access | **no** — unit is the token grant | **yes, for identity** — `sub` + nestable `act`, across the boundary | **no** — records that authority was granted, not what was done with it |
| **Datadog** Agent Observability | **yes** — `tool` span kind, `name` + `input_data` | span/trace ids, within the trace | **no** — `output_data` is the agent's own account |
| **AWS** CloudTrail | n/a — resource-owner side | **no**, all identifiers self-generated | n/a |

**The column that matters is the third, and it is still empty except inside a
single vendor's own estate.** Ten vendors across six layers; the one mechanism
that crosses an organisational boundary carrying caller-supplied context — Okta's
`act` chain — carries identity and not causality. Several vendors reconstruct
causality within their own boundary. Nothing carries that reconstruction across
one, and the only thing that crosses carries something else.

---

---

# Addendum — 2026-08-24 — the questions campaign 3 adds, and their status

**Not yet examined. No vendor documentation was fetched for this addendum**, and
nothing below is a finding. It is recorded now so the questions exist in writing
before anyone goes looking for answers that flatter the thesis — the same reason
the pre-registrations exist.

Campaign 3 asks three things of a vendor record that the matrix above does not:

| # | question | why campaign 3 raises it | status |
|---|---|---|---|
| P-4 | Does the record bind an action to an **earlier run** that caused it — not a parent span in the same trace, but a prior, completed execution? | An agent that writes to its own memory can instruct its own future. 60 runs, 0 traces naming the writer. | **not established** |
| P-5 | Does the record distinguish *"no human authorised this"* from *"we did not write down who did"*? Is there a principal **type** and an **authentication method**, or only an optional identity string? | A scheduled chain reached a sensitive action with every control satisfied; an empty principal field and an honest `scheduled / none` are indistinguishable in most schemas. | **not established** |
| P-6 | Is the correlation identifier minted **per call** or **per credential**? | Under a shared credential our own per-credential identifier stopped disambiguating — 0 ambiguous records sequentially, 40 of 166 concurrently. A vendor whose identifier is per-session or per-token inherits the same failure. | **not established** |

**P-6 is the one most likely to change a conclusion in the matrix above.** Several
products there were credited with carrying a correlation identifier. That credit
was given without asking at what granularity the identifier is minted, and
campaign 3 shows the granularity is the whole question: an identifier that
survives one call and not two concurrent ones is not the mechanism the matrix
assumed it was. **Any re-examination should re-open those cells first**, and it
should be done knowing it may narrow the claim against this project's own
interest — which is how the last two rounds of this document went.

The existing verdicts are unchanged by this addendum. Nothing above is retracted;
three questions are added and marked unanswered.

---

## Version

**`2026-08-24-c3-complete`** · vendor verdicts unchanged since `c2`, with three
questions added and marked unanswered in the 2026-08-24 addendum above.

The matrix's evidence base remains the documentation fetched **2026-08-23**. A
verdict of "no standard/product defines this" is defensible only for as long as
the cited version says what it says, so the dates above are load-bearing rather
than decorative.

Snapshot and manifest: `golden-attack/versions/2026-08-24-c3-complete/`, which
records repo HEAD, this file's sha256, the corpus window, and the last ledger row
of every stage.

This document describes that campaign state and no other. The stamp is here
because the campaign carries no identifier of its own — `c3` in a run-id prefix is
the only one — so a copy of this file found on its own could otherwise not say
which run produced it. Campaign 1 is void and never scored.
