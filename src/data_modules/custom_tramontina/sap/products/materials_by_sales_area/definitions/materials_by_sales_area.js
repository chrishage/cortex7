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
  ['client_mandt', 'material_number_matnr', 'sales_organization_vkorg', 'distribution_channel_vtweg']
);

iceberg_helper.publishProduct(
  tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT

  mandt AS client_mandt,
  matnr AS material_number_matnr,
  vkorg AS sales_organization_vkorg,
  vtweg AS distribution_channel_vtweg,
  vmsta AS distr_chain_material_status_vmsta,
  vmstd AS distr_chain_material_status_valid_from_vmstd,
  dwerk AS delivering_plant_dwerk,
  kondm AS material_pricing_group_kondm,
  versg AS material_statistics_group_versg,
  prodh AS product_hierarchy_prodh,
  mvgr1 AS material_group_1_mvgr1,
  mvgr2 AS material_group_2_mvgr2,
  mvgr3 AS material_group_3_mvgr3,
  mvgr4 AS material_group_4_mvgr4,
  mvgr5 AS material_group_5_mvgr5,
  vrkme AS sales_unit_vrkme,
  mtpos AS item_category_group_mtpos,
  ktgrm AS account_assignment_group_ktgrm,
  lvorm AS deletion_flag_lvorm,
  IFNULL(recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "mvke")}
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["mvke"])
, "mandt = '400'"
])}
  `
);
