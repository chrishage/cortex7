import os, re

template_single = """// ___MODULE_CONTEXT___
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
  {keys}
);

iceberg_helper.publishProduct(
  tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT
{columns}
  IFNULL(recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "{table}")}
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["{table}"])
])}
AND mandt = '400'
  `
);
"""

template_incoterms = """// ___MODULE_CONTEXT___
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
  ['client_mandt', 'incoterms_classification_inco1', 'language_key_spras']
);

iceberg_helper.publishProduct(
  tableConfig.tableName,
  publishConfig,
  tableConfig,
  (ctx) => `
SELECT
  TINCT.mandt AS client_mandt,
  TINCT.inco1 AS incoterms_classification_inco1,
  TINCT.spras AS language_key_spras,
  TINCT.bezei AS incoterms_classification_name_bezei,
  TINC.ortob AS incoterms_location_mandatory_ortob,
  GREATEST(
    IFNULL(TINCT.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')), IFNULL(TINC.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00'))
  ) AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "TINCT")} AS TINCT
LEFT JOIN (
  SELECT * FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "TINC")}
  QUALIFY ROW_NUMBER() OVER (PARTITION BY mandt, inco1 ORDER BY IFNULL(recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) DESC) = 1
) AS TINC
  ON TINCT.mandt = TINC.mandt AND TINCT.inco1 = TINC.inco1
${sql_helper.buildDynamicWhere([
  incremental.getFilter(ctx, ["TINCT", "TINC"])
])}
AND TINCT.mandt = '400'
  `
);
"""

products = {
    'sales_groups': ('TVGRT', ['client_mandt', 'sales_group_vkgrp', 'language_key_spras']),
    'sales_offices': ('TVKBT', ['client_mandt', 'sales_office_vkbur', 'language_key_spras']),
    'sales_districts': ('T171T', ['client_mandt', 'sales_district_bzirk', 'language_key_spras']),
    'billing_document_types': ('TVFKT', ['client_mandt', 'billing_type_fkart', 'language_key_spras']),
    'payment_terms': ('T052U', ['client_mandt', 'terms_of_payment_zterm', 'language_key_spras']),
    'materials_by_sales_area': ('MVKE', ['client_mandt', 'material_number_matnr', 'sales_organization_vkorg', 'distribution_channel_vtweg']),
    'customers_by_sales_area': ('KNVV', ['client_mandt', 'customer_number_kunnr', 'sales_organization_vkorg', 'distribution_channel_vtweg', 'division_spart'])
}

for prod, (table, keys) in products.items():
    path = f'src/data_modules/custom_tramontina/sap/products/{prod}/definitions/{prod}.js'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract columns from existing SELECT
    match = re.search(r'SELECT(.*?)CURRENT_TIMESTAMP\(\) AS source_last_updated_at', content, re.DOTALL)
    if match:
        columns = match.group(1).rstrip()
        
        # Need to fix the f-string curly braces inside the template
        # So we just replace manually instead of format()
        
        new_content = template_single.replace('{keys}', str(keys)).replace('{columns}', columns).replace('{table}', table)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
    else:
        print(f'Failed to match {prod}')

# Handle incoterms separately
path_incoterms = 'src/data_modules/custom_tramontina/sap/products/incoterms/definitions/incoterms.js'
with open(path_incoterms, 'w', encoding='utf-8') as f:
    f.write(template_incoterms)

print('Updated 8 JS files.')
