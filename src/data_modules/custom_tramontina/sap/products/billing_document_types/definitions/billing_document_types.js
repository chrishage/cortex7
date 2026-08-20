const custom_tramontina = require("../../../../../custom_tramontina");

custom_tramontina.publishProduct({
  name: "billing_document_types",
  type: "incremental",
  schema: "data_products",
  dependencies: ["sapRaw"],
  query: (
    ctx
  ) => `
SELECT
  mandt AS client_mandt,
  fkart AS billing_type_fkart,
  spras AS language_key_spras,
  vtext AS billing_type_name_vtext,
  CURRENT_TIMESTAMP() AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM
  ${ctx.ref("sapRaw", "TVFKT")}
QUALIFY ROW_NUMBER() OVER (PARTITION BY mandt, fkart, spras ORDER BY IFNULL(recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) DESC) = 1
  `
});
