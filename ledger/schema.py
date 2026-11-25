"""Stdlib validator for schema/claim.schema.json plus the rules JSON Schema cannot say."""
from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "claim.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
REQUIRED = tuple(SCHEMA["required"])
STATUSES = tuple(SCHEMA["$defs"]["status"]["enum"])


def _resolve(node: dict) -> dict:
    while "$ref" in node:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            raise ValueError(f"unsupported $ref {ref}")
        node = SCHEMA
        for part in ref[2:].split("/"):
            node = node[part]
    return node


_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


def _check(value, node: dict, path: str, out: list[str]) -> None:
    node = _resolve(node)
    if "oneOf" in node:
        ok = [s for s in node["oneOf"] if not _errors(value, s, path)]
        if len(ok) != 1:
            out.append(f"{path}: does not match exactly one allowed form")
        return
    t = node.get("type")
    if t and not _TYPES[t](value):
        out.append(f"{path}: expected {t}, got {type(value).__name__}")
        return
    if "enum" in node and value not in node["enum"]:
        out.append(f"{path}: {value!r} is not one of {node['enum']}")
    if isinstance(value, str):
        if "pattern" in node and not re.search(node["pattern"], value):
            out.append(f"{path}: {value!r} does not match {node['pattern']}")
        if len(value) < node.get("minLength", 0):
            out.append(f"{path}: too short")
    if _TYPES["number"](value):
        if "minimum" in node and value < node["minimum"]:
            out.append(f"{path}: below {node['minimum']}")
        if "maximum" in node and value > node["maximum"]:
            out.append(f"{path}: above {node['maximum']}")
    if isinstance(value, list):
        if len(value) < node.get("minItems", 0):
            out.append(f"{path}: needs at least {node['minItems']} item(s)")
        if "items" in node:
            for i, item in enumerate(value):
                _check(item, node["items"], f"{path}[{i}]", out)
    if isinstance(value, dict):
        props = node.get("properties", {})
        for req in node.get("required", []):
            if req not in value:
                out.append(f"{path}.{req}: missing")
        for k, v in value.items():
            if k in props:
                _check(v, props[k], f"{path}.{k}", out)
            elif node.get("additionalProperties") is False:
                out.append(f"{path}.{k}: unknown field")


def _errors(value, node, path) -> list[str]:
    out: list[str] = []
    _check(value, node, path, out)
    return out


def validate_claim(c) -> list[str]:
    cid = c.get("id", "?") if isinstance(c, dict) else "?"
    msgs = _errors(c, SCHEMA, cid)
    if msgs or not isinstance(c, dict):
        return msgs
    if c["comparator"] == "eq" and c["tolerance"] != 0:
        msgs.append(f"{cid}.tolerance: eq needs tolerance 0")
    for i, g in enumerate(c.get("guards", [])):
        if g["comparator"] == "approx":
            msgs.append(f"{cid}.guards[{i}].comparator: approx has no reference value in a guard")
    if not c["id"].startswith(c["project"] + "-"):
        msgs.append(f"{cid}.id: must start with the project name")
    dates = [h["date"] for h in c["history"]]
    if dates != sorted(dates):
        msgs.append(f"{cid}.history: dates must be in order")
    if c["history"][-1]["status"] != c["status"]:
        msgs.append(f"{cid}.status: differs from the last history entry")
    if c["adapter"] != "stdout_regex" and not c["result_path"]:
        msgs.append(f"{cid}.result_path: required for adapter {c['adapter']}")
    if c["lab_page"] is None and "essay_url" not in c:
        msgs.append(f"{cid}.lab_page: null needs essay_url")
    return msgs


def load_claims(directory: Path) -> dict[str, dict]:
    claims, problems = {}, []
    for p in sorted(Path(directory).glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        problems += validate_claim(c)
        if isinstance(c, dict) and c.get("id") != p.stem:
            problems.append(f"{p.name}: id {c.get('id')!r} does not match the file name")
        claims[c.get("id", p.stem)] = c
    if problems:
        raise ValueError("invalid claims:\n" + "\n".join(problems))
    return claims
