# Produtos custom_tramontina — ordem de criação

Alimente o agente do Antigravity **um produto por vez**, nesta ordem (dimensões/textos primeiro, transacionais depois, NF por último) — conforme recomendação do manual para evitar perda de contexto.

01. **sales_groups** — fonte TVGRT — 6 campos — grão: client_mandt + sales_group_vkgrp + language_key_spras
02. **sales_offices** — fonte TVKBT — 6 campos — grão: client_mandt + sales_office_vkbur + language_key_spras
03. **sales_districts** — fonte T171T — 6 campos — grão: client_mandt + sales_district_bzirk + language_key_spras
04. **billing_document_types** — fonte TVFKT — 6 campos — grão: client_mandt + billing_type_fkart + language_key_spras
05. **payment_terms** — fonte T052U (ya replicada) — 6 campos — grão: client_mandt + terms_of_payment_zterm + language_key_spras
06. **incoterms** — fonte TINCT (texto) + TINC (config, a replicar) — 7 campos — grão: client_mandt + incoterms_classification_inco1 + language_key_spras
07. **materials_by_sales_area** — fonte MVKE (a replicar) — 21 campos — grão: client_mandt + material_number_matnr + sales_organization_vkorg + distribution_channel_vtweg
08. **customers_by_sales_area** — fonte KNVV (a replicar) — 25 campos — grão: client_mandt + customer_number_kunnr + sales_organization_vkorg + distribution_channel_vtweg + division_spart
09. **** — fonte j_1bnfdoc (WHERE client_mandt='400') — 17 campos — grão: client_mandt + nota_fiscal_document_docnum
10. **** — fonte j_1bnflin — 9 campos — grão: client_mandt + nota_fiscal_document_docnum + nota_fiscal_item_itmnum

## Como usar cada spec com o agente
No chat do Antigravity, por produto:
```
Crie um produto de dados Cortex no namespace custom_tramontina, target S/4HANA,
conforme a especificação no arquivo specs_custom_tramontina/<arquivo>.md.
Consulte o DD03L para validar os campos e me mostre o plano antes de gerar.
```