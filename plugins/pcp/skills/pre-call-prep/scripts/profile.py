#!/usr/bin/env python3
"""profile.py -- the only reader and writer of the pcp calibration profile.

The schema is pcp.yaml `calibration.questions`: each question id is a field, its option values are
the allowed values, a question with `free_text: true` takes a string. Nothing else defines it, so a
question added to pcp.yaml is reported missing (and asked) without touching this file.

  inspect  [--profile NAME] [--recalibrate]       status + only the questions still to ask (JSON)
  apply    --answers-file PATH|- --base-sha256 SHA|none [--profile NAME] [--replace-invalid]
  validate [--profile NAME]                        exit 0 only for a complete, valid profile

Answers are a JSON object {question_id: value}. A value may be the option value or its exact label;
null means skipped, which stores the first (Recommended) option with defaulted: true.

The file lives at pcp.yaml `calibration.profile_path` (one per user, all named profiles in one file).
PCP_PROFILE overrides the location. Writes are atomic; a stale base digest or an unreadable file is
rejected without touching the existing bytes. Output is JSON on stdout; exit 0 = ok, 1 = rejected.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import tempfile

import yaml

HERE = pathlib.Path(__file__).resolve().parent
REGISTRY = HERE.parent / "pcp.yaml"
FORMAT = 1
DEFAULT_PROFILE = "default"


class Rejected(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


def load_calibration():
    cal = yaml.safe_load(REGISTRY.read_text())["calibration"]
    return cal, {q["id"]: q for q in cal["questions"]}


def profile_path(cal):
    return pathlib.Path(os.environ.get("PCP_PROFILE") or cal["profile_path"]).expanduser()


def read(path):
    """-> (raw bytes or None, parsed doc or None, reason if unreadable)."""
    if not path.exists():
        return None, None, None
    raw = path.read_bytes()
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return raw, None, f"not valid YAML: {exc}".splitlines()[0]
    if not isinstance(doc, dict) or doc.get("pcp_profile_format") != FORMAT or not isinstance(doc.get("profiles"), dict):
        return raw, None, f"not a pcp profile (expected pcp_profile_format: {FORMAT} and a profiles mapping)"
    for name, entry in doc["profiles"].items():
        if not isinstance(entry, dict) or not isinstance(entry.get("answers", {}), dict):
            return raw, None, f"profile {name!r} has no answers mapping"
    return raw, doc, None


def digest(raw):
    return None if raw is None else hashlib.sha256(raw).hexdigest()


def check_answer(q, stored):
    """Stored answer -> None if valid for the current registry, else the reason it must be re-asked."""
    if not isinstance(stored, dict) or "value" not in stored:
        return "stored answer has no value"
    v = stored["value"]
    if q.get("free_text"):
        return None if isinstance(v, str) and v.strip() else "free-text answer is empty"
    allowed = [o["value"] for o in q["options"]]
    return None if v in allowed else f"{v!r} is no longer an option ({', '.join(allowed)})"


def normalise(q, given):
    """User-supplied answer -> stored {value, defaulted}. Raises Rejected on anything not in the schema."""
    if given is None:
        if q.get("free_text"):
            raise Rejected("REQUIRED", f"{q['id']} is free text and has no recommended default; ask it again")
        return {"value": q["options"][0]["value"], "defaulted": True}
    if not isinstance(given, str) or not given.strip():
        raise Rejected("INVALID_ANSWER", f"{q['id']}: answer must be a non-empty string or null")
    given = given.strip()
    if q.get("free_text"):
        return {"value": given, "defaulted": False}
    for o in q["options"]:
        if given in (o["value"], o["label"]):
            return {"value": o["value"], "defaulted": False}
    raise Rejected("INVALID_ANSWER", f"{q['id']}: {given!r} is not an option",
                   allowed=[o["value"] for o in q["options"]])


def effective(questions, answers):
    """Apply each question's `sets` rows: value, text, or an 'a->b, c->d' mapping over the value."""
    out = {}
    for qid, q in questions.items():
        if qid not in answers or check_answer(q, answers[qid]):
            continue
        v = answers[qid]["value"]
        for field, rule in q["sets"].items():
            if rule in ("value", "text"):
                out[field] = v
            else:
                mapping = dict(part.split("->") for part in (p.strip() for p in rule.split(",")))
                out[field] = mapping.get(v)
    return out


def profile_line(eff):
    return " · ".join(str(eff.get(k, "?")) for k in ("caller.role", "domain", "research.depth", "jurisdiction"))


def question_view(q, current=None):
    view = {k: q[k] for k in ("id", "header", "question")}
    view["options"] = [{"label": o["label"], "value": o["value"], "description": o["description"]} for o in q["options"]]
    view["free_text"] = bool(q.get("free_text"))
    if current is not None:
        view["current"] = current
    return view


def inspect(name, recalibrate=False):
    cal, questions = load_calibration()
    path = profile_path(cal)
    raw, doc, bad = read(path)
    base = {"path": str(path), "profile": name, "sha256": digest(raw)}
    if bad:
        return {**base, "status": "invalid", "reason": bad, "questions": [question_view(q) for q in questions.values()]}
    answers = ((doc or {}).get("profiles", {}).get(name) or {}).get("answers", {})
    missing, stale = [], {}
    for qid, q in questions.items():
        if qid not in answers:
            missing.append(qid)
        elif (why := check_answer(q, answers[qid])):
            missing.append(qid); stale[qid] = why
    ask = list(questions) if recalibrate else missing
    eff = effective(questions, answers)
    status = "missing" if not answers else ("incomplete" if missing else "complete")
    return {**base, "status": status, "missing": missing, "stale": stale,
            "unknown": sorted(set(answers) - set(questions)),
            "questions": [question_view(questions[q], answers.get(q, {}).get("value") if recalibrate else None) for q in ask],
            "effective": eff, "defaulted": sorted(q for q in answers if answers[q].get("defaulted")),
            "profile_line": profile_line(eff) if not missing else None}


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".profile-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text); fh.flush(); os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        pathlib.Path(tmp).unlink(missing_ok=True)
        raise


def apply(name, answers_json, base_sha, replace_invalid=False):
    cal, questions = load_calibration()
    path = profile_path(cal)
    raw, doc, bad = read(path)
    expected = None if base_sha in (None, "none", "") else base_sha
    if digest(raw) != expected:
        raise Rejected("STALE", "the profile changed since inspect (or --base-sha256 is wrong); inspect again",
                       current_sha256=digest(raw))
    try:
        given = json.loads(answers_json)
    except ValueError as exc:
        raise Rejected("INVALID_JSON", f"answers are not JSON: {exc}")
    if not isinstance(given, dict) or not given:
        raise Rejected("INVALID_JSON", "answers must be a non-empty JSON object {question_id: value}")
    unknown = sorted(set(given) - set(questions))
    if unknown:
        raise Rejected("UNKNOWN_QUESTION", f"not calibration questions: {unknown}", allowed=list(questions))
    stored = {qid: normalise(questions[qid], v) for qid, v in given.items()}   # all-or-nothing

    try:
        return _write(path, name, stored, raw, doc, bad, replace_invalid)
    except PermissionError as exc:
        raise Rejected("WRITE_DENIED", f"the host did not allow writing {path} ({exc.strerror}); "
                       "retry with the host's permission to write there, or keep the answers for this run only",
                       path=str(path))


def _write(path, name, stored, raw, doc, bad, replace_invalid):
    backup = None
    if bad:
        if not replace_invalid:
            raise Rejected("INVALID_PROFILE", f"existing profile is unreadable ({bad}); ask the user, then pass --replace-invalid")
        backup = path.with_name(f"{path.name}.invalid-{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}")
        backup.write_bytes(raw)
        doc = None
    doc = doc or {"pcp_profile_format": FORMAT, "profiles": {}}
    entry = doc["profiles"].setdefault(name, {"answers": {}})
    entry.setdefault("answers", {}).update(stored)
    entry["updated"] = dt.date.today().isoformat()
    text = "# pcp calibration profile -- written by scripts/profile.py; edit with `/pcp --recalibrate`, not by hand.\n"
    atomic_write(path, text + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
    return {**inspect(name), "written": sorted(stored), "backup": str(backup) if backup else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("inspect", "apply", "validate"):
        p = sub.add_parser(cmd)
        p.add_argument("--profile", default=DEFAULT_PROFILE)
        if cmd == "inspect":
            p.add_argument("--recalibrate", action="store_true")
        if cmd == "apply":
            p.add_argument("--answers-file", required=True, help="JSON file, or - for stdin")
            p.add_argument("--base-sha256", required=True, help="sha256 from inspect, or none when no file exists")
            p.add_argument("--replace-invalid", action="store_true")
    a = ap.parse_args()
    try:
        if a.cmd == "inspect":
            out = inspect(a.profile, a.recalibrate)
        elif a.cmd == "apply":
            text = sys.stdin.read() if a.answers_file == "-" else pathlib.Path(a.answers_file).read_text()
            out = apply(a.profile, text, a.base_sha256, a.replace_invalid)
        else:
            out = inspect(a.profile)
            print(json.dumps(out, indent=1, ensure_ascii=False))
            return 0 if out["status"] == "complete" else 1
    except Rejected as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": str(exc), **exc.details}, indent=1, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, **out}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
