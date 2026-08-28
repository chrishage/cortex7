/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
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
    "sales_order_vbelv",
    "sales_order_item_posnv",
    "delivery_vbeln",
    "delivery_item_posnn",
    "billing_vbeln",
    "billing_item_posnn"
  ]
);

const filters = tableConfig.filters || {};
const precedingCats = filters.preceding_document_categories || ['C'];
const deliveryCats = filters.delivery_document_categories || ['J'];
const billingCats = filters.billing_document_categories || ['M'];

iceberg_helper.publishProduct(
  moduleContext.moduleId + "_" + tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT
  SO.mandt AS client_mandt,
  SO.vbelv AS sales_order_vbelv,
  SO.posnv AS sales_order_item_posnv,
  SO.vbeln AS delivery_vbeln,
  SO.posnn AS delivery_item_posnn,
  Billing.vbeln AS billing_vbeln,
  Billing.posnn AS billing_item_posnn,
  SO.erdat AS creation_date_erdat,
  SO.rfmng AS delivered_qty_rfmng,
  SO.meins AS delivered_uom_meins,
  Billing.rfmng AS billed_qty_rfmng,
  Billing.meins AS billed_uom_meins,
  Billing.rfwrt AS billed_value_rfwrt,
  Billing.waers AS billing_currency_waers,
  GREATEST(
    IFNULL(SO.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')),
    IFNULL(Billing.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00'))
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM
  ${ctx.ref(moduleConfig.sources.sapModule.datasetId, "vbfa")} AS SO
LEFT OUTER JOIN
  ${ctx.ref(moduleConfig.sources.sapModule.datasetId, "vbfa")} AS Billing
  ON
    SO.mandt = Billing.mandt
    AND SO.vbeln = Billing.vbelv
    AND SO.posnn = Billing.posnv
    AND Billing.vbtyp_n IN (${sql_helper.formatFilterArray(billingCats)})
${sql_helper.buildDynamicWhere([
    `SO.vbtyp_v IN (${sql_helper.formatFilterArray(precedingCats)})`,
    `SO.vbtyp_n IN (${sql_helper.formatFilterArray(deliveryCats)})`,
    incremental.getFilter(ctx, ["SO", "Billing"])
  ])}

UNION ALL

SELECT
  SO.mandt AS client_mandt,
  SO.vbelv AS sales_order_vbelv,
  SO.posnv AS sales_order_item_posnv,
  '' AS delivery_vbeln,
  '' AS delivery_item_posnn,
  SO.vbeln AS billing_vbeln,
  SO.posnn AS billing_item_posnn,
  SO.erdat AS creation_date_erdat,
  CAST(NULL AS NUMERIC) AS delivered_qty_rfmng,
  CAST(NULL AS STRING) AS delivered_uom_meins,
  SO.rfmng AS billed_qty_rfmng,
  SO.meins AS billed_uom_meins,
  SO.rfwrt AS billed_value_rfwrt,
  SO.waers AS billing_currency_waers,
  IFNULL(SO.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM
  ${ctx.ref(moduleConfig.sources.sapModule.datasetId, "vbfa")} AS SO
${sql_helper.buildDynamicWhere([
    `SO.vbtyp_v IN (${sql_helper.formatFilterArray(precedingCats)})`,
    `SO.vbtyp_n IN (${sql_helper.formatFilterArray(billingCats)})`,
    `NOT EXISTS (
      SELECT 1 FROM ${ctx.ref(moduleConfig.sources.sapModule.datasetId, "vbfa")} X
      WHERE X.mandt = SO.mandt
        AND X.vbeln = SO.vbeln
        AND X.posnn = SO.posnn
        AND X.vbtyp_v IN (${sql_helper.formatFilterArray(deliveryCats)})
    )`,
    incremental.getFilter(ctx, ["SO"])
  ])}
`,
);
