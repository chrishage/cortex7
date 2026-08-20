const custom_tramontina = require("../../../../../custom_tramontina");

custom_tramontina.publishProduct({
  name: "incoterms",
  type: "incremental",
  schema: "data_products",
  dependencies: ["sapRaw"],
  query: (
    ctx
  ) => `
SELECT
  TINCT.mandt AS client_mandt,
  TINCT.inco1 AS incoterms_classification_inco1,
  TINCT.spras AS language_key_spras,
  TINCT.bezei AS incoterms_classification_name_bezei,
  TINC.ortob AS incoterms_location_mandatory_ortob,
  CURRENT_TIMESTAMP() AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM
  ${ctx.ref("sapRaw", "TINCT")} AS TINCT
LEFT JOIN
  ${ctx.ref("sapRaw", "TINC")} AS TINC
  ON TINCT.mandt = TINC.mandt AND TINCT.inco1 = TINC.inco1
QUALIFY ROW_NUMBER() OVER (PARTITION BY TINCT.mandt, TINCT.inco1, TINCT.spras ORDER BY IFNULL(TINCT.recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) DESC) = 1
  `
});
