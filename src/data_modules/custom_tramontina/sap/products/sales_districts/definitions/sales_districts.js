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
  ['client_mandt', 'sales_district_bzirk', 'language_key_spras']
);

iceberg_helper.publishProduct(
  tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT
  t171t.mandt AS client_mandt,
  t171t.bzirk AS sales_district_bzirk,
  t171t.spras AS language_key_spras,
  t171t.bztxt AS sales_district_name_bztxt,
  IFNULL(
    t171t.recordstamp,
    TIMESTAMP('1900-01-01 00:00:00+00')
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "t171t")} AS t171t
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["t171t"])
])}
  `
);
