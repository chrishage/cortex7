const custom_tramontina = require("../../../../../custom_tramontina");

custom_tramontina.publishProduct({
  name: "sales_districts",
  type: "incremental",
  schema: "data_products",
  dependencies: ["sapRaw"],
  query: (
    ctx
  ) => `
SELECT
  mandt AS client_mandt,
  bzirk AS sales_district_bzirk,
  spras AS language_key_spras,
  bztxt AS sales_district_name_bztxt,
  CURRENT_TIMESTAMP() AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM
  ${ctx.ref("sapRaw", "T171T")}
QUALIFY ROW_NUMBER() OVER (PARTITION BY mandt, bzirk, spras ORDER BY IFNULL(recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) DESC) = 1
  `
});
