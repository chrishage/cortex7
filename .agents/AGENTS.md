# Cortex 7 Extensibility & Development Assistant

System instructions and task guidelines for working with Google Cloud Cortex Framework V7 and modular developer agent skills.

---

## Lifecycle Slash Commands

When the user issues any of the following commands, you must immediately load the referenced `.agents/skills/<skill_name>/SKILL.md` instructions into your active context and follow the workflow steps, quality gates, and validation checks outlined therein. Do not begin writing or modifying any code until you have fully parsed the relevant skill instructions.

| Command | Associated Skill | Target Action & Purpose |
|:---|:---|:---|
| `/using-cortex-skills` | [using_cortex_skills](file:///.agents/skills/using_cortex_skills/SKILL.md) | Discovers and invokes Cortex agent skills. Use when starting a session or when you need to discover which skill applies to the current task. |
| `/setup-cortex-config` | [setup_cortex_config](file:///.agents/skills/setup_cortex_config/SKILL.md) | Guides the interactive slot-filling setup, targets configuration, and environment setup of the main `config.yaml`. |
| `/create-data-product` | [create_data_product](file:///.agents/skills/create_data_product/SKILL.md) | Scaffolds standard directory structure, parses source datasets, maps fields, and creates a new Cortex data product. |
| `/update-data-product` | [update_data_product](file:///.agents/skills/update_data_product/SKILL.md) | Workflow for impact analysis, research documentation, coding updates, and validation for changing existing products. |
| `/materialize-as-iceberg` | [materialize_as_iceberg](file:///.agents/skills/materialize_as_iceberg/SKILL.md) | Materializes a data product as an Apache Iceberg managed (BigLake) table in GCS for external engines (e.g. Databricks). Invoked on its own or referenced by create/update when the product must be Iceberg. |
| `/validate-data-product` | [validate_data_product](file:///.agents/skills/validate_data_product/SKILL.md) | Performs structural checks, syntax checking, pipeline execution, and runs the pytest validation suite. |
| `/build-and-deploy` | [build_and_deploy_data_product](file:///.agents/skills/build_and_deploy_data_product/SKILL.md) | Syncs environment variables, identifies configuration profiles, builds Dataform models, and deploys data products. |
| `/query-sap-ddic` | [query_sap_ddic](file:///.agents/skills/query_sap_ddic/SKILL.md) | Inspects and dumps SAP table schemas directly from replicated SAP DDIC tables in BigQuery. |
| `/generate-er-diagram` | [generate_er_diagram](file:///.agents/skills/generate_er_diagram/SKILL.md) | Extracts schema definitions, automatically infers entity relationships via SAP field suffixes, and generates visual ERDs. |
| `/tramontina-cortex-cicd` | [tramontina_cortex_cicd](file:///.agents/skills/tramontina_cortex_cicd/SKILL.md) | The Tramontina GitLab esteira: protected-branch/MR flow, `git ls-remote` as source of truth, the three validation gates (build→compile→run), the agent-vs-human division of labor, and the CORTEX_CONFIG File-variable duality. Consult before any git or pipeline action in this repo. |

---

## Version Control & CI/CD (always in effect for this repo)

This repo ships through a protected-branch GitLab esteira (`git.tramontina.net/databricks/cortex`) with non-obvious rules that have caused repeated, expensive mistakes. Before ANY git operation (commit, push, Merge Request), pipeline run, `.gitlab-ci.yml` or CI/CD-variable edit, or prod promotion, load and follow [tramontina_cortex_cicd](file:///.agents/skills/tramontina_cortex_cicd/SKILL.md) — even for routine-looking actions. This is not only a slash command; treat its invariants as standing rules whenever you touch version control or the pipeline. Key invariants:

*   **Division of labor:** the agent only edits files in the local working tree. It does NOT run `cortex-build`/`dataform`, does NOT query BigQuery, does NOT operate the GitLab UI, and does NOT push/merge on its own authority. The human runs builds, queries, and all git/UI operations; observed output — not predicted success — is what advances a step.
*   **Never `git add .`** — stage by explicit path. Throwaway artifacts (`fix_*.py`, `compile_out.json`, `build_out/`) must never enter a commit.
*   **MR target is `develop`, not `main`.** The GitLab new-MR screen often pre-fills `main`; verify and correct the target every time. `develop → main` is a separate, deliberate prod promotion.
*   **`git ls-remote <remote> refs/heads/<branch>` is the source of truth** over local tracking refs, which go stale (branches are deleted server-side on merge). Verify server hashes before and after push.
*   **Three validation gates, in order:** `cortex-build` (structure) → `dataform compile` (require/action structure) → run in BigQuery (real SQL). Each gate is blind to what the next catches; compiling proves nothing about SQL. Never commit or merge on an earlier gate alone.
*   **The pipeline builds from the CORTEX_CONFIG File CI/CD variable, not the repo config.** `config/config.yaml` is gitignored and overwritten at build time by `$CORTEX_CONFIG_FILE` (`CORTEX_CONFIG_DEV`/`CORTEX_CONFIG_PROD`). Registering a custom module locally is not enough — the matching UI File-variable must be updated too, or the run reports `No actions to run` with a populated actions variable (a false green).
*   **YAML the pipeline parses (e.g. `.gitlab-ci.yml`) must be saved via the IDE editor, never PowerShell `Set-Content`/`Add-Content`** (BOM injection breaks parsing).

---

## Primary Code Structure & Formats

*   **Data Products**: All custom modules and transformations must reside under `src/data_modules/<namespace>/[...optional_segments...]/<type>/` with configurations at `config/<namespace>/[...optional_segments...]/<type>/`. The first segment must be the namespace (e.g., `cortex`), the last segment (the leaf) must match the `type` defined in the manifest, and any middle segments are optional organizational folders (e.g., `<source>/products`).
*   **Data Foundation**: Core core/foundation pipelines reside under `src/data_modules/cortex/<source>/foundations/sap/` and configurations under `config/cortex/<source>/foundations/sap/`.
*   **Language**: Cortex V7 targets **Dataform**. Data models and tables should be authored as Dataform `.js` or `.sqlx` scripts in their respective directories. Do not write legacy raw SQL formats.
*   **Relationship Discovery**: When building relationships dynamically, always refer to field names. SAP-replicated tables map primary/foreign key bounds based on raw SAP suffix indicators (like `_lifnr` or `_matnr`), keeping in mind to ignore common client identifiers (`mandt`, `client`), ingestion timestamps, and technical system fields.
