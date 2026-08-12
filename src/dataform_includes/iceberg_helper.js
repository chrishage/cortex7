/**
 * Copyright 2026 Google LLC
 * Licensed under the Apache License, Version 2.0
 *
 * Iceberg helper for Cortex Framework.
 *
 * WHY THIS EXISTS:
 * The Dataform publish() API does NOT emit `WITH CONNECTION ... OPTIONS(table_format='ICEBERG')`
 * from a `bigquery.iceberg` config block — it silently creates a NATIVE BigQuery table.
 * To create a real BigLake Iceberg managed table we emit an explicit
 * CREATE OR REPLACE TABLE ... WITH CONNECTION ... OPTIONS(...) via a Dataform
 * `operations` action.
 *
 * The product SELECT queries call incremental.getFilter(ctx, ...) which internally
 * uses ctx.when(ctx.incremental(), ...) and ctx.self() — methods that exist in the
 * publish() context but NOT in the operations() context. Iceberg tables here use a
 * full-refresh (CREATE OR REPLACE), i.e. non-incremental, so we shim the ctx with:
 *   - incremental() => false      (so the incremental filter collapses to the empty branch)
 *   - when(cond, t, f) => cond ? t : f
 *   - self() => fully-qualified table (in case referenced)
 *   - ref/resolve => delegate to the real operations ctx
 *
 * USAGE (in a product .js, replacing publish(...).query(...)):
 *   const iceberg_helper = require("includes/iceberg_helper.js");
 *   iceberg_helper.publishProduct(actionName, publishConfig, tableConfig, (ctx) => `SELECT ...`);
 */

function isIceberg(tableConfig) {
  return !!(tableConfig && tableConfig.bigquery && tableConfig.bigquery.iceberg
            && tableConfig.bigquery.iceberg.bucketName);
}

function buildStorageUri(iceberg, tableName) {
  const bucket = iceberg.bucketName;
  const root = iceberg.tableFolderRoot ? iceberg.tableFolderRoot.replace(/\/+$/,"") + "/" : "";
  const sub  = iceberg.tableFolderSubpath ? iceberg.tableFolderSubpath.replace(/\/+$/,"") + "/" : "";
  return `gs://${bucket}/${root}${sub}${tableName}`;
}

/**
 * Wraps the operations ctx so that publish()-only methods used inside the product
 * query (incremental filters) behave correctly for a full-refresh Iceberg table.
 */
function shimContext(ctx, fqTable) {
  return {
    // delegate the real ones
    ref: (...args) => ctx.ref(...args),
    resolve: (...args) => ctx.resolve(...args),
    // full-refresh => not incremental
    incremental: () => false,
    when: (cond, trueBranch, falseBranch = "") => (cond ? trueBranch : falseBranch),
    self: () => fqTable,
    // pass through anything else Dataform exposes
    name: ctx.name ? (...a) => ctx.name(...a) : undefined,
    schema: ctx.schema ? (...a) => ctx.schema(...a) : undefined,
    database: ctx.database ? (...a) => ctx.database(...a) : undefined,
  };
}

function publishProduct(actionName, publishConfig, tableConfig, queryFn) {
  if (!isIceberg(tableConfig)) {
    publish(actionName, publishConfig).query(queryFn);
    return;
  }

  const iceberg    = tableConfig.bigquery.iceberg;
  const project    = publishConfig.database;
  const dataset    = publishConfig.schema;
  const tableName  = publishConfig.name;
  const fqTable    = `\`${project}.${dataset}.${tableName}\``;
  const connection = iceberg.connection || "DEFAULT";
  const connClause = connection === "DEFAULT"
    ? "WITH CONNECTION DEFAULT"
    : `WITH CONNECTION \`${connection}\``;
  const fileFormat = iceberg.fileFormat || "PARQUET";
  const storageUri = buildStorageUri(iceberg, tableName);

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
    const shimmed = shimContext(ctx, fqTable);
    const selectSql = queryFn(shimmed);
    const createSql = `
CREATE OR REPLACE TABLE ${fqTable}
${connClause}
OPTIONS(
  file_format = '${fileFormat}',
  table_format = 'ICEBERG',
  storage_uri = '${storageUri}'
)
AS
${selectSql}`;
    const exportSql = `EXPORT TABLE METADATA FROM ${fqTable}`;
    return [createSql, exportSql];
  });
}

module.exports = { isIceberg, buildStorageUri, publishProduct };
