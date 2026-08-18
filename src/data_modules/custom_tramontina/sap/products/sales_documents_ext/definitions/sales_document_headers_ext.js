/**
 * Copyright 2026 Tramontina S.A.
 * Data Product Extension: sales_document_headers_ext
 * Ampliação do produto sap_sales_documents_sales_document_headers com campos de VBKD (PLTYP, BZIRK, INCO1, ZTERM)
 */

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
  [
    "client_mandt",
    "document_number_vbeln"
  ]
);

iceberg_helper.publishProduct(
  moduleContext.moduleId + "_" + tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT
  sdh.* EXCEPT(source_last_updated_at, bq_loaded_at),
  vbkd_hdr.pltyp AS price_list_type_pltyp,
  vbkd_hdr.bzirk AS sales_district_bzirk,
  vbkd_hdr.inco1 AS incoterms_classification_inco1,
  vbkd_hdr.zterm AS customer_payment_terms_zterm,
  GREATEST(
    IFNULL(sdh.source_last_updated_at, TIMESTAMP('1900-01-01 00:00:00+00')),
    IFNULL(vbkd_hdr.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00'))
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM \`${dataform.projectConfig.vars.dataProject || moduleConfig.targetProjectId}.data_products.sales_document_headers\` AS sdh
LEFT JOIN ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "vbkd")} AS vbkd_hdr
  ON  vbkd_hdr.mandt = sdh.client_mandt
  AND vbkd_hdr.vbeln = sdh.document_number_vbeln
  AND vbkd_hdr.posnr = '000000'
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["sdh"])
])}
`,
);
