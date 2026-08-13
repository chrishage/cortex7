/**
 * Copyright 2026 Google LLC
 * Licensed under the Apache License, Version 2.0
 *
 * Iceberg helper for Cortex Framework — supports FULL REFRESH and INCREMENTAL.
 *
 * WHY THIS EXISTS:
 * The Dataform publish() API does NOT emit `WITH CONNECTION ... OPTIONS(table_format='ICEBERG')`
 * from a `bigquery.iceberg` config block — it silently creates a NATIVE BigQuery table.
 * This helper emits explicit Iceberg DDL/DML via a Dataform `operations` action.
 *
 * MODES (decided by tableConfig.materializationType):
 *   - "table"       -> full refresh: CREATE OR REPLACE TABLE ... AS <select>
 *   - "incremental" -> BigQuery scripting: IF table not exists THEN CREATE ... AS <select>
 *                      ELSE MERGE <delta> INTO table ON uniqueKeys. Always EXPORT METADATA.
 *
 * The product SELECT calls incremental.getFilter(ctx, ...) which uses
 * ctx.incremental()/ctx.when()/ctx.self(). We shim these:
 *   - full refresh  -> incremental()=false (filter collapses -> full scan)
 *   - incremental   -> incremental()=true  (filter active; on 1st run MAX() returns
 *                      the 1900 default so ALL rows are brought in, which is correct)
 *
 * USAGE (product .js):
 *   const iceberg_helper = require("includes/iceberg_helper.js");
 *   iceberg_helper.publishProduct(actionName, publishConfig, tableConfig, (ctx) => `SELECT ...`);
 */

function isIceberg(tableConfig) {
  return !!(tableConfig && tableConfig.bigquery && tableConfig.bigquery.iceberg
    && tableConfig.bigquery.iceberg.bucketName);
}

function buildStorageUri(iceberg, tableName) {
  const bucket = iceberg.bucketName;
  const root = iceberg.tableFolderRoot ? iceberg.tableFolderRoot.replace(/\/+$/, "") + "/" : "";
  const sub = iceberg.tableFolderSubpath ? iceberg.tableFolderSubpath.replace(/\/+$/, "") + "/" : "";
  return `gs://${bucket}/${root}${sub}${tableName}`;
}

/**
 * Shim ctx for the operations context.
 * @param {boolean} incrementalMode whether incremental() should report true.
 */
function shimContext(ctx, fqTable, incrementalMode) {
  return {
    ref: (...args) => ctx.ref(...args),
    resolve: (...args) => ctx.resolve(...args),
    incremental: () => incrementalMode,
    when: (cond, trueBranch, falseBranch = "") => (cond ? trueBranch : falseBranch),
    self: () => fqTable,
  };
}

/**
 * Extract plain column names from publishConfig.columns.
 * columns may be an object {name: description} or array of names.
 */
function columnNames(publishConfig) {
  const cols = publishConfig.columns;
  if (!cols) return [];
  if (Array.isArray(cols)) return cols.slice();
  return Object.keys(cols);
}

function publishProduct(actionName, publishConfig, tableConfig, queryFn) {
  if (!isIceberg(tableConfig)) {
    // Native Cortex behaviour (table / view / incremental).
    publish(actionName, publishConfig).query(queryFn);
    return;
  }

  const iceberg = tableConfig.bigquery.iceberg;
  const matType = tableConfig.materializationType || "incremental";
  const project = publishConfig.database;
  const dataset = publishConfig.schema;
  const tableName = publishConfig.name;
  const fqTable = `\`${project}.${dataset}.${tableName}\``;

  // Per-environment overrides via Dataform vars (official mechanism).
  // The CI pipeline passes them: dataform run --vars=icebergBucket=...,icebergConnection=...
  // In the .js they are available at dataform.projectConfig.vars.
  // Fall back to the table_settings values when the vars are absent (local runs).
  const dfVars = (typeof dataform !== "undefined" && dataform.projectConfig && dataform.projectConfig.vars) || {};
  const varConn = dfVars.icebergConnection || null;
  const varBucket = dfVars.icebergBucket || null;

  const connection = varConn || iceberg.connection || "DEFAULT";
  const connClause = connection === "DEFAULT"
    ? "WITH CONNECTION DEFAULT"
    : `WITH CONNECTION \`${connection}\``;
  const fileFormat = iceberg.fileFormat || "PARQUET";
  const effectiveIceberg = varBucket ? Object.assign({}, iceberg, { bucketName: varBucket }) : iceberg;
  const storageUri = buildStorageUri(effectiveIceberg, tableName);
  const optionsClause =
    `OPTIONS(file_format='${fileFormat}', table_format='ICEBERG', storage_uri='${storageUri}')`;

  const opConfig = {
    type: "operations",
    name: actionName,
    database: project,
    schema: dataset,
    tags: publishConfig.tags,
    hasOutput: true,
    description: publishConfig.description
  };

  operate(actionName, opConfig).queries((ctx) => {
    const exportSql = `EXPORT TABLE METADATA FROM ${fqTable}`;

    // ---------- FULL REFRESH ----------
    if (matType === "table") {
      const selectSql = queryFn(shimContext(ctx, fqTable, /*incremental=*/false));
      const createSql =
        `CREATE OR REPLACE TABLE ${fqTable}
${connClause}
${optionsClause}
AS
${selectSql}`;
      return [createSql, exportSql];
    }

    // ---------- INCREMENTAL ----------
    // TWO versions of the SELECT are needed:
    //  - selectFull  (incremental=false): NO self-referencing filter. Used by the
    //    CREATE ... WHERE FALSE so it does not read the not-yet-created table.
    //  - selectDelta (incremental=true): with the incremental filter (reads MAX from
    //    the table). Used by the MERGE, where the table is guaranteed to exist.
    const selectFull = queryFn(shimContext(ctx, fqTable, /*incremental=*/false));
    const selectDelta = queryFn(shimContext(ctx, fqTable, /*incremental=*/true));
    const uniqueKeys = publishConfig.uniqueKey || [];
    if (uniqueKeys.length === 0) {
      throw new Error(
        `[iceberg_helper] Incremental Iceberg table '${tableName}' requires uniqueKey in publishConfig.`);
    }
    const cols = columnNames(publishConfig);

    const onClause = uniqueKeys.map(k => `T.\`${k}\` = S.\`${k}\``).join(" AND ");
    const updateSet = cols.length > 0
      ? cols.map(c => `T.\`${c}\` = S.\`${c}\``).join(",\n    ")
      : null;
    const insertCols = cols.length > 0 ? cols.map(c => `\`${c}\``).join(", ") : null;
    const insertVals = cols.length > 0 ? cols.map(c => `S.\`${c}\``).join(", ") : null;

    // Two separate statements (NOT an IF/ELSE script), because BigQuery validates
    // the whole script before running — a MERGE referencing a not-yet-created table
    // would fail validation. Instead:
    //   1. CREATE TABLE IF NOT EXISTS ... AS SELECT ... WHERE FALSE  -> creates the
    //      Iceberg table with the correct schema on the first run; no-op afterwards.
    //   2. MERGE ... -> always runs; the table is guaranteed to exist. On the first
    //      run the table is empty, so every row goes through WHEN NOT MATCHED (insert).
    const createIfNotExists =
      `CREATE TABLE IF NOT EXISTS ${fqTable}
${connClause}
${optionsClause}
AS
SELECT * FROM (
${selectFull}
) WHERE FALSE`;

    const mergeSql =
      `MERGE ${fqTable} T
USING (
${selectDelta}
) S
ON ${onClause}
WHEN MATCHED THEN UPDATE SET
    ${updateSet}
WHEN NOT MATCHED THEN INSERT (${insertCols}) VALUES (${insertVals})`;

    return [createIfNotExists, mergeSql, exportSql];
  });
}

module.exports = { isIceberg, buildStorageUri, publishProduct };