# Especificação de Produto de Dados — `billing_document_types`

> **Namespace:** `custom_tramontina`  ·  **SAP:** S/4HANA (`s4`)  ·  **Ordem de criação:** 4/10

## Contexto de negócio
Produto de dados custom da Tramontina, derivado da migração das pipelines de vendas (Databricks DLT → Cortex 7). Fonte SAP: **TVFKT**. Este produto não existe no Cortex standard e cobre um gap identificado no de-para CDS↔Cortex.

## Especificação técnica
- **Nome do produto:** `billing_document_types`
- **Tabela(s) fonte (raw):** `TVFKT`
- **Granularidade / Chave primária:** `client_mandt + billing_type_fkart + language_key_spras`
- **Materialização:** incremental / table
- **Filtro obrigatório:** `mandt = '400'`
- **Validação:** Nombres confirmados contra DD03L/DD04T.

## Campos

| # | Campo (Cortex) | Técnico SAP | Tabela fonte | Tipo | PK | Uso analítico |
|---|---|---|---|---|---|---|
| 1 | `client_mandt` | MANDT | TVFKT | STRING | ✔ | Mandante. |
| 2 | `billing_type_fkart` | FKART | TVFKT | STRING | ✔ | Código. |
| 3 | `language_key_spras` | SPRAS | TVFKT | STRING | ✔ | Idioma. |
| 4 | `billing_type_name_vtext` | VTEXT | TVFKT | STRING |  | Descripción. |
| 5 | `source_last_updated_at` | — | TVFKT | TIMESTAMP |  | Auditoría de carga (patrón Cortex). |
| 6 | `bq_loaded_at` | — | TVFKT | TIMESTAMP |  | Auditoría de carga (patrón Cortex). |

## Instruções para o agente
1. Consulte o **DD03L** para confirmar tipo/comprimento de cada campo técnico SAP listado (tabela `TVFKT`).
2. Siga a convenção de nomes do Cortex: `nome_de_negocio_campoSAP` em minúsculas; textos como `<entidade>_name_<sapfield>`.
3. Aplique o filtro de mandante `mandt = '400'`.
4. Adicione os campos de auditoria padrão do Cortex (`source_last_updated_at`, `bq_loaded_at`) se ainda não presentes.
5. Gere no namespace `custom_tramontina`, target S/4HANA (`s4`).
