# Especificação de Produto de Dados — `nota_fiscal_headers`

> **Namespace:** `custom_tramontina`  ·  **SAP:** S/4HANA (`s4`)  ·  **Ordem de criação:** 9/10

## Contexto de negócio
Produto custom da Tramontina para **Nota Fiscal brasileira (NF/NF-e)**, derivado da migração das pipelines de vendas. Fonte SAP Brazil Localization: **j_1bnfdoc (WHERE client_mandt='400')**. Cobre a camada fiscal que não existe no Cortex standard.

## Especificação técnica
- **Nome do produto:** `nota_fiscal_headers`
- **Tabela(s) fonte (raw):** `j_1bnfdoc (WHERE client_mandt='400')`
- **Ampliação proposta:** LEFT JOIN j_1bnfe_active por docnum — MISMO GRANO (1:1)
- **Granularidade / Chave primária:** `client_mandt + nota_fiscal_document_docnum`
- **Materialização:** type=view
- **Filtro obrigatório:** `mandt = '400'`
- **Estado:** 9 campos CONFIRMADOS (SQLX) + NF-e propuestos (j_1bnfe_active)

## Campos

| # | Campo (Cortex) | Técnico SAP | Tabela fonte | Tipo | PK | Uso analítico |
|---|---|---|---|---|---|---|
| 1 | `client_mandt` | MANDT | j_1bnfdoc | STRING | ✔ | Mandante (filtro '400'). |
| 2 | `nota_fiscal_document_docnum` | DOCNUM | j_1bnfdoc | STRING | ✔ | Nº interno del documento fiscal (clave). |
| 3 | `company_code_bukrs` | BUKRS | j_1bnfdoc | STRING |  | Sociedad. |
| 4 | `billing_document_belnr` | BELNR | j_1bnfdoc | STRING |  | Factura de referencia. |
| 5 | `nota_fiscal_number_nfnum` | NFNUM | j_1bnfdoc | STRING |  | Número de la nota fiscal. |
| 6 | `nota_fiscal_type_nftype` | NFTYPE | j_1bnfdoc | STRING |  | Tipo de NF. |
| 7 | `document_date_docdat` | DOCDAT | j_1bnfdoc | DATE |  | Fecha del documento fiscal. |
| 8 | `nfe_number_nfenum` | NFENUM | j_1bnfdoc | STRING |  | Número de la NF-e. |
| 9 | `cancel_flag_cancel` | CANCEL | j_1bnfdoc | STRING |  | Indicador de cancelación. |
| 10 | `nfe_model_model` | MODEL | j_1bnfe_active | STRING |  | Modelo (55=NF-e). |
| 11 | `nfe_series_serie` | SERIE | j_1bnfe_active | STRING |  | Serie de la NF-e. |
| 12 | `nfe_document_status_docsta` | DOCSTA | j_1bnfe_active | STRING |  | Estado del documento electrónico. |
| 13 | `nfe_authorization_protocol_authcod` | AUTHCOD | j_1bnfe_active | STRING |  | Protocolo de autorización. |
| 14 | `nfe_authorization_date_authdate` | AUTHDATE | j_1bnfe_active | DATE |  | Fecha de autorización SEFAZ. |
| 15 | `nfe_environment_type_tpamb` | TPAMB | j_1bnfe_active | STRING |  | Ambiente (1=prod, 2=homolog). |
| 16 | `nfe_emission_type_tpemis` | TPEMIS | j_1bnfe_active | STRING |  | Tipo de emisión. |
| 17 | `nfe_access_key` | varios | j_1bnfe_active | STRING |  | Clave de acceso (44 díg.): REGIO,NFYEAR,NFMONTH,STCD1,MODEL,SERIE,NFNUM9,DOCNUM9,CDV. |

## Instruções para o agente
1. Consulte o **DD03L** para confirmar tipo/comprimento dos campos da(s) tabela(s) `j_1bnfdoc (WHERE client_mandt='400')`.
2. Materializar como **VIEW** (type=view) — sem campos de auditoria.
3. Aplique o filtro `mandt = '400'`.
4. Para a ampliação NF-e: LEFT JOIN j_1bnfe_active por docnum — MISMO GRANO (1:1). Manter grão 1:1 (não multiplicar linhas).
5. Gere no namespace `custom_tramontina`, target S/4HANA (`s4`).
