---
name: tramontina-cortex-cicd
description: The Tramontina-specific GitLab CI/CD workflow for the Cortex Framework V7 repo (git.tramontina.net/databricks/cortex) — protected-branch/Merge-Request flow, the agent-vs-human division of labor, git ls-remote as the source of truth, the three validation gates, and the CORTEX_CONFIG File-variable duality. Use this whenever committing, pushing, opening or merging an MR, running cortex-build/dataform, editing .gitlab-ci.yml or CI/CD variables, promoting to prod, or diagnosing why a pipeline built or ran differently than a local build in this repo. Consult it before ANY git or pipeline action here, even if the request looks routine — the esteira has non-obvious rules that have caused repeated, expensive mistakes.
---
# Tramontina Cortex V7 — GitLab CI/CD Esteira

This skill captures how work actually ships in the Tramontina Cortex repo (`git.tramontina.net/databricks/cortex`). None of this is in upstream Cortex docs; all of it was learned by hitting the walls. It governs git, Merge Requests, the pipeline, CI/CD variables, and who does what. For the Iceberg materialization mechanics themselves (definition boilerplate, table_settings, run vars, SQL bug catalog), see the `materialize-as-iceberg` skill — this skill is the process around it.

---

## Phase 0: The division of labor (READ FIRST)

Two actors work this repo and their responsibilities do NOT overlap. Crossing the line is how things break.

**The agent (editing in the IDE, e.g. Antigravity):**
*   ONLY edits files in the local git working tree.
*   Does NOT run `cortex-build` or `dataform`, does NOT query BigQuery, does NOT touch the GitLab UI (MRs, CI/CD variables, pipelines), does NOT run `git push`/merge on its own authority.
*   Proposes exact commands for the human to run, and interprets their output.

**The human (Bruno):**
*   Runs every build, `dataform compile`, and BigQuery query (BigQuery is reached through the **web console** because of an IPv6 networking constraint on the local machine — plan for console-based validation, not CLI `bq`).
*   Performs all git operations (commit/push/MR) and all GitLab UI edits (CI/CD variables, pipeline runs).
*   Is the only one who can confirm what actually happened in the environment.

Practical consequence: when the agent "knows" something passed, that is a hypothesis. The human running the command and pasting the output is the fact. Do not advance a git or pipeline step on predicted success — advance on observed success.

---

## Phase 1: Branches, Merge Requests, and the target-branch trap

*   `develop` and `main` are **protected**. Nothing is pushed to them directly. Everything is: feature/fix branch → push → **Merge Request** → merge.
*   **`develop` is the integration branch. `main` is production.** The normal MR target is **`develop`**. Promotion to prod is a deliberate, separate `develop → main` MR (Phase 6).
*   **The single most repeated mistake in this repo is an MR whose target defaulted to `main` instead of `develop`.** The GitLab "new MR" screen frequently pre-fills the target as `main`. Before creating ANY MR, visually confirm the target field reads `develop` and change it if it says `main`. An MR merged into `main` by accident requires a revert on `main` (via the UI) plus conflict cleanup on `develop` — hours of recovery. Check the target every single time; it is not a formality.
*   Use the MR link GitLab prints at the end of `git push` — it pre-fills the source branch. You still must set the target.
*   Do NOT mark the MR as Draft unless you specifically want to block merge.

**The MR pipeline `compile`/SA-key behavior is EXPECTED, not a failure.** In MR context the pipeline cannot read the service-account key, so SA-key-dependent jobs fail with e.g. `Could not read json file /tmp/sa-key.json`. That failure does not block the merge and is not a signal of a code problem. What matters in the MR pipeline is the `compile` job. (Note: `compile` validates structure and `require`s, not SQL — see Phase 3.)

---

## Phase 2: git ls-remote is the source of truth; local tracking refs lie

The local branch-tracking state (`Your branch is up to date with 'origin/...'`) is **not** reliable in this repo — branches get deleted server-side on merge, force-pushes happen, and the local ref goes stale. Trust the server, not the local echo.

*   Before and after any push, confirm the server state directly:
    ```
    git ls-remote <remote> refs/heads/<branch>
    git log --oneline -1
    ```
    The `ls-remote` hash MUST equal the local `git log` hash. If they differ, stop and reconcile before doing anything else.
*   A push that prints `* [new branch]` means the branch did not exist on the server (it was deleted on a prior merge) and the push **recreated** it — this is normal after a merge, not an error.
*   Never trust "up to date with origin/X" to mean X still exists on the server. Verify with `ls-remote`.
*   Ids (commit SHAs, MR ids) come only from real tool output or a link the human pasted — never guess or hand-edit them.

---

## Phase 3: The three validation gates (build → compile → run)

Every class of bug in this repo is caught by exactly one gate, and each gate is blind to what the next one catches. Run them in order; **never commit or merge on an earlier gate alone.**

| Gate | Command (human runs) | Catches | Blind to |
|---|---|---|---|
| 1. Build | `Remove-Item -Recurse -Force build_out ; uv run cortex-build --config config/config.yaml --output-dir build_out` | YAML / `table_settings` structure; `.js` copied into build | `require()` resolution; ALL SQL |
| 2. Compile | `cd build_out ; dataform compile ; cd ..` | `require()` resolution; Dataform action structure | ALL SQL (executes nothing against BigQuery) |
| 3. Run | pipeline run (post-merge) or an isolated action run in BigQuery | real SQL and data: syntax, aliases, key cardinality, missing sources | — |

Rules:
*   **`cortex-build` passing is weak evidence.** Always follow it locally with `dataform compile` — that is the gate that catches an invented/relative `require`. The pipeline runs compile; reproduce it locally so the error is found before the push.
*   **`dataform compile` passing says nothing about SQL.** A whole family of failures (orphaned `AND` on first run, missing table alias, non-unique MERGE key, wrong column) compiles cleanly and only fails at run. For anything touching SQL, validate in the BigQuery console before committing — the console is the SQL dry-run.
*   "It compiled, you can commit" is the exact phrasing that has repeatedly preceded a broken run here. Do not accept it. The proof for an incremental/Iceberg product is the run materializing the table, verified in BigQuery.

---

## Phase 4: Committing cleanly (never `git add .`)

The working tree routinely contains throwaway artifacts the agent generated — `fix_*.py` helper scripts, `compile_out.json`, the entire `build_out/` directory. These must NEVER enter a commit.

*   **Stage by explicit path, never `git add .`:**
    ```
    git add "src/data_modules/custom_tramontina/sap/products/*/definitions/*.js"
    git add "src/data_modules/custom_tramontina/sap/products/*/table_settings.default.yaml"
    ```
*   After staging, run `git status` and confirm ONLY the intended files are staged and the throwaway files remain under "Untracked" (out of the commit). If any `fix_*.py` / `*.json` / `build_out` is staged, unstage it before committing.
*   Add `build_out/`, `compile_out.json`, and `fix_*.py` to `.gitignore` — but edit `.gitignore` through the **IDE editor**, not `Add-Content`/`Set-Content` (PowerShell can inject a BOM; see Phase 5).
*   Keep commits scoped to one fix with a message that says what changed and why; small diffs are easy to verify against `git status` before pushing.

---

## Phase 5: Editing `.gitlab-ci.yml` and config files safely

*   **NEVER write `.gitlab-ci.yml` (or any YAML the pipeline parses) with PowerShell `Set-Content`/`Add-Content`** — they can emit a BOM / control character that breaks YAML parsing. Edit and save through the IDE editor only.
*   The repo's `.gitlab-ci.yml` uses YAML anchors for the job bases (`*dev_base`, `*prod_base`, `*setup`) and per-group `ACTIONS_*` variables. Run jobs are `when: manual` (triggered with ▶ in the pipeline UI). Group deploys are keyed by `DEPLOY_GROUP` (e.g. `notas_fiscais`, `masterdata_custom`).
*   Actions that are commented out in `.gitlab-ci.yml` effectively make the corresponding variable empty — a commented action is not "disabled safely", it silently yields nothing to select.

---

## Phase 6: The CORTEX_CONFIG File-variable duality (the pipeline does NOT build from the repo config)

This is the highest-value, least-obvious fact about this esteira. `config/config.yaml` in the repo is **gitignored**, and the pipeline does not build from it. The pipeline does:

```
cp "$CORTEX_CONFIG_FILE" config/config.yaml   # overwrites the repo file
uv run cortex-build --config config/config.yaml
```

`$CORTEX_CONFIG_FILE` points at a GitLab **File-type CI/CD variable** — `CORTEX_CONFIG_DEV` for dev, `CORTEX_CONFIG_PROD` for prod. So the effective build config is the UI variable, not the file in your branch.

Consequences:
*   Registering a new custom module (namespace + product `modulePath` entries) in your local `config/config.yaml` is **not enough**. You MUST also paste the updated config into the corresponding File CI/CD variable in the GitLab UI, or the pipeline will never build those products — and the run will report `No actions to run` with a fully-populated `--actions` variable (a false green).
*   When something builds locally but is absent from the pipeline, compare the "Generating data product" lines: local build lists the custom products, pipeline build doesn't → the CI config variable is stale. Update `CORTEX_CONFIG_DEV`/`CORTEX_CONFIG_PROD` to match.
*   Before pasting, confirm the variable's project/location match the environment: the dev config must point at the dev project (`tra-prd-cortex-aecorsoft`), the prod config at the prod project (`tra-prd-cortex`). Pasting a dev config into the prod variable (or vice-versa) points the build at the wrong project.
*   To dump the *effective* config the pipeline built from, a temporary `grep -n 'namespaces\|modulePath\|custom_' config/config.yaml` step in the job is safe (those lines are not secret). Remove the debug line after diagnosing. Do not dump the whole config if it might contain anything sensitive.

---

## Phase 7: Recovering from a wrong-target or accidental merge

If an MR lands on the wrong branch (typically `main` when it should have been `develop`):
1.  Do the recovery in the GitLab UI, on the branch that received the bad merge — a **Revert** of the merge commit, targeting the same branch (`main`), via the UI's revert button.
2.  If `develop` also picked up the change and later conflicts, resolve with intent: `git checkout --ours <path>` for files where the branch's version should win, then re-verify with `ls-remote`.
3.  When in doubt, take a fresh `git ls-remote` snapshot of `develop`, `main`, and the working branch BEFORE acting — you cannot recover safely without knowing where each branch actually is on the server.
4.  Never force-push to a protected branch to "fix" it. Use MRs/reverts through the UI.

Close any revert MR that itself targets the wrong branch before merging it — a revert aimed at `develop` when the bad merge was on `main` compounds the problem.

---

## Phase 8: Promoting to PROD

PROD is `tra-prd-cortex` (project) with the `tra-cortex-iceberg-prod` bucket; the branch is `main`. Promotion is deliberate:

1.  **Source `raw` must exist in prod first.** A product cannot materialize where its source raw tables are absent. The prod `raw` is replicated separately (AecorSoft CDC); confirm every source table the products consume is present in prod's `raw` before promoting. Compare dev vs prod with an `EXCEPT DISTINCT` over each `raw` dataset's `INFORMATION_SCHEMA.TABLES`. Missing sources are a hard prerequisite owned by the replication team, not something code can work around.
2.  **Replicate config to `CORTEX_CONFIG_PROD`** (Phase 6) — pointing at the prod project, not dev.
3.  **Create/confirm the prod pipeline schedules** keyed by `DEPLOY_GROUP` (e.g. `notas_fiscais`, `masterdata_custom`), target `main`.
4.  **MR `develop → main`** (verify the target is `main` here — this is the one case where `main` is correct).
5.  **Bucket hygiene before first prod deploy:** if the prod Iceberg bucket holds residue, clean it in the correct order — DROP the prod BigQuery tables FIRST, then empty the bucket — never the reverse (a BigLake table pointing at a deleted path is broken). Always `gcloud storage ls` the bucket to see what will be removed BEFORE any `rm --recursive`; a bucket delete has no undo. Prefer the narrowest path (`.../cortex_data_products/**`) over the whole bucket.
6.  Validate prod the same way dev was validated (Phase 3 gate 3 + the Iceberg skill's Phase 6 checks): Iceberg format, key uniqueness, referential integrity, storage_uri under the prod bucket.

---

## Phase 9: Environment quick-reference

*   **DEV project:** `tra-prd-cortex-aecorsoft` (a sandbox despite the `prd` in the name). Branch `develop`. Iceberg bucket `tra-cortex-iceberg-dev`.
*   **PROD project:** `tra-prd-cortex`. Branch `main`. Iceberg bucket `tra-cortex-iceberg-prod`.
*   BigQuery location: `US`. Tenant/client `mandt = '400'`. SAP version `s4`.
*   Datasets: `raw` (AecorSoft CDC, data arrives ready — the foundation does NOT re-materialize it), `data_products`, `data_consumption`.
*   Repo reached over VPN. GitLab runner is k8s (pod deadline ~1h). BigQuery reached via the web console (IPv6 constraint on the local machine).
*   Custom products live under the `custom_tramontina` namespace.

---

## Cross-References
*   [materialize-as-iceberg](../materialize_as_iceberg/SKILL.md) — Iceberg definition boilerplate, `table_settings`, run vars, and the SQL bug catalog (orphaned AND, missing alias, non-unique key, dedup + full-refresh). This CI/CD skill is the process; that one is the mechanism.
*   [create-data-product](../create_data_product/SKILL.md) / [update-data-product](../update_data_product/SKILL.md) — product authoring workflows that feed into this esteira.
