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
  mvke.mandt AS client_mandt,
  mvke.matnr AS material_number_matnr,
  mvke.vkorg AS sales_organization_vkorg,
  mvke.vtweg AS distribution_channel_vtweg,
  mvke.vmsta AS distr_chain_material_status_vmsta,
  mvke.vmstd AS distr_chain_material_status_valid_from_vmstd,
  mvke.dwerk AS delivering_plant_dwerk,
  mvke.kondm AS material_pricing_group_kondm,
  mvke.versg AS material_statistics_group_versg,
  mvke.prodh AS product_hierarchy_prodh,
  mvke.mvgr1 AS material_group_1_mvgr1,
  mvke.mvgr2 AS material_group_2_mvgr2,
  mvke.mvgr3 AS material_group_3_mvgr3,
  mvke.mvgr4 AS material_group_4_mvgr4,
  mvke.mvgr5 AS material_group_5_mvgr5,
  mvke.vrkme AS sales_unit_vrkme,
  mvke.mtpos AS item_category_group_mtpos,
  mvke.ktgrm AS account_assignment_group_ktgrm,
  mvke.lvorm AS deletion_flag_lvorm,
  IFNULL(
    mvke.recordstamp,
    TIMESTAMP('1900-01-01 00:00:00+00')
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "mvke")} AS mvke
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["mvke"])
])}

  `
);
