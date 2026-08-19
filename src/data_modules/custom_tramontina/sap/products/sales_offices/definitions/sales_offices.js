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
  ['client_mandt', 'sales_office_vkbur', 'language_key_spras']
);

iceberg_helper.publishProduct(
  tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT
  tvkbt.mandt AS client_mandt,
  tvkbt.vkbur AS sales_office_vkbur,
  tvkbt.spras AS language_key_spras,
  tvkbt.bezei AS sales_office_name_bezei,
  IFNULL(
    tvkbt.recordstamp,
    TIMESTAMP('1900-01-01 00:00:00+00')
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "tvkbt")} AS tvkbt
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["tvkbt"])
])}
  `
);
