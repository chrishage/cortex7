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
  knvv.mandt AS client_mandt,
  knvv.kunnr AS customer_number_kunnr,
  knvv.vkorg AS sales_organization_vkorg,
  knvv.vtweg AS distribution_channel_vtweg,
  knvv.spart AS division_spart,
  knvv.bzirk AS sales_district_bzirk,
  knvv.vkgrp AS sales_group_vkgrp,
  knvv.vkbur AS sales_office_vkbur,
  knvv.kdgrp AS customer_group_kdgrp,
  knvv.kvgr1 AS customer_group_1_kvgr1,
  knvv.kvgr2 AS customer_group_2_kvgr2,
  knvv.kvgr3 AS customer_group_3_kvgr3,
  knvv.kvgr4 AS customer_group_4_kvgr4,
  knvv.kvgr5 AS customer_group_5_kvgr5,
  knvv.konda AS price_group_konda,
  knvv.pltyp AS price_list_type_pltyp,
  knvv.versg AS customer_statistics_group_versg,
  knvv.inco1 AS incoterms_classification_inco1,
  knvv.zterm AS terms_of_payment_zterm,
  knvv.waers AS currency_waers,
  knvv.lprio AS delivery_priority_lprio,
  knvv.kalks AS customer_pricing_procedure_kalks,
  knvv.loevm AS deletion_flag_loevm,
  IFNULL(
    knvv.recordstamp,
    TIMESTAMP('1900-01-01 00:00:00+00')
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "knvv")} AS knvv
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["knvv"])
])}

  `
);
