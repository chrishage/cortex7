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
  ['client_mandt', 'nota_fiscal_document_docnum']
);

iceberg_helper.publishProduct(
  tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT
  j_1bnfdoc.mandt AS client_mandt,
  j_1bnfdoc.docnum AS nota_fiscal_document_docnum,
  j_1bnfdoc.bukrs AS company_code_bukrs,
  j_1bnfdoc.belnr AS billing_document_belnr,
  j_1bnfdoc.nfnum AS nota_fiscal_number_nfnum,
  j_1bnfdoc.nftype AS nota_fiscal_type_nftype,
  j_1bnfdoc.docdat AS document_date_docdat,
  j_1bnfdoc.nfenum AS nfe_number_nfenum,
  j_1bnfdoc.cancel AS cancel_flag_cancel,
  j_1bnfe_active.model AS nfe_model_model,
  j_1bnfe_active.serie AS nfe_series_serie,
  j_1bnfe_active.docsta AS nfe_document_status_docsta,
  j_1bnfe_active.authcod AS nfe_authorization_protocol_authcod,
  j_1bnfe_active.authdate AS nfe_authorization_date_authdate,
  j_1bnfe_active.tpamb AS nfe_environment_type_tpamb,
  j_1bnfe_active.tpemis AS nfe_emission_type_tpemis,
  j_1bnfe_active.regio || j_1bnfe_active.nfyear || j_1bnfe_active.nfmonth || j_1bnfe_active.stcd1 || j_1bnfe_active.model || j_1bnfe_active.serie || j_1bnfe_active.nfnum9 || j_1bnfe_active.docnum9 || j_1bnfe_active.cdv AS nfe_access_key,
  j_1bnfe_active.waerk AS currency_waerk,
  j_1bnfe_active.regio AS region_regio,
  GREATEST(
    IFNULL(j_1bnfdoc.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')), IFNULL(j_1bnfe_active.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00'))
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "j_1bnfdoc")} AS j_1bnfdoc
LEFT JOIN (
  SELECT * FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "j_1bnfe_active")}
  QUALIFY ROW_NUMBER() OVER (PARTITION BY mandt, docnum ORDER BY IFNULL(recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) DESC) = 1
) AS j_1bnfe_active
  ON j_1bnfdoc.mandt = j_1bnfe_active.mandt AND j_1bnfdoc.docnum = j_1bnfe_active.docnum
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["j_1bnfdoc", "j_1bnfe_active"])
])}
AND j_1bnfdoc.mandt = '400'
  `
);
