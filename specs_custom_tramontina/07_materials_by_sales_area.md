# Especificação de Produto de Dados — `materials_by_sales_area`

> **Namespace:** `custom_tramontina`  ·  **SAP:** S/4HANA (`s4`)  ·  **Ordem de criação:** 7/10

## Contexto de negócio
Produto de dados custom da Tramontina, derivado da migração das pipelines de vendas (Databricks DLT → Cortex 7). Fonte SAP: **MVKE (a replicar)**. Este produto não existe no Cortex standard e cobre um gap identificado no de-para CDS↔Cortex.

## Especificação técnica
- **Nome do produto:** `materials_by_sales_area`
- **Tabela(s) fonte (raw):** `MVKE (a replicar)`
- **Granularidade / Chave primária:** `client_mandt + material_number_matnr + sales_organization_vkorg + distribution_channel_vtweg`
- **Materialização:** incremental / table
- **Filtro obrigatório:** `mandt = '400'`
- **Validação:** Nombres confirmados contra DD03L/DD04T.

## Campos

| # | Campo (Cortex) | Técnico SAP | Tabela fonte | Tipo | PK | Uso analítico |
|---|---|---|---|---|---|---|
| 1 | `client_mandt` | MANDT | MVKE | STRING | ✔ | Mandante. |
| 2 | `material_number_matnr` | MATNR | MVKE | STRING | ✔ | Material. |
| 3 | `sales_organization_vkorg` | VKORG | MVKE | STRING | ✔ | Organización de ventas. |
| 4 | `distribution_channel_vtweg` | VTWEG | MVKE | STRING | ✔ | Canal de distribución. |
| 5 | `distr_chain_material_status_vmsta` | VMSTA | MVKE | STRING |  | Estado de ventas de la cadena. |
| 6 | `distr_chain_material_status_valid_from_vmstd` | VMSTD | MVKE | DATE |  | Fecha de validez del estado. |
| 7 | `delivering_plant_dwerk` | DWERK | MVKE | STRING |  | Centro de expedición. |
| 8 | `material_pricing_group_kondm` | KONDM | MVKE | STRING |  | Grupo de material para precios. |
| 9 | `material_statistics_group_versg` | VERSG | MVKE | STRING |  | Grupo de estadística. |
| 10 | `product_hierarchy_prodh` | PRODH | MVKE | STRING |  | Jerarquía de producto. |
| 11 | `material_group_1_mvgr1` | MVGR1 | MVKE | STRING |  | Grupo de material de ventas 1. |
| 12 | `material_group_2_mvgr2` | MVGR2 | MVKE | STRING |  | Grupo de material de ventas 2. |
| 13 | `material_group_3_mvgr3` | MVGR3 | MVKE | STRING |  | Grupo de material de ventas 3. |
| 14 | `material_group_4_mvgr4` | MVGR4 | MVKE | STRING |  | Grupo de material de ventas 4. |
| 15 | `material_group_5_mvgr5` | MVGR5 | MVKE | STRING |  | Grupo de material de ventas 5. |
| 16 | `sales_unit_vrkme` | VRKME | MVKE | STRING |  | Unidad de venta. |
| 17 | `item_category_group_mtpos` | MTPOS | MVKE | STRING |  | Grupo de tipo de posición. |
| 18 | `account_assignment_group_ktgrm` | KTGRM | MVKE | STRING |  | Grupo de imputación. |
| 19 | `deletion_flag_lvorm` | LVORM | MVKE | STRING |  | Marca de borrado. |
| 20 | `source_last_updated_at` | — | MVKE | TIMESTAMP |  | Auditoría de carga (patrón Cortex). |
| 21 | `bq_loaded_at` | — | MVKE | TIMESTAMP |  | Auditoría de carga (patrón Cortex). |

## Instruções para o agente
1. Consulte o **DD03L** para confirmar tipo/comprimento de cada campo técnico SAP listado (tabela `MVKE (a replicar)`).
2. Siga a convenção de nomes do Cortex: `nome_de_negocio_campoSAP` em minúsculas; textos como `<entidade>_name_<sapfield>`.
3. Aplique o filtro de mandante `mandt = '400'`.
4. Adicione os campos de auditoria padrão do Cortex (`source_last_updated_at`, `bq_loaded_at`) se ainda não presentes.
5. Gere no namespace `custom_tramontina`, target S/4HANA (`s4`).
