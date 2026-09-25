"""The saved calibration profile: asked once, reused, extended question-by-question, never corrupted.

Runs the real scripts/profile.py as a subprocess against a temporary PCP_PROFILE, and against a
temporary copy of the skill when the registry itself has to change.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/pcp/skills/pre-call-prep"
ALL = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]
ANSWERS = {"Q1": "Founder / principal (Recommended)", "Q2": "wealth", "Q3": "person", "Q4": "intro",
           "Q5": "fast", "Q6": "professional", "Q7": "us", "Q8": "We prepare advisors; a win is a second meeting."}


class ProfileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.path = self.tmp / "home" / ".pcp" / "profile.yaml"
        self.skill = SKILL

    def run_profile(self, *args, answers=None):
        env = {**os.environ, "PCP_PROFILE": str(self.path)}
        r = subprocess.run([sys.executable, str(self.skill / "scripts/profile.py"), *args],
                           input=None if answers is None else json.dumps(answers),
                           capture_output=True, text=True, env=env, cwd=self.tmp, timeout=30)
        return r.returncode, json.loads(r.stdout)

    def apply(self, answers, *extra):
        _, seen = self.run_profile("inspect")
        return self.run_profile("apply", "--answers-file", "-", "--base-sha256", seen["sha256"] or "none", *extra, answers=answers)

    def test_first_run_asks_all_then_second_run_asks_nothing(self):
        code, first = self.run_profile("inspect")
        self.assertEqual((code, first["status"], first["missing"]), (0, "missing", ALL))
        self.assertEqual([q["id"] for q in first["questions"]], ALL)
        code, applied = self.apply(ANSWERS)
        self.assertEqual(code, 0, applied)
        code, second = self.run_profile("inspect")
        self.assertEqual((second["status"], second["missing"], second["questions"]), ("complete", [], []))
        self.assertEqual(second["profile_line"], "principal · wealth · fast · us")
        self.assertEqual(second["effective"]["caller.authority_level"], "high")
        self.assertEqual(self.run_profile("validate")[0], 0)

    def test_partial_answers_leave_only_the_rest_to_ask(self):
        self.apply({k: ANSWERS[k] for k in ("Q1", "Q2", "Q3")})
        _, seen = self.run_profile("inspect")
        self.assertEqual((seen["status"], seen["missing"]), ("incomplete", ["Q4", "Q5", "Q6", "Q7", "Q8"]))
        self.assertIsNone(seen["profile_line"])
        self.assertEqual(self.run_profile("validate")[0], 1)

    def test_new_registry_question_is_the_only_one_asked(self):
        self.skill = self.tmp / "skill"
        shutil.copytree(SKILL, self.skill)
        self.apply(ANSWERS)
        reg = yaml.safe_load((self.skill / "pcp.yaml").read_text())
        reg["calibration"]["questions"].append({
            "id": "Q9", "header": "Region", "question": "Main region?", "sets": {"region": "value"}, "consumed_by": [],
            "options": [{"label": "Americas (Recommended)", "value": "amer", "description": "x"},
                        {"label": "EMEA", "value": "emea", "description": "y"}]})
        (self.skill / "pcp.yaml").write_text(yaml.safe_dump(reg, sort_keys=False))
        _, seen = self.run_profile("inspect")
        self.assertEqual((seen["status"], seen["missing"]), ("incomplete", ["Q9"]))
        self.assertEqual([q["id"] for q in seen["questions"]], ["Q9"])

    def test_removed_option_reasks_only_that_question(self):
        self.skill = self.tmp / "skill"
        shutil.copytree(SKILL, self.skill)
        self.apply(ANSWERS)
        reg = yaml.safe_load((self.skill / "pcp.yaml").read_text())
        q2 = next(q for q in reg["calibration"]["questions"] if q["id"] == "Q2")
        q2["options"] = [o for o in q2["options"] if o["value"] != "wealth"]
        (self.skill / "pcp.yaml").write_text(yaml.safe_dump(reg, sort_keys=False))
        _, seen = self.run_profile("inspect")
        self.assertEqual(seen["missing"], ["Q2"])
        self.assertIn("no longer an option", seen["stale"]["Q2"])

    def test_skipped_answer_takes_recommended_option_marked_defaulted(self):
        code, out = self.apply({**ANSWERS, "Q5": None})
        self.assertEqual(code, 0, out)
        self.assertEqual(out["effective"]["research.depth"], "standard")
        self.assertEqual(out["defaulted"], ["Q5"])

    def test_skipped_free_text_is_rejected_not_invented(self):
        code, out = self.apply({**ANSWERS, "Q8": None})
        self.assertEqual((code, out["code"]), (1, "REQUIRED"))
        self.assertFalse(self.path.exists())

    def test_answer_outside_the_options_is_rejected_and_nothing_written(self):
        code, out = self.apply({**ANSWERS, "Q2": "banking"})
        self.assertEqual((code, out["code"]), (1, "INVALID_ANSWER"))
        self.assertIn("wealth", out["allowed"])
        self.assertFalse(self.path.exists())

    def test_unknown_question_id_is_rejected(self):
        code, out = self.apply({"Q99": "x"})
        self.assertEqual((code, out["code"]), (1, "UNKNOWN_QUESTION"))

    def test_corrupt_profile_is_never_overwritten_without_consent(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"profiles: [this is: not: a profile\n")
        before = self.path.read_bytes()
        _, seen = self.run_profile("inspect")
        self.assertEqual(seen["status"], "invalid")
        code, out = self.run_profile("apply", "--answers-file", "-", "--base-sha256", seen["sha256"], answers=ANSWERS)
        self.assertEqual((code, out["code"]), (1, "INVALID_PROFILE"))
        self.assertEqual(self.path.read_bytes(), before)
        code, out = self.run_profile("apply", "--answers-file", "-", "--base-sha256", seen["sha256"],
                                     "--replace-invalid", answers=ANSWERS)
        self.assertEqual((code, out["status"]), (0, "complete"), out)
        self.assertEqual(Path(out["backup"]).read_bytes(), before)

    def test_stale_digest_is_rejected(self):
        self.apply(ANSWERS)
        code, out = self.run_profile("apply", "--answers-file", "-", "--base-sha256", "none", answers={"Q5": "deep"})
        self.assertEqual((code, out["code"]), (1, "STALE"))
        self.assertEqual(self.run_profile("inspect")[1]["effective"]["research.depth"], "fast")

    def test_named_profiles_are_isolated(self):
        self.apply(ANSWERS)
        _, seen = self.run_profile("inspect")
        code, out = self.run_profile("apply", "--answers-file", "-", "--base-sha256", seen["sha256"],
                                     "--profile", "investor", answers={**ANSWERS, "Q1": "investor"})
        self.assertEqual(code, 0, out)
        self.assertEqual(self.run_profile("inspect")[1]["effective"]["caller.role"], "principal")
        self.assertEqual(self.run_profile("inspect", "--profile", "investor")[1]["effective"]["caller.role"], "investor")
        self.assertEqual(self.run_profile("inspect", "--profile", "nobody")[1]["missing"], ALL)

    def test_recalibrate_lists_every_question_with_its_saved_answer(self):
        self.apply(ANSWERS)
        _, seen = self.run_profile("inspect", "--recalibrate")
        self.assertEqual([q["id"] for q in seen["questions"]], ALL)
        self.assertEqual(seen["questions"][1]["current"], "wealth")

    def test_blocked_write_reports_write_denied_as_json(self):
        self.path.parent.mkdir(parents=True)
        self.path.parent.chmod(0o500)
        self.addCleanup(self.path.parent.chmod, 0o700)
        code, out = self.apply(ANSWERS)
        self.assertEqual((code, out["code"]), (1, "WRITE_DENIED"), out)
        self.assertFalse(self.path.exists())

    def test_recalibrate_has_its_own_status_so_complete_never_suppresses_it(self):
        self.apply(ANSWERS)
        _, seen = self.run_profile("inspect", "--recalibrate")
        self.assertEqual(seen["status"], "recalibrate")
        self.assertEqual(self.run_profile("inspect")[1]["status"], "complete")

    def test_profile_written_by_v2_0_0_is_read_without_asking_again(self):
        # tests/fixtures/v2.0.0-profile.yaml was written by the v2.0.0 skill itself in a live run
        legacy = (ROOT / "tests/fixtures/v2.0.0-profile.yaml").read_bytes()
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(legacy)
        _, seen = self.run_profile("inspect")
        self.assertEqual((seen["status"], seen["missing"], seen["migrated_from"]), ("complete", [], "v2.0.0"))
        self.assertEqual(seen["profile_line"], "principal · general · standard · us")
        self.assertIn("working session", seen["effective"]["meeting.win_definition"])
        code, out = self.run_profile("apply", "--answers-file", "-", "--base-sha256", seen["sha256"], answers={"Q5": "deep"})
        self.assertEqual(code, 0, out)
        self.assertEqual(out["effective"]["research.depth"], "deep")
        self.assertEqual(out["effective"]["domain"], "general")
        self.assertEqual(Path(out["backup"]).read_bytes(), legacy)
        self.assertEqual(yaml.safe_load(self.path.read_text())["pcp_profile_format"], 1)

    def test_v2_0_0_value_that_is_no_longer_an_option_is_asked_not_kept(self):
        legacy = yaml.safe_load((ROOT / "tests/fixtures/v2.0.0-profile.yaml").read_text())
        legacy["domain"] = "banking"
        self.path.parent.mkdir(parents=True)
        self.path.write_text(yaml.safe_dump(legacy))
        _, seen = self.run_profile("inspect")
        self.assertEqual((seen["status"], seen["missing"]), ("incomplete", ["Q2"]))

    def test_improve_writes_only_a_patch_beside_the_debrief(self):
        out = self.tmp / "call"
        out.mkdir()
        (out / "debrief.yaml").write_text(yaml.safe_dump({"facts_used": [1], "questions_landed": [],
                                                          "band_accuracy": {"dominance": "miss"}, "outcome": "no"}))
        before = {p for p in SKILL.rglob("*") if "__pycache__" not in p.parts}
        r = subprocess.run([sys.executable, str(SKILL / "scripts/eval.py"), "improve", str(out / "debrief.yaml")],
                           cwd=self.tmp, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        patches = list(out.glob("pcp-proposals-*.patch"))
        self.assertEqual(len(patches), 1)
        self.assertIn("rubric dominance", patches[0].read_text())
        self.assertEqual({p for p in SKILL.rglob("*") if "__pycache__" not in p.parts}, before)

    def test_profile_line_comes_from_the_registry(self):
        """The footer's profile line is read from pcp.yaml calibration.profile_line."""
        self.skill = self.tmp / "skill"
        shutil.copytree(SKILL, self.skill)
        self.apply(ANSWERS)
        reg = yaml.safe_load((self.skill / "pcp.yaml").read_text())
        reg["calibration"]["profile_line"] = ["jurisdiction", "caller.role"]
        (self.skill / "pcp.yaml").write_text(yaml.safe_dump(reg, sort_keys=False))
        self.assertEqual(self.run_profile("inspect")[1]["profile_line"], "us · principal")

    def test_profile_file_is_private(self):
        self.apply(ANSWERS)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.path.parent.glob(".profile-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
