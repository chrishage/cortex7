# Especificação de Produto de Dados — `customers_by_sales_area`

> **Namespace:** `custom_tramontina`  ·  **SAP:** S/4HANA (`s4`)  ·  **Ordem de criação:** 8/10

## Contexto de negócio
Produto de dados custom da Tramontina, derivado da migração das pipelines de vendas (Databricks DLT → Cortex 7). Fonte SAP: **KNVV (a replicar)**. Este produto não existe no Cortex standard e cobre um gap identificado no de-para CDS↔Cortex.

## Especificação técnica
- **Nome do produto:** `customers_by_sales_area`
- **Tabela(s) fonte (raw):** `KNVV (a replicar)`
- **Granularidade / Chave primária:** `client_mandt + customer_number_kunnr + sales_organization_vkorg + distribution_channel_vtweg + division_spart`
- **Materialização:** incremental / table
- **Filtro obrigatório:** `mandt = '400'`
- **Validação:** Nombres confirmados contra DD03L/DD04T.

## Campos

| # | Campo (Cortex) | Técnico SAP | Tabela fonte | Tipo | PK | Uso analítico |
|---|---|---|---|---|---|---|
| 1 | `client_mandt` | MANDT | KNVV | STRING | ✔ | Mandante. |
| 2 | `customer_number_kunnr` | KUNNR | KNVV | STRING | ✔ | Cliente. |
| 3 | `sales_organization_vkorg` | VKORG | KNVV | STRING | ✔ | Organización de ventas. |
| 4 | `distribution_channel_vtweg` | VTWEG | KNVV | STRING | ✔ | Canal de distribución. |
| 5 | `division_spart` | SPART | KNVV | STRING | ✔ | Sector. |
| 6 | `sales_district_bzirk` | BZIRK | KNVV | STRING |  | Distrito de ventas. |
| 7 | `sales_group_vkgrp` | VKGRP | KNVV | STRING |  | Grupo de ventas. |
| 8 | `sales_office_vkbur` | VKBUR | KNVV | STRING |  | Oficina de ventas. |
| 9 | `customer_group_kdgrp` | KDGRP | KNVV | STRING |  | Grupo de clientes. |
| 10 | `customer_group_1_kvgr1` | KVGR1 | KNVV | STRING |  | Grupo de clientes 1. |
| 11 | `customer_group_2_kvgr2` | KVGR2 | KNVV | STRING |  | Grupo de clientes 2. |
| 12 | `customer_group_3_kvgr3` | KVGR3 | KNVV | STRING |  | Grupo de clientes 3. |
| 13 | `customer_group_4_kvgr4` | KVGR4 | KNVV | STRING |  | Grupo de clientes 4. |
| 14 | `customer_group_5_kvgr5` | KVGR5 | KNVV | STRING |  | Grupo de clientes 5. |
| 15 | `price_group_konda` | KONDA | KNVV | STRING |  | Grupo de precios. |
| 16 | `price_list_type_pltyp` | PLTYP | KNVV | STRING |  | Tipo de lista de precios. |
| 17 | `customer_statistics_group_versg` | VERSG | KNVV | STRING |  | Grupo de estadística. |
| 18 | `incoterms_classification_inco1` | INCO1 | KNVV | STRING |  | Incoterms por defecto. |
| 19 | `terms_of_payment_zterm` | ZTERM | KNVV | STRING |  | Condición de pago. |
| 20 | `currency_waers` | WAERS | KNVV | STRING |  | Moneda. |
| 21 | `delivery_priority_lprio` | LPRIO | KNVV | STRING |  | Prioridad de entrega. |
| 22 | `customer_pricing_procedure_kalks` | KALKS | KNVV | STRING |  | Esquema de cliente para pricing. |
| 23 | `deletion_flag_loevm` | LOEVM | KNVV | STRING |  | Marca de borrado del área de ventas. |
| 24 | `source_last_updated_at` | — | KNVV | TIMESTAMP |  | Auditoría de carga (patrón Cortex). |
| 25 | `bq_loaded_at` | — | KNVV | TIMESTAMP |  | Auditoría de carga (patrón Cortex). |

## Instruções para o agente
1. Consulte o **DD03L** para confirmar tipo/comprimento de cada campo técnico SAP listado (tabela `KNVV (a replicar)`).
2. Siga a convenção de nomes do Cortex: `nome_de_negocio_campoSAP` em minúsculas; textos como `<entidade>_name_<sapfield>`.
3. Aplique o filtro de mandante `mandt = '400'`.
4. Adicione os campos de auditoria padrão do Cortex (`source_last_updated_at`, `bq_loaded_at`) se ainda não presentes.
5. Gere no namespace `custom_tramontina`, target S/4HANA (`s4`).
