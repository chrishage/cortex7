/**
 * Copyright 2026 Google LLC
 * Licensed under the Apache License, Version 2.0
 *
 * Iceberg helper for Cortex Framework - supports FULL REFRESH and INCREMENTAL.
 *
 * WHY THIS EXISTS:
 * The Dataform publish() API does NOT emit `WITH CONNECTION ... OPTIONS(table_format='ICEBERG')`
 * from a `bigquery.iceberg` config block - it silently creates a NATIVE BigQuery table.
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
  // Padrao novo: cortex_data_products/<produto>/<definition>
  return `gs://${bucket}/cortex_data_products/${productFolder}/${tableName}`;
}

/**
 * Escapa uma string para interpolacao segura em literal SQL entre aspas simples.
 * As descricoes vem das annotations e contem apostrofos, acentos e parenteses;
 * um apostrofo nao escapado quebra o DDL inteiro do produto.
 */
function sqlStr(s) {
  return String(s)
    .replace(/\\/g, "\\\\")
    .replace(/'/g, "\\'")
    .replace(/\r?\n/g, " ");
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

/**
 * Monta um unico ALTER TABLE aplicando as descricoes de coluna vindas das
 * annotations (publishConfig.columns = {coluna: descricao}).
 *
 * POR QUE ISTO EXISTE: no caminho nativo o Dataform aplica as descricoes via API
 * (tables.patch) a partir do publishConfig.columns. O helper usa operate() em vez
 * de publish(), entao esse mecanismo nao roda e os produtos Iceberg ficam SEM
 * descricao nenhuma. O CREATE ... AS SELECT nao permite anotar colunas, logo a
 * unica via e um ALTER apos a criacao.
 *
 * Nao e CREATE-time: funciona em tabela existente (validado em Iceberg gerenciada),
 * portanto NAO exige DROP+rerun.
 *
 * Protegido por EXCEPTION: descricao e metadado e nunca deve derrubar uma carga.
 * Se uma coluna do publishConfig nao existir na tabela, o ALTER inteiro falharia e
 * mataria o produto - com o handler, vira no-op silencioso.
 *
 * Retorna null quando nao ha descricoes (columns ausente ou array de nomes).
 */
function buildDescriptionsSql(fqTable, publishConfig) {
  const cols = publishConfig.columns;
  if (!cols || Array.isArray(cols)) return null;
  const named = Object.keys(cols).filter(k => cols[k]);
  if (named.length === 0) return null;

  const setters = named
    .map(k => `  ALTER COLUMN \`${k}\` SET OPTIONS(description='${sqlStr(cols[k])}')`)
    .join(",\n");

  return `BEGIN
ALTER TABLE ${fqTable}
${setters};
EXCEPTION WHEN ERROR THEN
  SELECT CONCAT('[iceberg_helper] column descriptions skipped: ', @@error.message);
END;`;
}

/**
 * Extrai o nome NU da coluna de particao a partir do partitionBy do publishConfig.
 *
 * O cortex-build entrega expressoes: "DATE(col)", "DATE_TRUNC(col, MONTH)", "col".
 * O pruning do MERGE precisa do NOME da coluna para montar o predicado BETWEEN
 * sobre o target. So se aplica quando a expressao referencia uma unica coluna
 * simples; para qualquer forma nao reconhecida retorna null e o pruning e
 * desligado (fallback seguro).
 */
function partitionColumnName(partitionBy) {
  if (!partitionBy) return null;
  const expr = String(partitionBy).trim();
  let m = expr.match(/^DATE\(\s*([A-Za-z0-9_]+)\s*\)$/);
  if (m) return m[1];
  m = expr.match(/^(?:DATE_TRUNC|TIMESTAMP_TRUNC|DATETIME_TRUNC)\(\s*([A-Za-z0-9_]+)\s*,/);
  if (m) return m[1];
  m = expr.match(/^([A-Za-z0-9_]+)$/);
  if (m) return m[1];
  return null;
}

function publishProduct(actionName, publishConfig, tableConfig, queryFn) {
  // NOTA: as configuracoes de layout NAO vem no tableConfig.
  // publishConfig.bigquery traz partitionBy/clusterBy ja traduzidos pelo cortex-build
  // a partir de partitionDetails/clusterDetails do table_settings.
  // O tableConfig NAO carrega essas chaves - nao tentar ler de la.
  // Chaves nao reconhecidas pelo cortex-build (ex.: partitionDetails.sources) passam
  // na validacao do yaml mas sao DESCARTADAS: nao chegam ao publishConfig.
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

  // Descricao da TABELA: cabe direto no OPTIONS() do CREATE (diferente das colunas,
  // que exigem ALTER - ver buildDescriptionsSql).
  const tableDesc = publishConfig.description
    ? `, description='${sqlStr(publishConfig.description)}'`
    : "";
  const optionsClause =
    `OPTIONS(file_format='${fileFormat}', table_format='ICEBERG', storage_uri='${storageUri}'${tableDesc})`;

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
    const descriptionsSql = buildDescriptionsSql(fqTable, publishConfig);

    // CLUSTER BY: honra publishConfig.bigquery.clusterBy (traduzido pelo
    // cortex-build a partir de clusterDetails do table_settings); caso ausente,
    // deriva da uniqueKey. BigQuery permite no maximo 4 colunas de clustering.
    // Preferir o clusterBy evita gastar slots com colunas constantes da uniqueKey
    // (ex.: client_rclnt='400', ledger_in_general_ledger_accounting_rldnr).
    const pubBq = publishConfig.bigquery || {};
    const clusterSource = (pubBq.clusterBy && pubBq.clusterBy.length > 0)
      ? pubBq.clusterBy
      : (publishConfig.uniqueKey || []);
    const clusterKeys = clusterSource.slice(0, 4);
    const clusterClause = clusterKeys.length > 0
      ? `CLUSTER BY ${clusterKeys.map(k => `\`${k}\``).join(", ")}`
      : "";

    // PARTITION BY: honra publishConfig.bigquery.partitionBy, que ja vem como
    // expressao SQL pronta - interpolar direto.
    // Ganho no CONSUMO (SELECT com filtro de data: 34,79 GB -> 72 MB medido em dev)
    // E TAMBEM no MERGE, desde que o ON receba um predicado de data (ver adiante).
    // Mudanca CREATE-time: tabela ja existente exige DROP + rerun para adotar
    // (e limpar o prefixo no GCS, que o DROP nao remove).
    //
    // O cortex-build gera "DATE(coluna)" sem checar o tipo. Em coluna ja DATE isso
    // e invalido no BigQuery (DATE() so aceita TIMESTAMP/DATETIME). Como as colunas
    // de particao dos produtos SAP sao DATE, desembrulha para a coluna nua.
    // O regex preserva DATE_TRUNC(...)/TIMESTAMP_TRUNC(...) intactos.
    const rawPartition = pubBq.partitionBy || "";
    const unwrapped = rawPartition.replace(/^DATE\(\s*([A-Za-z0-9_]+)\s*\)$/, "$1");
    const partitionClause = unwrapped ? `PARTITION BY ${unwrapped}` : "";

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
      return descriptionsSql
        ? [createSql, descriptionsSql, exportSql]
        : [createSql, exportSql];
    }

    // ---------- INCREMENTAL ----------
    // TWO versions of the SELECT are needed:
    //  - selectFull  (incremental=false): NO self-referencing filter. Used by the
    //    CREATE ... WHERE FALSE so it does not read the not-yet-created table.
    //  - selectDelta (incremental=true): with the incremental filter (reads MAX from
    //    the table). Used by the MERGE, where the table is guaranteed to exist.
    const selectFull = queryFn(shimContext(ctx, fqTable, /*incremental=*/false));
    const selectDelta = queryFn(shimContext(ctx, fqTable, /*incremental=*/true));

    // OTIMIZACAO DE CUSTO: a subquery correlacionada no filtro incremental
    // (recordstamp >= (SELECT MAX... FROM target)) impede o partition pruning do
    // BigQuery - o MERGE le a fonte quase inteira todo run. Materializar o watermark
    // numa variavel de script (DECLARE) antes do MERGE permite o pruning.
    // Ganho medido: 5,5 GB -> 18,6 MB. Sem mudanca de corretude (mesmo valor).
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

    const keyOnClause = uniqueKeys.map(k => `T.\`${k}\` = S.\`${k}\``).join(" AND ");
    const updateSet = cols.length > 0
      ? cols.map(c => `T.\`${c}\` = S.\`${c}\``).join(",\n    ")
      : null;
    const insertCols = cols.length > 0 ? cols.map(c => `\`${c}\``).join(", ") : null;
    const insertVals = cols.length > 0 ? cols.map(c => `S.\`${c}\``).join(", ") : null;

    // ---------- PARTITION PRUNING DO MERGE ----------
    // O `ON` de um MERGE por chave NAO aciona a particao do target: o BigQuery varre
    // a tabela inteira para casar as chaves. Numa tabela de 370M linhas isso domina o
    // custo (medido em prod: 612 GB por run do universal_journal).
    //
    // A correcao e dar ao planner um predicado sobre a COLUNA DE PARTICAO do target.
    // Calculamos os limites de data do proprio delta em variaveis de script (constantes
    // no plano, como o watermark) e adicionamos um BETWEEN como PRIMEIRA condicao do ON.
    // Medido em prod numa query equivalente: 612 GB -> ~25 GB (~25x).
    //
    // PREMISSA DE CORRETUDE - LEIA ANTES DE MEXER:
    // O BETWEEN faz o MERGE casar SOMENTE linhas cuja coluna de particao esteja no
    // intervalo do lote. Isso e seguro apenas se a coluna for IMUTAVEL por chave: se o
    // valor mudar entre cargas, a linha existente fica fora do intervalo, o MERGE nao a
    // encontra e faz INSERT -> DUPLICATA SILENCIOSA.
    // Verificado em prod para budat (data de lancamento contabil, imutavel apos o
    // posting): zero chaves com budat divergente nos ultimos 30 dias de CDC e no
    // exercicio 2026 inteiro. Monitorar com a checagem n == n_keys da Phase 6.
    //
    // CUSTO: o SET faz uma passada extra sobre o delta lendo UMA coluna. Os limites
    // sao calculados sobre o selectDelta (o SELECT do produto) porque o helper NAO
    // conhece a tabela fonte nem o nome da coluna nela - e a chave que declararia isso
    // no yaml (partitionDetails.sources) e descartada pelo cortex-build.
    //
    // Condicoes para ativar (todas obrigatorias; qualquer uma falsa -> MERGE inalterado):
    //   1. o target e particionado (partitionClause presente);
    //   2. a expressao de particao referencia uma unica coluna simples;
    //   3. o filtro incremental usa watermark (senao o "delta" e a tabela toda e os
    //      limites cobririam todo o historico, tornando o BETWEEN inutil).
    const partitionCol = partitionClause ? partitionColumnName(unwrapped) : null;
    const usesPruning = !!(partitionCol && usesWatermark);

    const boundsDeclare = usesPruning
      ? `
  DECLARE _part_min DATE;
  DECLARE _part_max DATE;
  SET (_part_min, _part_max) = (
    SELECT AS STRUCT
      MIN(\`${partitionCol}\`),
      MAX(\`${partitionCol}\`)
    FROM (
${selectDeltaVar}
    )
  );`
      : "";

    // COALESCE nos limites: se o delta vier VAZIO, MIN/MAX retornam NULL e o BETWEEN
    // nunca casaria - o MERGE faria INSERT de tudo. Com o fallback aberto o predicado
    // fica sempre verdadeiro e o comportamento volta a ser o de sempre (sem pruning,
    // mas correto). Delta vazio significa nenhuma linha a inserir de qualquer forma.
    const pruningPredicate = usesPruning
      ? `T.\`${partitionCol}\` BETWEEN COALESCE(_part_min, DATE '0001-01-01') AND COALESCE(_part_max, DATE '9999-12-31')
   AND `
      : "";

    const onClause = `${pruningPredicate}${keyOnClause}`;

    // Two separate statements (NOT an IF/ELSE script), because BigQuery validates
    // the whole script before running - a MERGE referencing a not-yet-created table
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
  DECLARE _watermark TIMESTAMP DEFAULT ${watermarkSubquery};${boundsDeclare}
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

    // ALTER das descricoes vai APOS o CREATE (a tabela precisa existir) e ANTES do
    // MERGE, para que uma falha de metadado nao ocorra depois da carga.
    return descriptionsSql
      ? [createIfNotExists, descriptionsSql, mergeSql, exportSql]
      : [createIfNotExists, mergeSql, exportSql];
  });
}

module.exports = {
  isIceberg,
  buildStorageUri,
  buildDescriptionsSql,
  partitionColumnName,
  publishProduct
};