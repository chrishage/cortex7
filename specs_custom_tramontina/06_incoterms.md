# Especificação de Produto de Dados — `incoterms`

> **Namespace:** `custom_tramontina`  ·  **SAP:** S/4HANA (`s4`)  ·  **Ordem de criação:** 6/10

## Contexto de negócio
Produto de dados custom da Tramontina, derivado da migração das pipelines de vendas (Databricks DLT → Cortex 7). Fonte SAP: **TINCT (texto) + TINC (config, a replicar)**. Este produto não existe no Cortex standard e cobre um gap identificado no de-para CDS↔Cortex.

## Especificação técnica
- **Nome do produto:** `incoterms`
- **Tabela(s) fonte (raw):** `TINCT (texto) + TINC (config, a replicar)`
- **Granularidade / Chave primária:** `client_mandt + incoterms_classification_inco1 + language_key_spras`
- **Materialização:** incremental / table
- **Filtro obrigatório:** `mandt = '400'`
- **Validação:** Nombres confirmados contra DD03L/DD04T.

## Campos

| # | Campo (Cortex) | Técnico SAP | Tabela fonte | Tipo | PK | Uso analítico |
|---|---|---|---|---|---|---|
| 1 | `client_mandt` | MANDT | TINCT | STRING | ✔ | Mandante. |
| 2 | `incoterms_classification_inco1` | INCO1 | TINCT | STRING | ✔ | Código Incoterms. |
| 3 | `language_key_spras` | SPRAS | TINCT | STRING | ✔ | Idioma. |
| 4 | `incoterms_classification_name_bezei` | BEZEI | TINCT | STRING |  | Nombre del Incoterm. |
| 5 | `incoterms_location_mandatory_ortob` | ORTOB | TINC | STRING |  | Ubicación obligatoria (nivel INCO1). |
| 6 | `source_last_updated_at` | — | TINCT | TIMESTAMP |  | Auditoría de carga (patrón Cortex). |
| 7 | `bq_loaded_at` | — | TINCT | TIMESTAMP |  | Auditoría de carga (patrón Cortex). |

## Instruções para o agente
1. Consulte o **DD03L** para confirmar tipo/comprimento de cada campo técnico SAP listado (tabela `TINCT (texto) + TINC (config, a replicar)`).
2. Siga a convenção de nomes do Cortex: `nome_de_negocio_campoSAP` em minúsculas; textos como `<entidade>_name_<sapfield>`.
3. Aplique o filtro de mandante `mandt = '400'`.
4. Adicione os campos de auditoria padrão do Cortex (`source_last_updated_at`, `bq_loaded_at`) se ainda não presentes.
5. Gere no namespace `custom_tramontina`, target S/4HANA (`s4`).
