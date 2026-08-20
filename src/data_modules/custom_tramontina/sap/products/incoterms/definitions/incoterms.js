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
  ['client_mandt', 'incoterms_classification_inco1', 'language_key_spras']
);

iceberg_helper.publishProduct(
  tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT
  TINCT.mandt AS client_mandt,
  TINCT.inco1 AS incoterms_classification_inco1,
  TINCT.spras AS language_key_spras,
  TINCT.bezei AS incoterms_classification_name_bezei,
  TINC.ortob AS incoterms_location_mandatory_ortob,
  GREATEST(
    IFNULL(TINCT.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')), IFNULL(TINC.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00'))
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "tinct")} AS TINCT
LEFT JOIN (
  SELECT * FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "tinc")}
  QUALIFY ROW_NUMBER() OVER (PARTITION BY mandt, inco1 ORDER BY IFNULL(recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) DESC) = 1
) AS TINC
  ON TINCT.mandt = TINC.mandt AND TINCT.inco1 = TINC.inco1
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["tinct", "tinc"])
])}
AND TINCT.mandt = '400'
  `
);
