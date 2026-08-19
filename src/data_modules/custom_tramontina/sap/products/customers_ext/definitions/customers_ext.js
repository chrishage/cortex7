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
  ["client_mandt", "customer_number_kunnr"]
);

iceberg_helper.publishProduct(
  tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT
  cust.* EXCEPT(source_last_updated_at, bq_loaded_at),
  kna1.regio AS region_matriz,
  GREATEST(
    IFNULL(cust.source_last_updated_at, TIMESTAMP('1900-01-01 00:00:00+00')),
    IFNULL(kna1.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00'))
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM \`${dataform.projectConfig.vars.dataProject || moduleConfig.targetProjectId}.data_products.customers\` AS cust
LEFT JOIN ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "kna1")} AS kna1
  ON  kna1.mandt = cust.client_mandt
  AND kna1.kunnr = cust.customer_number_kunnr
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["cust.source_last_updated_at"])
])}
  `
);
