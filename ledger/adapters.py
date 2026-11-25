"""Read one number out of a command's result (stdlib only).

json_select     a.b.c, list[k=v,k2=v2].field, an optional aggregate min(...)/max(...) around a
                filter that may match several rows, and an optional trailing *<factor>
md_table        "<section heading>|<row label>|<column header>"; each part matches the start of
                the text after markdown emphasis is stripped
junit_failures  failures + errors over every testcase; a file with no testcase is an error
zeno_counts     counts[key] / shots
stdout_regex    float of the first group of the first match (re.S)
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ADAPTERS = ("json_select", "md_table", "junit_failures", "zeno_counts", "stdout_regex")
_MINUS = str.maketrans({"−": "-", "–": "-", " ": " "})


def _num(x, where: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"{where}: not a number: {x!r}")
    return float(x)


def _parse_filter(text: str) -> dict:
    conds = {}
    for part in text.split(","):
        if "=" not in part:
            raise ValueError(f"bad filter {text!r}")
        k, v = part.split("=", 1)
        conds[k.strip()] = v.strip()
    return conds


def _match(row, conds: dict) -> bool:
    return isinstance(row, dict) and all(k in row and str(row[k]) == v for k, v in conds.items())


_SEG = re.compile(r"([A-Za-z0-9_-]*)(?:\[([^\]]*)\])?$")


def _walk(nodes: list, path: str, key: str) -> list:
    for seg in path.split("."):
        m = _SEG.match(seg)
        if not m or (not m.group(1) and m.group(2) is None):
            raise ValueError(f"bad key segment {seg!r} in {key!r}")
        name, filt = m.group(1), m.group(2)
        nxt = []
        for node in nodes:
            if name:
                if not isinstance(node, dict) or name not in node:
                    raise ValueError(f"{key}: missing {name!r}")
                node = node[name]
            if filt is not None:
                if not isinstance(node, list):
                    raise ValueError(f"{key}: {name or 'root'} is not a list")
                nxt.extend(r for r in node if _match(r, _parse_filter(filt)))
            else:
                nxt.append(node)
        if not nxt:
            raise ValueError(f"{key}: no row matches {seg!r}")
        nodes = nxt
    return nodes


def json_select(data, key: str) -> float:
    expr, factor = key, 1.0
    m = re.fullmatch(r"(.+)\*([0-9.eE+-]+)", expr)
    if m:
        expr, factor = m.group(1), float(m.group(2))
    agg = None
    m = re.fullmatch(r"(min|max)\((.+)\)", expr)
    if m:
        agg, expr = m.group(1), m.group(2)
    nodes = _walk([data], expr, key)
    vals = [_num(n, key) for n in nodes]
    if agg:
        return (min if agg == "min" else max)(vals) * factor
    if len(vals) != 1:
        raise ValueError(f"{key}: {len(vals)} matches; wrap the key in min() or max()")
    return vals[0] * factor


def _clean(cell: str) -> str:
    return re.sub(r"[*_`]", "", cell).translate(_MINUS).strip()


def md_table(text: str, key: str) -> float:
    try:
        section, row_label, col = (p.strip() for p in key.split("|"))
    except ValueError:
        raise ValueError(f"md_table key needs three parts: {key!r}") from None
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        h = re.match(r"#+\s+(.*)", line)
        if h and _clean(h.group(1)).startswith(section):
            start = i
            break
    if start is None:
        raise ValueError(f"md_table: no section {section!r}")
    header = None
    for line in lines[start + 1:]:
        if re.match(r"#+\s", line):
            break
        if not line.lstrip().startswith("|"):
            continue
        cells = [_clean(c) for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if cells[0].startswith(row_label):
            for j, h in enumerate(header):
                if h.startswith(col) and j < len(cells):
                    try:
                        return float(cells[j].replace(",", "."))
                    except ValueError:
                        raise ValueError(f"md_table: cell {cells[j]!r} is not a number") from None
            raise ValueError(f"md_table: no column {col!r}")
    raise ValueError(f"md_table: no row {row_label!r} in {section!r}")


def junit_failures(path: Path) -> float:
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    if not cases:
        raise ValueError(f"{path.name}: no testcase elements")
    bad = sum(1 for c in cases if c.find("failure") is not None or c.find("error") is not None)
    return float(bad)


def extract(adapter: str, result_file: Path | None, key: str, stdout: str) -> float:
    if adapter not in ADAPTERS:
        raise ValueError(f"unknown adapter {adapter!r}")
    if adapter == "stdout_regex":
        m = re.search(key, stdout, re.S)
        if not m:
            raise ValueError("stdout_regex: no match")
        return float(m.group(1).translate(_MINUS))
    if result_file is None:
        raise ValueError(f"{adapter} needs a result file")
    result_file = Path(result_file)
    if adapter == "junit_failures":
        return junit_failures(result_file)
    text = result_file.read_text(encoding="utf-8")
    if adapter == "md_table":
        return md_table(text, key)
    data = json.loads(text)
    if adapter == "zeno_counts":
        shots = _num(data.get("shots"), "shots")
        if shots <= 0:
            raise ValueError("zeno_counts: shots must be positive")
        return _num(data.get("counts", {}).get(key, 0), f"counts[{key}]") / shots
    return json_select(data, key)
