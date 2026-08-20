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
  ['client_mandt', 'nota_fiscal_document_docnum', 'nota_fiscal_item_itmnum']
);

iceberg_helper.publishProduct(
  tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT
  j_1bnflin.mandt AS client_mandt,
  j_1bnflin.docnum AS nota_fiscal_document_docnum,
  j_1bnflin.itmnum AS nota_fiscal_item_itmnum,
  j_1bnflin.matnr AS material_number_matnr,
  j_1bnflin.charg AS batch_charg,
  j_1bnflin.meins AS base_unit_meins,
  j_1bnflin.menge AS quantity_menge,
  j_1bnflin.netpr AS net_price_netpr,
  j_1bnflin.netwr AS net_value_netwr,
  j_1bnflin.nfnett AS nota_fiscal_total_amount_nfnett,
  j_1bnflin.netfre AS net_freight_netfre,
  j_1bnflin.netins AS insurance_netins,
  j_1bnflin.netoth AS other_expenses_netoth,
  j_1bnflin.refkey AS billing_document_refkey,
  IFNULL(
    j_1bnflin.recordstamp,
    TIMESTAMP('1900-01-01 00:00:00+00')
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "j_1bnflin")} AS j_1bnflin
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["j_1bnflin"])
])}

  `
);
