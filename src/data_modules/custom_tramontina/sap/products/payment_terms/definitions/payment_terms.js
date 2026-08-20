const custom_tramontina = require("../../../../../custom_tramontina");

custom_tramontina.publishProduct({
  name: "payment_terms",
  type: "incremental",
  schema: "data_products",
  dependencies: ["sapRaw"],
  query: (
    ctx
  ) => `
SELECT
  mandt AS client_mandt,
  zterm AS terms_of_payment_zterm,
  spras AS language_key_spras,
  text1 AS terms_of_payment_name_vtext,
  CURRENT_TIMESTAMP() AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM
  ${ctx.ref("sapRaw", "T052U")}
QUALIFY ROW_NUMBER() OVER (PARTITION BY mandt, zterm, spras ORDER BY IFNULL(recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) DESC) = 1
  `
});
