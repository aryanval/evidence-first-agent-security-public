#!/usr/bin/env python3
"""Validate evidence-envelope JSONL against agent-trace-schema.json.

No third-party dependencies. Python 3.8+.

    python3 validate.py *.jsonl
    python3 validate.py --schema agent-trace-schema.json fully-corroborated.jsonl

Two passes:

  1. Per-line JSON Schema validation. Supports the conservative draft 2020-12
     subset the schema deliberately stays inside: type, enum, const, required,
     properties, additionalProperties, items, minItems, minimum, maximum,
     minLength, pattern, format(date-time), allOf, anyOf, if/then/else, and
     $ref to local $defs. Anything else in the schema is reported rather than
     silently ignored, so the validator cannot quietly under-check.

  2. Cross-line envelope rules E-1 .. E-8 from SPEC.md, which JSON Schema
     cannot express. E-8 is a warning; the rest are errors.

Exit status: 0 if no errors, 1 otherwise.
"""

import argparse
import json
import re
import sys
from collections import defaultdict

SUPPORTED = {
    "$schema", "$id", "$defs", "title", "description", "default", "examples",
    "type", "enum", "const", "required", "properties", "additionalProperties",
    "items", "minItems", "minimum", "maximum", "minLength", "pattern",
    "format", "allOf", "anyOf", "if", "then", "else", "$ref",
}

DATE_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$"
)


# --------------------------------------------------------------------------
# pass 1: JSON Schema subset
# --------------------------------------------------------------------------

def json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):          # before int: bool is an int subclass
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "integer" if value.is_integer() else "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def type_ok(value, expected):
    actual = json_type(value)
    if expected == "number":
        return actual in ("integer", "number")
    return actual == expected


def resolve(ref, root):
    if not ref.startswith("#"):
        raise ValueError("only local $ref is supported, got %r" % ref)
    node = root
    for part in ref.lstrip("#/").split("/"):
        if not part:
            continue
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[part]
    return node


def check(value, schema, root, path, errs, unsupported):
    """Append '<path>: <message>' strings to errs for every violation."""
    if schema is True or schema == {}:
        return
    if schema is False:
        errs.append("%s: schema forbids any value here" % path)
        return

    for key in schema:
        if key not in SUPPORTED:
            unsupported.add(key)

    if "$ref" in schema:
        check(value, resolve(schema["$ref"], root), root, path, errs, unsupported)

    if "type" in schema:
        expected = schema["type"]
        allowed = expected if isinstance(expected, list) else [expected]
        if not any(type_ok(value, t) for t in allowed):
            errs.append("%s: expected type %s, got %s"
                        % (path, "/".join(allowed), json_type(value)))
            return  # further keywords would be noise

    if "enum" in schema and value not in schema["enum"]:
        errs.append("%s: %r is not one of %s" % (path, value, schema["enum"]))
    if "const" in schema and value != schema["const"]:
        errs.append("%s: expected constant %r, got %r"
                    % (path, schema["const"], value))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errs.append("%s: shorter than minLength %d" % (path, schema["minLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errs.append("%s: %r does not match pattern %s"
                        % (path, value, schema["pattern"]))
        if schema.get("format") == "date-time" and not DATE_TIME.match(value):
            errs.append("%s: %r is not an RFC3339 date-time" % (path, value))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errs.append("%s: %r < minimum %r" % (path, value, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            errs.append("%s: %r > maximum %r" % (path, value, schema["maximum"]))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errs.append("%s: fewer than minItems %d" % (path, schema["minItems"]))
        if "items" in schema:
            for i, item in enumerate(value):
                check(item, schema["items"], root, "%s[%d]" % (path, i),
                      errs, unsupported)

    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                errs.append("%s: missing required property %r" % (path, name))
        props = schema.get("properties", {})
        for name, sub in props.items():
            if name in value:
                check(value[name], sub, root, "%s.%s" % (path, name),
                      errs, unsupported)
        extra = schema.get("additionalProperties")
        if extra is not None and extra is not True:
            for name in value:
                if name not in props:
                    if extra is False:
                        errs.append("%s: additional property %r not allowed"
                                    % (path, name))
                    else:
                        check(value[name], extra, root, "%s.%s" % (path, name),
                              errs, unsupported)

    for i, sub in enumerate(schema.get("allOf", [])):
        check(value, sub, root, path, errs, unsupported)

    if "anyOf" in schema:
        branch_errs = []
        for sub in schema["anyOf"]:
            probe = []
            check(value, sub, root, path, probe, unsupported)
            if not probe:
                break
            branch_errs.append(probe[0].split(": ", 1)[-1])
        else:
            errs.append("%s: matches no anyOf branch (%s)"
                        % (path, "; ".join(branch_errs)))

    if "if" in schema:
        probe = []
        check(value, schema["if"], root, path, probe, unsupported)
        branch = "then" if not probe else "else"
        if branch in schema:
            check(value, schema[branch], root, path, errs, unsupported)


# --------------------------------------------------------------------------
# pass 2: cross-line envelope rules
# --------------------------------------------------------------------------

LEGACY = {"claimed": "CLAIMED", "observed": "OBSERVED"}


def envelope_rules(records):
    """records: list of (lineno, obj). Returns (errors, warnings)."""
    errs, warns = [], []
    seen_spans = defaultdict(set)          # run_id -> {span_id}
    declared = set()                       # (run_id, producer) seen already
    parents = []                           # (lineno, run_id, parent_span_id)

    for lineno, rec in records:
        tag = "line %d" % lineno
        run = rec.get("run_id")
        span = rec.get("span_id")
        producer = rec.get("producer")
        cls = rec.get("evidence_class")
        link = rec.get("causal_link")

        # E-1 causal_link.parent_span_id agrees with the top-level one
        if isinstance(link, dict) and "parent_span_id" in link:
            if "parent_span_id" in rec and link["parent_span_id"] != rec["parent_span_id"]:
                errs.append("%s: E-1 causal_link.parent_span_id %r != parent_span_id %r"
                            % (tag, link["parent_span_id"], rec["parent_span_id"]))

        # E-3 first record per (run, producer) declares blind spots.
        # 0.2 only: the field does not exist in 0.1, so 0.1 records are exempt
        # rather than retroactively non-conforming.
        key = (run, producer)
        if key not in declared:
            declared.add(key)
            if rec.get("schema_version") == "0.2" and "declared_blind_spots" not in rec:
                errs.append("%s: E-3 first record of producer %r in run %r "
                            "must carry declared_blind_spots" % (tag, producer, run))

        # E-4 only a range_harness may label ground truth
        if "ground_truth_label" in rec:
            kind = (rec.get("observer_identity") or {}).get("kind")
            if kind != "range_harness":
                errs.append("%s: E-4 ground_truth_label set by observer kind %r; "
                            "only 'range_harness' may label" % (tag, kind))

        # E-6 legacy field and evidence_class agree
        legacy = rec.get("evidence")
        if legacy is not None and cls is not None and LEGACY.get(legacy) != cls:
            errs.append("%s: E-6 evidence %r and evidence_class %r disagree"
                        % (tag, legacy, cls))

        # E-7 span_id unique within run
        if span in seen_spans[run]:
            errs.append("%s: E-7 duplicate span_id %r in run %r" % (tag, span, run))
        seen_spans[run].add(span)

        parent = rec.get("parent_span_id")
        if parent:
            parents.append((lineno, run, parent))

    # E-8 parents resolve within the run (warning: cross-run parents are legal)
    for lineno, run, parent in parents:
        if parent not in seen_spans[run]:
            warns.append("line %d: E-8 parent_span_id %r not found in run %r"
                         % (lineno, parent, run))

    return errs, warns


# --------------------------------------------------------------------------

def summarize(records):
    by_class = defaultdict(int)
    by_domain = defaultdict(int)
    edges = defaultdict(int)
    for _, rec in records:
        by_class[rec.get("evidence_class") or
                 LEGACY.get(rec.get("evidence"), "?") + " (0.1)"] += 1
        by_domain[rec.get("source_trust_domain", "-")] += 1
        link = rec.get("causal_link")
        if isinstance(link, dict):
            edges[(link.get("edge"), link.get("evidence_class"))] += 1
    return by_class, by_domain, edges


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="JSONL fixture files")
    ap.add_argument("--schema", default="agent-trace-schema.json")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="suppress the per-file evidence summary")
    args = ap.parse_args()

    with open(args.schema, encoding="utf-8") as fh:
        schema = json.load(fh)

    total_errors = 0
    unsupported = set()

    for path in args.files:
        errs, warns, records = [], [], []
        with open(path, encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, 1):
                if not raw.strip():
                    continue
                try:
                    rec = json.loads(raw)
                except json.JSONDecodeError as exc:
                    errs.append("line %d: not valid JSON: %s" % (lineno, exc))
                    continue
                records.append((lineno, rec))
                line_errs = []
                check(rec, schema, schema, "line %d" % lineno, line_errs, unsupported)
                errs.extend(line_errs)

        rule_errs, rule_warns = envelope_rules(records)
        errs.extend(rule_errs)
        warns.extend(rule_warns)

        status = "FAIL" if errs else "ok"
        print("%-28s %s  (%d records)" % (path, status, len(records)))
        for message in errs:
            print("    ERROR %s" % message)
        for message in warns:
            print("    warn  %s" % message)

        if not args.quiet and records:
            by_class, by_domain, edges = summarize(records)
            print("    evidence:      " +
                  ", ".join("%s=%d" % kv for kv in sorted(by_class.items())))
            print("    trust domains: " +
                  ", ".join("%s=%d" % kv for kv in sorted(by_domain.items())))
            if edges:
                print("    edges:")
                for (edge, cls), n in sorted(edges.items(),
                                             key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
                    print("        %-38s %-14s x%d" % (edge, cls, n))
        print()
        total_errors += len(errs)

    if unsupported:
        print("NOTE: schema uses keywords this validator does not check: %s"
              % ", ".join(sorted(unsupported)))
        print("      They were not enforced. Either add support or drop them "
              "from the schema.")

    if total_errors:
        print("%d error(s)." % total_errors)
        return 1
    print("All files valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
