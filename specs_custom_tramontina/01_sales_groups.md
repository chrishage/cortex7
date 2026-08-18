# Especificação de Produto de Dados — `sales_groups`

> **Namespace:** `custom_tramontina`  ·  **SAP:** S/4HANA (`s4`)  ·  **Ordem de criação:** 1/10

## Contexto de negócio
Produto de dados custom da Tramontina, derivado da migração das pipelines de vendas (Databricks DLT → Cortex 7). Fonte SAP: **TVGRT**. Este produto não existe no Cortex standard e cobre um gap identificado no de-para CDS↔Cortex.

## Especificação técnica
- **Nome do produto:** `sales_groups`
- **Tabela(s) fonte (raw):** `TVGRT`
- **Granularidade / Chave primária:** `client_mandt + sales_group_vkgrp + language_key_spras`
- **Materialização:** incremental / table
- **Filtro obrigatório:** `mandt = '400'`
- **Validação:** Nombres confirmados contra DD03L/DD04T.

## Campos

| # | Campo (Cortex) | Técnico SAP | Tabela fonte | Tipo | PK | Uso analítico |
|---|---|---|---|---|---|---|
| 1 | `client_mandt` | MANDT | TVGRT | STRING | ✔ | Mandante. |
| 2 | `sales_group_vkgrp` | VKGRP | TVGRT | STRING | ✔ | Código. |
| 3 | `language_key_spras` | SPRAS | TVGRT | STRING | ✔ | Idioma. |
| 4 | `sales_group_name_bezei` | BEZEI | TVGRT | STRING |  | Descripción. |
| 5 | `source_last_updated_at` | — | TVGRT | TIMESTAMP |  | Auditoría de carga (patrón Cortex). |
| 6 | `bq_loaded_at` | — | TVGRT | TIMESTAMP |  | Auditoría de carga (patrón Cortex). |

## Instruções para o agente
1. Consulte o **DD03L** para confirmar tipo/comprimento de cada campo técnico SAP listado (tabela `TVGRT`).
2. Siga a convenção de nomes do Cortex: `nome_de_negocio_campoSAP` em minúsculas; textos como `<entidade>_name_<sapfield>`.
3. Aplique o filtro de mandante `mandt = '400'`.
4. Adicione os campos de auditoria padrão do Cortex (`source_last_updated_at`, `bq_loaded_at`) se ainda não presentes.
5. Gere no namespace `custom_tramontina`, target S/4HANA (`s4`).
