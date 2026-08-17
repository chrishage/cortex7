/**
 * Copyright 2026 Tramontina S.A.
 * Data Product Extension: sales_document_items_ext
 * Ampliação do produto sap_sales_documents_sales_document_items com campos de VBKD (BZIRK, INCO1, ZTERM)
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
    "document_number_vbeln",
    "item_number_posnr"
  ]
);

iceberg_helper.publishProduct(
  moduleContext.moduleId + "_" + tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT
  sdi.* EXCEPT(source_last_updated_at, bq_loaded_at),
  COALESCE(vbkd_item.pltyp, vbkd_hdr.pltyp) AS price_list_type_pltyp,
  COALESCE(vbkd_item.bzirk, vbkd_hdr.bzirk) AS sales_district_bzirk,
  COALESCE(vbkd_item.inco1, vbkd_hdr.inco1) AS incoterms_classification_inco1,
  COALESCE(vbkd_item.zterm, vbkd_hdr.zterm) AS customer_payment_terms_zterm,
  GREATEST(
    IFNULL(sdi.source_last_updated_at, TIMESTAMP('1900-01-01 00:00:00+00')),
    IFNULL(vbkd_item.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')),
    IFNULL(vbkd_hdr.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00'))
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapSalesDocuments.datasetId, "sap_sales_documents_sales_document_items")} AS sdi
LEFT JOIN ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "vbkd")} AS vbkd_item
  ON  vbkd_item.mandt = sdi.client_mandt
  AND vbkd_item.vbeln = sdi.document_number_vbeln
  AND vbkd_item.posnr = sdi.item_number_posnr
LEFT JOIN ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "vbkd")} AS vbkd_hdr
  ON  vbkd_hdr.mandt = sdi.client_mandt
  AND vbkd_hdr.vbeln = sdi.document_number_vbeln
  AND vbkd_hdr.posnr = '000000'
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["sdi"])
])}
`,
);
