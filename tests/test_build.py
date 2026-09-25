"""Packaging: one source generates every host file, the installed payload is self-contained and runs
from anywhere, and each gate is shown able to fail.

Every test works on a temporary copy of the repository, never the checkout itself.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
HOST_FILES = {
    ".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json", ".cursor-plugin/marketplace.json",
    "plugins/pcp/plugin.json", "plugins/pcp/.claude-plugin/plugin.json", "plugins/pcp/.cursor-plugin/plugin.json",
    "plugins/pcp/gemini-extension.json", "plugins/pcp/commands/pcp.md", "plugins/pcp/commands/pcp.toml",
}


class BuildTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.root = self.tmp / "repo"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns(".git", "dist", "__pycache__", ".venv", ".DS_Store"))
        self.plugin = self.root / "plugins/pcp"

    def generate(self, *args):
        return subprocess.run([sys.executable, "build/generate.py", *args], cwd=self.root,
                              capture_output=True, text=True, timeout=60)

    def snapshot(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*") if p.is_file() and "dist" not in p.relative_to(self.root).parts}

    def payload(self, catalog):
        doc = json.loads((self.root / catalog).read_text())
        entry, = doc["plugins"]
        source = entry["source"]["path"] if isinstance(entry["source"], dict) else entry["source"]
        return (self.root / source).resolve()

    # -- the generator ---------------------------------------------------------------------------

    def test_checkout_is_up_to_date_and_generation_is_repeatable(self):
        r = self.generate("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        before = self.snapshot()
        r = self.generate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.snapshot(), before, "a fresh generate changed the checkout -- it was stale")

    def test_hand_edit_of_any_host_file_fails_check(self):
        for rel in sorted(HOST_FILES) + ["plugins/pcp/skills/pre-call-prep/SKILL.md",
                                          "plugins/pcp/skills/talyx-pdf/scripts/talyx_pdf.py",
                                          "adapters/gemini/pcp-knowledge.md"]:
            with self.subTest(rel):
                path = self.root / rel
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                r = self.generate("--check")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(rel, r.stdout)
                path.write_bytes(original)

    def test_version_changes_in_one_place_reach_every_manifest(self):
        src = self.root / "build/plugin.source.json"
        doc = json.loads(src.read_text()); doc["version"] = "9.9.9"
        src.write_text(json.dumps(doc))
        self.assertEqual(self.generate().returncode, 0)
        for rel in ("plugins/pcp/plugin.json", "plugins/pcp/.claude-plugin/plugin.json",
                    "plugins/pcp/.cursor-plugin/plugin.json", "plugins/pcp/gemini-extension.json"):
            self.assertEqual(json.loads((self.root / rel).read_text())["version"], "9.9.9", rel)
        for rel in (".claude-plugin/marketplace.json", ".cursor-plugin/marketplace.json"):
            self.assertEqual(json.loads((self.root / rel).read_text())["metadata"]["version"], "9.9.9", rel)
        self.assertIn("(v9.9.9)", (self.plugin / "skills/pre-call-prep/SKILL.md").read_text())

    def test_unportable_skill_fails_the_build_and_writes_nothing(self):
        skill = self.plugin / "skills/talyx-pdf/SKILL.md"
        for bad in ("Run `python3 ../format/talyx_pdf.py`.", "Run `${CLAUDE_PLUGIN_ROOT}/x.py`.",
                    "Save to ~/.pcp/profile.yaml.", "Run `python3 scripts/missing.py`."):
            with self.subTest(bad):
                original = skill.read_text()
                skill.write_text(original + "\n" + bad + "\n")
                before = self.snapshot()
                r = self.generate()
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("FAIL", r.stdout)
                self.assertEqual(self.snapshot(), before)
                skill.write_text(original)

    def test_frontmatter_that_is_not_yaml_fails_the_build(self):
        skill = self.plugin / "skills/talyx-pdf/SKILL.md"
        text = skill.read_text()
        start = text.index("description:")
        end = text.index("\n---", start)
        skill.write_text(text[:start] + "description: Render a PDF: one page. Use when asked." + text[end:])
        r = self.generate("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("not valid YAML", r.stdout)

    def test_comma_split_registry_value_fails_the_build(self):
        reg = self.plugin / "skills/pre-call-prep/pcp.yaml"
        text = reg.read_text()
        quoted = '{label: "Fast -- 6 families, about 3 minutes", '
        self.assertIn(quoted, text)
        reg.write_text(text.replace(quoted, "{label: Fast -- 6 families, about 3 minutes, "))
        r = self.generate("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("stray key", r.stdout)

    def test_page_ladder_drift_between_registry_and_renderer_fails(self):
        reg = self.plugin / "skills/pre-call-prep/pcp.yaml"
        reg.write_text(reg.read_text().replace("{name: compact, body_pt: 10.0", "{name: compact, body_pt: 9.5"))
        r = self.generate("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("page ladder differs", r.stdout)

    # -- host contracts --------------------------------------------------------------------------

    def test_every_catalog_resolves_to_the_one_payload(self):
        for catalog in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json", ".cursor-plugin/marketplace.json"):
            self.assertEqual(self.payload(catalog), self.plugin.resolve(), catalog)
        codex, = json.loads((self.root / ".agents/plugins/marketplace.json").read_text())["plugins"]
        self.assertEqual(set(codex["policy"]), {"installation", "authentication"})
        self.assertIn("category", codex)

    def test_agent_plugins_manifest_matches_the_published_schema(self):
        schema = json.loads((self.root / "build/schemas/plugin.schema.json").read_text())
        manifest = json.loads((self.plugin / "plugin.json").read_text())
        jsonschema.validate(manifest, schema)
        bad = {**manifest, "commands": "./commands"}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)
        interface = manifest["extensions"]["com.openai"]["interface"]
        for key in ("logo", "logoDark"):
            self.assertTrue((self.plugin / interface[key]).is_file(), key)

    def test_gemini_command_is_valid_toml_with_args_placeholder(self):
        try:
            import tomllib
        except ModuleNotFoundError:   # Python 3.10
            import tomli as tomllib
        doc = tomllib.loads((self.plugin / "commands/pcp.toml").read_text())
        self.assertIn("{{args}}", doc["prompt"])
        self.assertNotIn("$ARGUMENTS", doc["prompt"])
        md = (self.plugin / "commands/pcp.md").read_text()
        self.assertIn("$ARGUMENTS", md)
        self.assertTrue(md.startswith("---\n"), "hosts ignore command frontmatter that is not first")
        self.assertIn("argument-hint", yaml.safe_load(md.split("---")[1]))

    def test_skill_frontmatter_follows_agent_skills_spec(self):
        for skill in sorted((self.plugin / "skills").iterdir()):
            text = (skill / "SKILL.md").read_text()
            self.assertTrue(text.startswith("---\n"), f"{skill.name}: hosts ignore frontmatter that is not first")
            fm = yaml.safe_load(text.split("---")[1])
            self.assertEqual(fm["name"], skill.name)
            self.assertLessEqual(len(fm["description"].encode()), 1024)
            self.assertTrue((skill / "agents/openai.yaml").is_file())

    # -- the installed payload -------------------------------------------------------------------

    def installed_copy(self):
        dest = self.tmp / "installed" / "pcp"
        shutil.copytree(self.payload(".claude-plugin/marketplace.json"), dest)
        return dest

    def test_payload_carries_no_development_material(self):
        installed = self.installed_copy()
        forbidden = {"build", "tests", "evals", "dist", "adapters", ".git", "__pycache__", "plugin.source.json"}
        for path in installed.rglob("*"):
            self.assertFalse(forbidden & set(path.relative_to(installed).parts), path)
        self.assertEqual({p.name for p in (installed / "skills").iterdir()}, {"pre-call-prep", "talyx-pdf"})

    def test_installed_scripts_run_from_an_unrelated_working_folder(self):
        installed = self.installed_copy()
        elsewhere = self.tmp / "client-folder"
        elsewhere.mkdir()
        fixture = ROOT / "evals/fixtures/control_12.md"
        env = {**os.environ, "PCP_PROFILE": str(self.tmp / "p" / "profile.yaml")}
        skill = installed / "skills/pre-call-prep"
        r = subprocess.run([sys.executable, str(skill / "scripts/eval.py"), "duf", str(fixture)],
                           cwd=elsewhere, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["bound"], 12)
        r = subprocess.run([sys.executable, str(skill / "scripts/profile.py"), "inspect"],
                           cwd=elsewhere, capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(json.loads(r.stdout)["status"], "missing", r.stderr)
        for s in ("pre-call-prep", "talyx-pdf"):
            r = subprocess.run([sys.executable, str(installed / "skills" / s / "scripts/talyx_pdf.py"), "--help"],
                               cwd=elsewhere, capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(list(elsewhere.iterdir()), [], "a script wrote into the caller's folder")

    def test_perplexity_zip_is_the_skill_folder_and_runs_extracted(self):
        self.assertEqual(self.generate().returncode, 0)
        zpath = self.root / "dist/perplexity/pre-call-prep.zip"
        with zipfile.ZipFile(zpath) as zf:
            names = zf.namelist()
            self.assertIn("SKILL.md", names)
            self.assertLessEqual(len(names), 100)
            skill = self.plugin / "skills/pre-call-prep"
            for n in names:
                self.assertEqual(zf.read(n), (skill / n).read_bytes(), n)
            zf.extractall(self.tmp / "px")
        self.assertLessEqual(zpath.stat().st_size, 10 * 1024 * 1024)
        r = subprocess.run([sys.executable, str(self.tmp / "px/scripts/eval.py"), "duf",
                            str(ROOT / "evals/fixtures/control_broken.md")],
                           cwd=self.tmp, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 1, "the extracted counter must still fail the negative control")
        self.assertEqual(json.loads(r.stdout)["unbound"], 3)

    def test_maintainer_self_test_passes_and_can_fail(self):
        r = subprocess.run([sys.executable, "evals/pcp_eval.py", "self-test"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        (self.root / "evals/fixtures/control_12.md").write_text("# empty\n")
        r = subprocess.run([sys.executable, "evals/pcp_eval.py", "self-test"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
