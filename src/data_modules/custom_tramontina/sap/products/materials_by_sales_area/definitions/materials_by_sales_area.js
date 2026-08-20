const custom_tramontina = require("../../../../../custom_tramontina");

custom_tramontina.publishProduct({
  name: "materials_by_sales_area",
  type: "incremental",
  schema: "data_products",
  dependencies: ["sapRaw"],
  query: (
    ctx
  ) => `
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
  CURRENT_TIMESTAMP() AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM
  ${ctx.ref("sapRaw", "MVKE")}
QUALIFY ROW_NUMBER() OVER (PARTITION BY mandt, matnr, vkorg, vtweg ORDER BY IFNULL(recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) DESC) = 1
  `
});
