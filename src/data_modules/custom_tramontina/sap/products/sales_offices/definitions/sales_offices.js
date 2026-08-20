const custom_tramontina = require("../../../../../custom_tramontina");

custom_tramontina.publishProduct({
  name: "sales_offices",
  type: "incremental",
  schema: "data_products",
  dependencies: ["sapRaw"],
  query: (
    ctx
  ) => `
SELECT
  mandt AS client_mandt,
  vkbur AS sales_office_vkbur,
  spras AS language_key_spras,
  bezei AS sales_office_name_bezei,
  CURRENT_TIMESTAMP() AS source_last_updated_at,
  CURRENT_TIMESTAMP() AS bq_loaded_at
FROM
  ${ctx.ref("sapRaw", "TVKBT")}
QUALIFY ROW_NUMBER() OVER (PARTITION BY mandt, vkbur, spras ORDER BY IFNULL(recordstamp, TIMESTAMP('1900-01-01 00:00:00+00')) DESC) = 1
  `
});
