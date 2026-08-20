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
  ['client_mandt', 'customer_number_kunnr', 'sales_organization_vkorg', 'distribution_channel_vtweg', 'division_spart']
);

iceberg_helper.publishProduct(
  tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT

  mandt AS client_mandt,
  kunnr AS customer_number_kunnr,
  vkorg AS sales_organization_vkorg,
  vtweg AS distribution_channel_vtweg,
  spart AS division_spart,
  bzirk AS sales_district_bzirk,
  vkgrp AS sales_group_vkgrp,
  vkbur AS sales_office_vkbur,
  kdgrp AS customer_group_kdgrp,
  kvgr1 AS customer_group_1_kvgr1,
  kvgr2 AS customer_group_2_kvgr2,
  kvgr3 AS customer_group_3_kvgr3,
  kvgr4 AS customer_group_4_kvgr4,
  kvgr5 AS customer_group_5_kvgr5,
  konda AS price_group_konda,
  pltyp AS price_list_type_pltyp,
  versg AS customer_statistics_group_versg,
  inco1 AS incoterms_classification_inco1,
  zterm AS terms_of_payment_zterm,
  waers AS currency_waers,
  lprio AS delivery_priority_lprio,
  kalks AS customer_pricing_procedure_kalks,
  loevm AS deletion_flag_loevm,
  IFNULL(recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "knvv")}
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["knvv"])
])}
AND mandt = '400'
  `
);
