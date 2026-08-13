# Especificação de Produto de Dados — `sales_offices`

> **Namespace:** `custom_tramontina`  ·  **SAP:** S/4HANA (`s4`)  ·  **Ordem de criação:** 2/10

## Contexto de negócio
Produto de dados custom da Tramontina, derivado da migração das pipelines de vendas (Databricks DLT → Cortex 7). Fonte SAP: **TVKBT**. Este produto não existe no Cortex standard e cobre um gap identificado no de-para CDS↔Cortex.

## Especificação técnica
- **Nome do produto:** `sales_offices`
- **Tabela(s) fonte (raw):** `TVKBT`
- **Granularidade / Chave primária:** `client_mandt + sales_office_vkbur + language_key_spras`
- **Materialização:** incremental / table
- **Filtro obrigatório:** `mandt = '400'`
- **Validação:** Nombres confirmados contra DD03L/DD04T.

## Campos

| # | Campo (Cortex) | Técnico SAP | Tabela fonte | Tipo | PK | Uso analítico |
|---|---|---|---|---|---|---|
| 1 | `client_mandt` | MANDT | TVKBT | STRING | ✔ | Mandante. |
| 2 | `sales_office_vkbur` | VKBUR | TVKBT | STRING | ✔ | Código. |
| 3 | `language_key_spras` | SPRAS | TVKBT | STRING | ✔ | Idioma. |
| 4 | `sales_office_name_bezei` | BEZEI | TVKBT | STRING |  | Descripción. |
| 5 | `source_last_updated_at` | — | TVKBT | TIMESTAMP |  | Auditoría de carga (patrón Cortex). |
| 6 | `bq_loaded_at` | — | TVKBT | TIMESTAMP |  | Auditoría de carga (patrón Cortex). |

## Instruções para o agente
1. Consulte o **DD03L** para confirmar tipo/comprimento de cada campo técnico SAP listado (tabela `TVKBT`).
2. Siga a convenção de nomes do Cortex: `nome_de_negocio_campoSAP` em minúsculas; textos como `<entidade>_name_<sapfield>`.
3. Aplique o filtro de mandante `mandt = '400'`.
4. Adicione os campos de auditoria padrão do Cortex (`source_last_updated_at`, `bq_loaded_at`) se ainda não presentes.
5. Gere no namespace `custom_tramontina`, target S/4HANA (`s4`).
