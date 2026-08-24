/**
 * Copyright 2026 Google LLC
 * Licensed under the Apache License, Version 2.0
 *
 * Iceberg helper for Cortex Framework â€” supports FULL REFRESH and INCREMENTAL.
 *
 * WHY THIS EXISTS:
 * The Dataform publish() API does NOT emit `WITH CONNECTION ... OPTIONS(table_format='ICEBERG')`
 * from a `bigquery.iceberg` config block â€” it silently creates a NATIVE BigQuery table.
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

function buildStorageUri(iceberg, tableName, productFolder) {
  const bucket = iceberg.bucketName;
  // Override manual via table_settings tem prioridade
  if (iceberg.tableFolderRoot || iceberg.tableFolderSubpath) {
    const root = iceberg.tableFolderRoot ? iceberg.tableFolderRoot.replace(/\/+$/, "") + "/" : "";
    const sub = iceberg.tableFolderSubpath ? iceberg.tableFolderSubpath.replace(/\/+$/, "") + "/" : "";
    return `gs://${bucket}/${root}${sub}${tableName}`;
  }
  // PadrÃ£o novo: cortex_data_products/<produto>/<definition>
  return `gs://${bucket}/cortex_data_products/${productFolder}/${tableName}`;
}

/**
 * Monta a clausula PARTITION BY a partir de partitionDetails do table_settings.
 *
 *   partitionDetails:
 *     column: <nome_da_coluna>
 *     partitionType: DATE | TIMESTAMP
 *     timeGrain: DAY | MONTH | YEAR   (HOUR tambem para TIMESTAMP)
 *
 * Retorna "" quando ausente ou invalido -> fallback seguro: tabela sem particao,
 * comportamento identico ao anterior. Produto sem partitionDetails nao muda.
 *
 * IMPORTANTE: Iceberg gerenciado PERSISTE a particao. Para conferir, usar a UI do
 * BigQuery ou INFORMATION_SCHEMA.PARTITIONS â€” o campo .ddl de INFORMATION_SCHEMA.TABLES
 * NAO renderiza a particao de tabelas Iceberg (so mostra CLUSTER BY).
 *
 * VALIDADO EM PROD: apenas DATE + DAY. As demais combinacoes seguem a sintaxe do
 * BigQuery mas ainda nao foram testadas em Iceberg gerenciado â€” testar isolado antes.
 */
function buildPartitionClause(details) {
  if (!details || !details.column) return "";
  const col = `\`${details.column}\``;
  const type = (details.partitionType || "DATE").toUpperCase();
  const grain = (details.timeGrain || "DAY").toUpperCase();

  if (type === "DATE") {
    if (grain === "DAY") return `PARTITION BY ${col}`;
    if (grain === "MONTH" || grain === "YEAR") return `PARTITION BY DATE_TRUNC(${col}, ${grain})`;
    return "";
  }
  if (type === "TIMESTAMP") {
    if (["HOUR", "DAY", "MONTH", "YEAR"].indexOf(grain) === -1) return "";
    return `PARTITION BY TIMESTAMP_TRUNC(${col}, ${grain})`;
  }
  return "";
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
  // DEBUG TEMPORARIO
  console.log("[DBG] " + actionName + " pubKeys: " + JSON.stringify(Object.keys(publishConfig || {})));
  console.log("[DBG] " + actionName + " pubBq: " + JSON.stringify(publishConfig && publishConfig.bigquery));
  console.log("[DBG] " + actionName + " uKey: " + JSON.stringify(publishConfig && publishConfig.uniqueKey));
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
  const productId = actionName.slice(0, actionName.length - (tableName.length + 1));
  const productFolder = productId.replace(/^sap_/, "");
  const storageUri = buildStorageUri(effectiveIceberg, tableName, productFolder);
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

    // CLUSTER BY: honra clusterDetails.columns do table_settings quando presente;
    // caso contrario deriva das colunas-chave (uniqueKey), comportamento anterior.
    // BigQuery permite no maximo 4 colunas de clustering; pega as primeiras 4.
    // Preferir o yaml evita gastar slot com coluna constante (ex.: client_mandt='400').
    const clusterDetails = tableConfig.clusterDetails || {};
    const clusterSource = (clusterDetails.columns && clusterDetails.columns.length > 0)
      ? clusterDetails.columns
      : (publishConfig.uniqueKey || []);
    const clusterKeys = clusterSource.slice(0, 4);
    const clusterClause = clusterKeys.length > 0
      ? `CLUSTER BY ${clusterKeys.map(k => `\`${k}\``).join(", ")}`
      : "";

    // PARTITION BY: honra partitionDetails do table_settings (ver buildPartitionClause).
    // Ganho no CONSUMO (SELECT com filtro de data: 2,75 GB -> 20 MB medido em prod).
    // NAO reduz o MERGE quando o gargalo e a leitura da tabela FONTE, porque o ON do
    // MERGE e por chave e nao aciona a particao do target.
    // Mudanca CREATE-time: tabela ja existente exige DROP + rerun para adotar.
    const partitionClause = buildPartitionClause(tableConfig.partitionDetails);

    // Ordem obrigatoria no DDL: PARTITION BY -> CLUSTER BY -> WITH CONNECTION -> OPTIONS.
    const layoutClause =
      `${partitionClause ? "\n" + partitionClause : ""}${clusterClause ? "\n" + clusterClause : ""}`;

    // ---------- FULL REFRESH ----------
    if (matType === "table") {
      const selectSql = queryFn(shimContext(ctx, fqTable, /*incremental=*/false));
      const createSql =
        `CREATE OR REPLACE TABLE ${fqTable}${layoutClause}
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

    // OTIMIZAÃ‡ÃƒO DE CUSTO: a subquery correlacionada no filtro incremental
    // (recordstamp >= (SELECT MAX... FROM target)) impede o partition pruning do
    // BigQuery â€” o MERGE lÃª a fonte quase inteira todo run. Materializar o watermark
    // numa variÃ¡vel de script (DECLARE) antes do MERGE permite o pruning.
    // Ganho medido: 5,5 GB -> 18,6 MB. Sem mudanÃ§a de corretude (mesmo valor).
    // A subquery tem formato fixo gerado por incremental.getFilter (usando ctx.self()=fqTable).
    const watermarkSubquery = `(
      SELECT TIMESTAMP_SUB(
        IFNULL(MAX(source_last_updated_at), TIMESTAMP("1900-12-25 05:30:00+00")),
        INTERVAL 30 MINUTE
      )
      FROM ${fqTable}
    )`;
    const usesWatermark = selectDelta.includes(watermarkSubquery);
    const selectDeltaVar = usesWatermark
      ? selectDelta.split(watermarkSubquery).join("_watermark")
      : selectDelta;

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
    // the whole script before running â€” a MERGE referencing a not-yet-created table
    // would fail validation. Instead:
    //   1. CREATE TABLE IF NOT EXISTS ... AS SELECT ... WHERE FALSE  -> creates the
    //      Iceberg table with the correct schema on the first run; no-op afterwards.
    //   2. MERGE ... -> always runs; the table is guaranteed to exist. On the first
    //      run the table is empty, so every row goes through WHEN NOT MATCHED (insert).
    const createIfNotExists =
      `CREATE TABLE IF NOT EXISTS ${fqTable}${layoutClause}
${connClause}
${optionsClause}
AS
SELECT * FROM (
${selectFull}
) WHERE FALSE`;

    const mergeSql = usesWatermark
      ? `BEGIN
  DECLARE _watermark TIMESTAMP DEFAULT ${watermarkSubquery};
  MERGE ${fqTable} T
USING (
${selectDeltaVar}
) S
ON ${onClause}
WHEN MATCHED THEN UPDATE SET
    ${updateSet}
WHEN NOT MATCHED THEN INSERT (${insertCols}) VALUES (${insertVals});
END;`
      : `MERGE ${fqTable} T
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

module.exports = { isIceberg, buildStorageUri, buildPartitionClause, publishProduct };

// DEBUG TEMPORARIO - remover antes do merge final
