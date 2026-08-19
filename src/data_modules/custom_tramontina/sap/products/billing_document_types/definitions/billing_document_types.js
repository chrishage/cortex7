// ___MODULE_CONTEXT___
// ___TABLE_CONFIG___

const moduleConfig = config.product[moduleContext.moduleId];
const materializationType = tableConfig.materializationType || "incremental";
const incremental = require("includes/incremental.js");
const publish_config = require("includes/publish_config.js");
const sql_helper = require("includes/sql_helper.js");
const iceberg_helper = require("includes/iceberg_helper.js");

const publishConfig = publish_config.getPublishConfig(
  materializationType,
  tableConfig,
  moduleConfig,
  ['client_mandt', 'billing_type_fkart', 'language_key_spras']
);

iceberg_helper.publishProduct(
  tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT
  tvfkt.mandt AS client_mandt,
  tvfkt.fkart AS billing_type_fkart,
  tvfkt.spras AS language_key_spras,
  tvfkt.vtext AS billing_type_name_vtext,
  IFNULL(
    tvfkt.recordstamp,
    TIMESTAMP('1900-01-01 00:00:00+00')
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "tvfkt")} AS tvfkt
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["tvfkt"])
])}
  `
);
