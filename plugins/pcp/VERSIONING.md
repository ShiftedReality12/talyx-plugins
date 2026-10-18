# Versioning the pcp plug-in

## One version, one place

`registry_version` in `plugins/pcp/pcp.yaml` is the version of record. Everything else is written from it or checked against it:

- `build/plugin.source.json` holds the same number; `build/adapters.py` writes every host manifest and marketplace entry from it.
- `render_skill.py` writes the version into the generated headers (`SKILL.md`, `INVENTORY.md`, the chat knowledge files) and `pcp.json`.
- `plugins/pcp/CHANGELOG.md`'s newest entry carries it.
- `python3 plugins/pcp/eval.py versions` (C30) fails if any of them disagrees. It runs in the pre-commit hook, in CI and in `eval.py self-test`.

To release: edit `registry_version` and its header comment in `pcp.yaml` and `version` in `build/plugin.source.json`, add the CHANGELOG entry, run
`python3 plugins/pcp/render_skill.py` and `python3 build/adapters.py`, then `eval.py versions`. Never edit a generated file or a manifest by hand.

## Semver for this plug-in

- **Patch (3.1.x):** fixes and wording, no behaviour lost. Nothing of the 2.1.0 baseline is removed or weakened; `eval.py parity --strict`, `gates` and `skill` pass.
- **Minor (3.x.0):** additive behaviour: a new check, source type, setup question, host or reference; existing briefs still pass.
- **Major (x.0.0):** a change to the schema or the brief's layout: blocks added, removed or renamed, the page budget, the setup answers' meaning. A major needs
  its `evals/DECISIONS.yaml` entries approved and the frozen targets refit.

A host decides whether to offer an update by comparing this number, so two different builds must never carry the same one.

## Layout: what ships and what does not

What a host installs or a user uploads is `plugins/pcp/` (the plug-in), `adapters/` (chat-app and Perplexity files), the marketplace files at the repo root
and `build/`. Material that is not part of the plug-in lives outside `plugins/pcp/`: the launch-film creative framework moved from
`plugins/pcp/film/` to `marketing/film/` (`git mv`, 3.1.1). `build/adapters.py` lists `marketing` in `NOT_SHIPPED`, so its name check does not scan it. That is the
only change to the scan: the rule (`plain_words.names_banned`, including "dossier") is unchanged and still covers everything that ships. Put any new non-shipped
folder under `marketing/` (or add it to `NOT_SHIPPED` deliberately), never under `plugins/pcp/`.

## Releases

- One **annotated** tag per release: `pcp-vX.Y.Z`, on the commit that carries that version (`git tag -a pcp-v3.1.1 -m "..."`). The release candidates before the
  tag convention are `pcp-3.1.0-rc1` and `pcp-3.1.0-rc2`.
- Release branches: `release/pcp-X.Y.Z`, cut when a version needs fixes after its tag. Work branches are named for the work (`restore-2026-10-16`).
- Push releases to `origin` (ShiftedReality12/talyx-plugins) only. The talyx-ai repo (`upstream`) is changed by pull request from its owners, never by a push from here.

## Where the parity baseline lives

The standard the plug-in is held to is the original talyx-ai 2.1.0, frozen in `plugins/pcp/evals/`:

- `baseline-2.1.0.json`: 403 items (registry values, eval commands, renderer flags), built from `upstream/main` `993a8be` by `build/baseline.py`; never edited.
- `DECISIONS.yaml`: the only way an item differs from it (approved entries, pins, schema-lock approvals).
- `schema.lock.json`: hashes of the schema sections. `ref21.py`: the 2.1.0 checks, verbatim, run by `eval.py gates`.

## Branch map (as of 2026-10-18; no branch is deleted or renamed)

Current build: **`restore-2026-10-16`** (local and `origin`), carrying 3.1.2. Everything below that is "in" it is an ancestor of it.

| Branch | Tip | What it is | Superseded? |
|---|---|---|---|
| `restore-2026-10-16` (+ `origin/restore-2026-10-16`) | 3.1.2 line | Restored toward 2.1.0, trimmed, with Daniel's Oct 17 decisions and the 3.1.2 fixes. The release branch of 3.1.1 and 3.1.2. | No: current |
| `main` (local) | `51b2a65`, 3.0.0 | Local `main` stopped at 3.0.0, 63 commits behind `origin/main`. | Yes, by `origin/main` and `restore-2026-10-16` |
| `origin/main` (and `origin/HEAD`) | `32badc4`, labelled 3.1.0 | The pre-restore 3.1.0 build (`pcp-3.1.0-rc2`). Its version string is 3.1.0 but it lacks the restore, trim and decisions. | Yes, by 3.1.2 on `restore-2026-10-16`, until Daniel advances `main` to it |
| `pcp-update-2026-10-13` (+ origin) | `32badc4` | The branch the 3.1.0 work was done on; same commit as `origin/main`. | Yes, by `restore-2026-10-16` |
| `pcp-v3-intelligence-brief` (+ origin) | `51b2a65`, 3.0.0 | The 3.0.0 Intelligence Brief work; same commit as local `main`. | Yes |
| `brief-rework` | `6122e8d`, 2.1.0 line | The Oct 9 renderer rework (3-page brief with bookmarks), one commit ahead of `upstream/main`. | Yes (its work is in 3.0.0 and later) |
| `adapters-bugfixes` (+ origin) | `8510d43` | The 2.1.0 install-on-every-host work; merged into `upstream/main` (PR #1). | Yes, by `upstream/main` |
| `pcp-marketplace` | `8510d43` | Same commit as `adapters-bugfixes`. | Yes |
| `talyx-ai-v2.0.0` (+ origin) | `bec6175` | The 2.0.0 snapshot (Sep 23). | Yes (historical) |
| `multi-host-adapters` (+ origin) | `ca53a99` | Sep 25 2.1.0 packaging variant (simplified repo layout, CI); not merged. | Yes, by 2.1.0 on `upstream/main` (not an ancestor of the current build) |
| `parameterize-all` (+ origin) | `ed19a63` | Sep 25 parameterization experiment on the 2.1.0 line; not merged. | Yes, by the registry-driven build (not an ancestor) |
| `pcp-packaging` | `9374686` | Sep 28 2.1.0 packaging variant; not merged, no origin copy. | Yes (not an ancestor) |
| `setup-script` (+ origin) | `96d38fd` | Sep 28 merge of `adapters-bugfixes` with a setup-script variant; not merged. | Yes (not an ancestor) |
| `upstream/main` | `993a8be`, 2.1.0 | talyx-ai's original plug-in: the parity standard. Not ours to push to. | No: it is the baseline, not a build to ship |

Tags: `pcp-3.1.0-rc1` (`45f423e`), `pcp-3.1.0-rc2` (`32badc4`), `pcp-v3.1.1` (the 3.1.1 release), `pcp-v3.1.2` (the 3.1.2 release).
