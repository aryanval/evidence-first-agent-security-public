# Exhibit A — a tool call and the record of what it caused, side by side

**Two real records from one run of the campaign, arguments redacted.** This is
the whole finding in a form that can be checked in ten seconds rather than
argued about: both records are authoritative about their own half, they are
37 milliseconds apart, and **no field on either one refers to the other.**

Everything identifying the scenario, the payload, the fleet topology and the
resource path is redacted. What is left is the part that matters — which fields
exist on each side.

---

## 1. What the agent framework recorded

The tool call, as the execution substrate saw it.

```jsonc
{
  "kind":                "tool_call",
  "span_id":             "s-66d720e1",
  "ts":                  "2026-08-23T01:25:27.398Z",
  "evidence_class":      "CLAIMED",
  "source_trust_domain": "agent-process",
  "run_id":              "<run-id>",
  "parent_span_id":      "<parent-span>",
  "outcome":             "success",
  "causal_link":  { "edge": "authorization_to_tool", "evidence_class": "CLAIMED" },
  "data": {
    "tool":         "<tool-name>",
    "args_digest":  "sha256:<redacted>",
    "args_preview": null,
    "sensitive":    true
  }
}
```

**Fields available on this record that name a record in the resource owner's
world: none.** The complete field set is `agent, causal_link, data, evidence,
evidence_class, kind, observer_identity, outcome, parent_span_id, producer,
run_id, schema_version, source_trust_domain, span_id, ts` — and searching all of
them, plus every key under `data`, for anything that could point outward returns
the empty set.

## 2. What the platform recorded about the resulting change

The resource owner's own audit line, written 37 ms later.

```jsonc
{
  "system":   "<platform>",
  "event":    "records.export",
  "ts":       "2026-08-23T01:25:27.435Z",
  "resource": "<resource-path>",
  "outcome":  "success",
  "actor":    { "sub": "<subject>", "aud": "<audience>",
                "scope": ["<scope>"], "jti": "6a6f…2c77" },
  "required": { "scope": "<required-scope>", "audience": "<required-audience>" },
  "via":      "<gateway>/1.0"
}
```

**Fields available on this record that name the tool call that caused it: none.**
It records *what* happened, *which credential* did it, and *whether the credential
was sufficient*. It has nowhere to record *why* — no field points at
`s-66d720e1`, and no field points at any span, run, or agent.

---

## 3. The join, and what it actually rests on

The two records **can** be joined here, and it is worth being precise about how,
because the mechanism is the recommendation rather than the finding.

| candidate join | works? | what it rests on |
|---|---|---|
| `span_id` ↔ any platform field | **no** | the platform record has no field for it |
| timestamp proximity (37 ms) | **inferred only** | reconstruction, not evidence — and it degrades the moment two runs overlap |
| `jti` | **yes, here** | this lab mints a token per tool call and the platform records it |

The third row is the entire reason this pair joins at all, and it is a property
of **this lab**, not of the field. A representative production audit record
generates every identifier itself — the request id by the service, the event id
by the audit system — and carries **no caller-supplied reference** to the
operation that triggered the call. Remove the per-call token and the only
surviving join is the second row: a time window, which is inference, and which
the concurrency arm of this campaign measures degrading as soon as more than one
run shares a credential.

So the exhibit demonstrates two things at once:

1. **The gap.** Nothing in either schema binds a tool call to the resource
   owner's record of the side effect. Both endpoints are authoritative about
   their own half and neither carries the edge.
2. **The fix, already working.** A caller-supplied per-call identifier, recorded
   by the receiving platform, turns an inference into a join. That is exactly the
   two optional attributes proposed against the schema — `span_uid` for the join
   and `method` for how the attribution was established, so that a link stitched
   from a time window and one carried on propagated context are not
   indistinguishable once written down.

---

## 4. What is redacted here, and why

Tool name, resource path, subject, audience, scopes, gateway identity, run id,
parent span, and the argument digest's full value are redacted. They identify
the scenario and the fleet, and they are the part that would shorten someone's
path to a working payload. The span id and the truncated `jti` are kept because
they carry no information beyond "these two records exist and are distinct",
which is what the exhibit needs.

The timestamps are real and unmodified: the 37 ms gap is the point of row two in
the table above.
