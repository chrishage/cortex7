# Especificação de Produto de Dados — `nota_fiscal_items`

> **Namespace:** `custom_tramontina`  ·  **SAP:** S/4HANA (`s4`)  ·  **Ordem de criação:** 10/10

## Contexto de negócio
Produto custom da Tramontina para **Nota Fiscal brasileira (NF/NF-e)**, derivado da migração das pipelines de vendas. Fonte SAP Brazil Localization: **j_1bnflin**. Cobre a camada fiscal que não existe no Cortex standard.

## Especificação técnica
- **Nome do produto:** `nota_fiscal_items`
- **Tabela(s) fonte (raw):** `j_1bnflin`
- **Granularidade / Chave primária:** `client_mandt + nota_fiscal_document_docnum + nota_fiscal_item_itmnum`
- **Materialização:** type=view
- **Filtro obrigatório:** `mandt = '400'`
- **Estado:** CONFIRMADO contra el SQLX deployado

## Campos

| # | Campo (Cortex) | Técnico SAP | Tabela fonte | Tipo | PK | Uso analítico |
|---|---|---|---|---|---|---|
| 1 | `client_mandt` | MANDT | j_1bnflin | STRING | ✔ | Mandante. |
| 2 | `nota_fiscal_document_docnum` | DOCNUM | j_1bnflin | STRING | ✔ | Nº del documento fiscal — ligación con headers. |
| 3 | `nota_fiscal_item_itmnum` | ITMNUM | j_1bnflin | STRING | ✔ | Número de ítem de la NF. |
| 4 | `material_number_matnr` | MATNR | j_1bnflin | STRING |  | Material del ítem. |
| 5 | `quantity_menge` | MENGE | j_1bnflin | NUMERIC |  | Cantidad de la NF. |
| 6 | `net_price_netpr` | NETPR | j_1bnflin | NUMERIC |  | Precio neto del ítem. |
| 7 | `nota_fiscal_total_amount_nfnett` | NFNETT | j_1bnflin | NUMERIC |  | Valor total de la nota fiscal. |
| 8 | `net_value_netwr` | NETWR | j_1bnflin | NUMERIC |  | Valor neto del ítem. |
| 9 | `net_freight_netfre` | NETFRE | j_1bnflin | NUMERIC |  | Flete neto del ítem. |

## Instruções para o agente
1. Consulte o **DD03L** para confirmar tipo/comprimento dos campos da(s) tabela(s) `j_1bnflin`.
2. Materializar como **VIEW** (type=view) — sem campos de auditoria.
3. Aplique o filtro `mandt = '400'`.
5. Gere no namespace `custom_tramontina`, target S/4HANA (`s4`).
