#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplica as descrições de tabelas, views e colunas no dataset
tra-prd-cortex-aecorsoft.data_consumption usando a API do BigQuery.

Diferente da versão com o bq CLI, este script não chama nenhum processo
externo: fala direto com a API pela biblioteca google-cloud-bigquery. Isso
elimina de uma vez os três problemas que a CLI trouxe no Windows: prompts
interativos que travam a execução, corrupção de acentos pela página de código
e a resolução do bq.CMD no PATH.

Instalação:
    pip install google-cloud-bigquery

Autenticação (uma vez):
    gcloud auth application-default login
ou, com conta de serviço:
    $env:GOOGLE_APPLICATION_CREDENTIALS = "C:\\caminho\\chave.json"

Tratamento por tipo de objeto:
    TABLE              descrição do objeto + descrição de todas as colunas.
    VIEW               descrição do objeto. As descrições das colunas só
                       existem dentro da definição da view e o BigQuery não
                       tem comando para alterá-las, então exigem --recriar-views,
                       que salva a definição original em backup_views/ antes.
    MATERIALIZED VIEW  apenas a descrição do objeto.

Uso:
    python aplicar_descricoes_api.py --dry-run
    python aplicar_descricoes_api.py
    python aplicar_descricoes_api.py --recriar-views
"""
import argparse
import datetime
import io
import json
import os
import sys

PROJECT = "tra-prd-cortex-aecorsoft"
DATASET = "data_consumption"
BACKUP_DIR = "backup_views"

# Confirmado via `bq ls`: apenas estes tres objetos sao views. Usado so para
# avisar no inicio da execucao; o tipo real e sempre lido da API.
VIEWS_CONHECIDAS = ['dim_fatura_cortex', 'dim_produto_lancamento_cortex', 'ft_itens_fatura_cortex']

DESCRICOES = json.loads(r"""
{
 "dim_fatura_cortex": {
  "descricao": "Dimensão de cabeçalho dos documentos de faturamento (SAP SD — Billing Document). Um registro por documento de fatura por empresa, com dados da organização de vendas, do pagador, condições de pagamento, Incoterms, valores totais e status. Origem: pipeline DLT dim_fatura. Granularidade: BILLINGDOCUMENT + COMPANYCODE.",
  "colunas": {
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "SDDOCUMENTCATEGORY": "Categoria do documento SD, que classifica o tipo de documento no fluxo de vendas (ordem, remessa, fatura, entre outros).",
   "BILLINGDOCUMENTCATEGORY": "Categoria do documento de faturamento, que distingue fatura, nota de crédito, nota de débito e demais tipos.",
   "BILLINGDOCUMENTTYPE": "Código do tipo de documento de faturamento, que define o comportamento contábil e fiscal da fatura.",
   "BILLINGDOCUMENTTYPENAME": "Descrição do tipo de documento de faturamento.",
   "CREATIONDATE": "Data de criação do documento no SAP.",
   "BILLINGDOCUMENTDATE": "Data do documento de faturamento, utilizada como data de competência do faturamento.",
   "SALESORGANIZATION": "Código da organização de vendas responsável pelo documento. Define a unidade comercial que responde pela venda no SAP.",
   "DIVISION": "Código da divisão de produtos à qual o documento está associado.",
   "SALESDISTRICT": "Código do distrito de vendas, usado para segmentação geográfica da carteira comercial.",
   "COMPANYCODE": "Código da empresa (company code) no SAP, unidade contábil independente à qual o documento pertence.",
   "TOTALNETAMOUNT": "Valor líquido total do documento, somando todos os itens antes dos impostos.",
   "TOTALTAXAMOUNT": "Valor total dos impostos incidentes sobre o documento.",
   "TRANSACTIONCURRENCY": "Moeda em que a transação foi registrada, no padrão ISO de três letras.",
   "PRICELISTTYPE": "Tipo de lista de preços aplicada ao documento, que determina a tabela de preços utilizada.",
   "TAXDEPARTURECOUNTRY": "País de partida considerado para a apuração tributária da operação.",
   "INCOTERMSCLASSIFICATION": "Classificação dos Incoterms acordada, que define a divisão de responsabilidades e custos de transporte entre vendedor e comprador.",
   "PAYERPARTY": "Código do parceiro responsável pelo pagamento da fatura (payer).",
   "CUSTOMERPAYMENTTERMS": "Código das condições de pagamento acordadas com o cliente, que definem prazo e forma de quitação.",
   "BILLINGDOCUMENTISCANCELLED": "Indica se o documento de faturamento foi cancelado. Documentos cancelados não devem compor o faturamento.",
   "SDPRICINGPROCEDURE": "Procedimento de precificação SD aplicado ao documento, que determina o conjunto de condições de preço utilizadas.",
   "FISCALYEAR": "Ano fiscal ao qual o documento foi atribuído na contabilidade.",
   "DOCUMENTREFERENCEID": "Identificador do documento de referência externo associado ao faturamento.",
   "COUNTRY": "País associado ao endereço do parceiro do documento.",
   "REGION": "Região ou unidade federativa associada ao endereço do parceiro do documento.",
   "INVOICELISTTYPE": "Tipo da lista de faturas usada para agrupar documentos em uma cobrança consolidada.",
   "COMPOSITEKEY": "Chave composta para ligar a tabela (BILLINGDOCUMENT-COMPANYCODE)."
  }
 },
 "dim_nota_fiscal": {
  "descricao": "Dimensão de cabeçalho das notas fiscais brasileiras (SAP Localização Brasil — J_1BNFDOC), com o vínculo entre o documento de faturamento SD e a nota fiscal emitida, seu tipo, data e situação de cancelamento. Granularidade: BR_NFDOCNUM (um registro por nota fiscal).",
  "colunas": {
   "MANDT": "Mandante (client) do SAP ao qual o registro pertence. Identifica o ambiente lógico de origem do dado.",
   "COMPANYCODE": "Código da empresa (company code) no SAP, unidade contábil independente à qual o documento pertence.",
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "BR_NFDOCNUM": "Número interno do documento de nota fiscal no SAP (chave da tabela J_1BNFDOC). Usado para ligar o cabeçalho aos itens da nota fiscal.",
   "BR_NOTAFISCAL": "Número oficial da nota fiscal emitida, conforme a numeração fiscal brasileira.",
   "BR_NFNUM_INTERNO": "Número interno de controle da nota fiscal atribuído pelo SAP, distinto da numeração fiscal oficial informada em BR_NOTAFISCAL.",
   "NOTA_FISCAL_TYPE": "Código do tipo da nota fiscal, que classifica a operação fiscal (venda, devolução, remessa, entre outras).",
   "DOCUMENT_DATE": "Data de emissão do documento fiscal.",
   "BR_NFISCANCELED": "Indica se a nota fiscal foi cancelada perante a SEFAZ."
  }
 },
 "dim_ordem_venda": {
  "descricao": "Dimensão de cabeçalho das ordens de venda (SAP SD — Sales Order). Reúne dados comerciais, organizacionais, do cliente, condições de pagamento e datas de entrega solicitadas. Granularidade: SALESORDER (um registro por ordem de venda).",
  "colunas": {
   "SALESORDER": "Número da ordem de venda (pedido) no SAP SD. Documento que inicia o ciclo comercial.",
   "SALESORDERTYPE": "Código do tipo da ordem de venda, que define as regras de processamento do pedido (venda normal, bonificação, exportação, entre outros).",
   "SALESORDERDATE": "Data de criação da ordem de venda.",
   "SALESORGANIZATION": "Código da organização de vendas responsável pelo documento. Define a unidade comercial que responde pela venda no SAP.",
   "DISTRIBUTIONCHANNEL": "Código do canal de distribuição pelo qual o produto chega ao cliente (por exemplo venda direta ou distribuidor).",
   "ORGANIZATIONDIVISION": "Código da divisão da organização de vendas, usado para agrupar linhas de produto.",
   "SALESGROUP": "Código do grupo de vendas responsável pelo atendimento comercial do documento.",
   "SALESOFFICE": "Código do escritório de vendas responsável pela região comercial do documento.",
   "SOLDTOPARTY": "Código do cliente emissor da ordem (sold-to party), parceiro que efetua a compra.",
   "OVERALLSDPROCESSSTATUS": "Status geral de processamento do documento no fluxo SD: em aberto, parcialmente processado ou concluído.",
   "OVERALLSDDOCUMENTREJECTIONSTS": "Status geral de rejeição do documento SD, que indica se a ordem foi total ou parcialmente rejeitada.",
   "OVERALLDELIVERYSTATUS": "Status geral de entrega do documento: não entregue, parcialmente entregue ou totalmente entregue.",
   "TOTALNETAMOUNT": "Valor líquido total do documento, somando todos os itens antes dos impostos.",
   "TRANSACTIONCURRENCY": "Moeda em que a transação foi registrada, no padrão ISO de três letras.",
   "INCOTERMSCLASSIFICATION": "Classificação dos Incoterms acordada, que define a divisão de responsabilidades e custos de transporte entre vendedor e comprador.",
   "CUSTOMERPAYMENTTERMS": "Código das condições de pagamento acordadas com o cliente, que definem prazo e forma de quitação.",
   "PRICINGDATEORDER": "Data de precificação do documento de ordem de venda.",
   "SALESORDERTYPENAME": "Descrição textual do tipo da ordem de venda.",
   "SOLDTOPARTYNAME": "Nome ou razão social do cliente emissor da ordem de venda (sold-to party)."
  }
 },
 "dim_produto_lancamento": {
  "descricao": "Dimensão de produtos com o histórico consolidado de vendas e a marcação de lançamento. Considera lançamento o material cuja primeira venda ocorreu nos últimos 12 meses. Granularidade: Produto (um registro por material).",
  "colunas": {
   "Produto": "Código do material (SKU) conforme o cadastro de materiais do SAP.",
   "PrimeiraVenda": "Data da primeira venda registrada para o material, considerando o histórico consolidado de SAP e SIT.",
   "ValorTotalHistorico": "Valor total histórico faturado do material desde a primeira venda, em BRL.",
   "QuantidadeHistorica": "Quantidade total histórica vendida do material desde a primeira venda.",
   "Lancamento": "Indicador booleano de lançamento: verdadeiro quando a primeira venda do material ocorreu nos últimos 12 meses.",
   "bq_loaded_at": "Campo técnico de controle: data e hora em que o registro foi carregado no BigQuery pelo processo de ingestão."
  }
 },
 "dim_produto_lancamento_cortex": {
  "descricao": "Versão reduzida da dimensão de produtos em lançamento, contendo apenas o material, a data da primeira venda e o indicador de lançamento. Origem: pipeline DLT dim_produtos_lancamentos. Granularidade: Produto.",
  "colunas": {
   "Produto": "Código do material (SKU) conforme o cadastro de materiais do SAP.",
   "PrimeiraVenda": "Data da primeira venda registrada para o material, considerando o histórico consolidado de SAP e SIT.",
   "IndicadorLancamento": "Indicador booleano de lançamento: verdadeiro quando a primeira venda do material ocorreu nos últimos 12 meses."
  }
 },
 "dim_remessa": {
  "descricao": "Dimensão de cabeçalho dos documentos de remessa/entrega (SAP SD — Delivery Document), com dados de expedição, centro fornecedor, transporte e status de picking e de movimentação de mercadoria. Granularidade: DELIVERYDOCUMENT.",
  "colunas": {
   "DELIVERYDOCUMENT": "Número do documento de remessa (entrega) no SAP SD, gerado a partir da ordem de venda para expedição da mercadoria.",
   "DELIVERYDOCUMENTTYPE": "Código do tipo de documento de remessa, que define as regras de expedição aplicadas.",
   "CREATIONDATE": "Data de criação do documento no SAP.",
   "TRANSPORTATIONPLANNINGDATE": "Data de transportação da remessa (faturamento).",
   "SHIPPINGPOINT": "Código do local de expedição responsável pela saída física da mercadoria.",
   "SALESORGANIZATION": "Código da organização de vendas responsável pelo documento. Define a unidade comercial que responde pela venda no SAP.",
   "SHIPTOPARTY": "Código do cliente recebedor da mercadoria (ship-to party), parceiro que recebe a entrega.",
   "INCOTERMSCLASSIFICATION": "Classificação dos Incoterms acordada, que define a divisão de responsabilidades e custos de transporte entre vendedor e comprador.",
   "OVERALLDELIVRELTDBILLGSTATUS": "Status de faturamento relacionado à remessa, indicando o quanto da entrega já foi faturado."
  }
 },
 "ft_acompanhamento_de_vendas": {
  "descricao": "Fato de acompanhamento diário do ciclo de vendas. Consolida, no nível do item da ordem, o encadeamento ordem → remessa → fatura → nota fiscal, somando a reserva de estoque calculada pelo ATP, o agendamento de transporte e o status do funil (Sankey). É a base analítica principal da área comercial. Granularidade: item da ordem de venda na data de análise.",
  "colunas": {
   "SALESORDER": "Número da ordem de venda (pedido) no SAP SD. Documento que inicia o ciclo comercial.",
   "SALESORDERITEM": "Número do item dentro da ordem de venda. Junto de SALESORDER, identifica unicamente a linha do pedido.",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "SOLDTOPARTY": "Código do cliente emissor da ordem (sold-to party), parceiro que efetua a compra.",
   "NomeCliente": "Nome fantasia do cliente associado ao documento.",
   "MERCADO": "Informa se a venda é de mercado Interno ou Mercado Externo.",
   "Moeda": "Sigla da moeda utilizada na transação, no padrão ISO de três letras.",
   "TRANSACTIONCURRENCYPRICE": "Valor da cotação da moeda utilizada na fatura.",
   "DELIVERYBLOCKREASON": "Código do motivo de bloqueio de entrega aplicado ao documento, que impede a geração da remessa até a liberação.",
   "DELIVERYDOCUMENT": "Número do documento de remessa (entrega) no SAP SD, gerado a partir da ordem de venda para expedição da mercadoria.",
   "DataCriacaoRemessa": "Data de criação do documento de remessa no SAP.",
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "BILLINGDOCUMENTDATE": "Data do documento de faturamento, utilizada como data de competência do faturamento.",
   "QuantidadeEmOrdem": "Quantidade do item ainda em carteira, ou seja, pedida na ordem de venda e não convertida em remessa.",
   "QuantidadeEmRemessa": "Quantidade do item já convertida em documento de remessa e comprometida para expedição.",
   "QuantidadeVendida": "Quantidade total efetivamente vendida e faturada no período.",
   "Faturamento": "Valor do faturamento efetivamente realizado para o item, em BRL, considerando apenas as faturas válidas segundo a regra do campo FATURAR.",
   "PRICINGDATEORDER": "Data de precificação do documento de ordem de venda.",
   "QuantidadeReservadaATP": "Quantidade de estoque reservado pelo ATP para gerar remessa de ordem de venda.",
   "DiasEmOrdem": "Dias em ordem. Diferença entre datas (Data de criação Remessa - Data de criação ordem de venda).",
   "DiasEmPlanejamento": "Dias em planejamento. Diferença entre datas (Data de criação ordem de frete - Data de criação remessa).",
   "IndicadorPedidoCompleto": "Indicador com 1 ou 0 se o pedido está completamente faturado, ou se ainda reste itens em remessa ou ordem para concluir.",
   "IndicadorPedidoIncompleto": "Indicador com 1 ou 0 se o pedido está incompleto de estar todo em remessa.",
   "IndicadorPedidoCarteiraMesPassado": "Indicador com 1 ou 0 se o pedido está pendente do Mês passado.",
   "IndicadorPedidoCarteiraMesesAnteriores": "Indicador com 1 ou 0 se o pedido está pendente a mais de um mês.",
   "SankeyStatus": "Descrição do status em que parte do sankey a linha se encaixa.",
   "TMStatus": "Descrição do Status acomulado na etapa que o item do pedido está no faturamento.",
   "bq_loaded_at": "Campo técnico de controle: data e hora em que o registro foi carregado no BigQuery pelo processo de ingestão."
  }
 },
 "ft_atp_sap": {
  "descricao": "Fato do cálculo ATP (Available To Promise): distribui o estoque disponível entre os itens de ordem de venda em aberto, seguindo a ordem de prioridade definida pelo campo Rank e reproduzindo a lógica de alocação do SAP. Granularidade: SALESORDER + SALESORDERITEM + MATERIAL + BATCH.",
  "colunas": {
   "SALESORDER": "Número da ordem de venda (pedido) no SAP SD. Documento que inicia o ciclo comercial.",
   "SALESORDERITEM": "Número do item dentro da ordem de venda. Junto de SALESORDER, identifica unicamente a linha do pedido.",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "BATCH": "Código do lote (batch) do material, usado para rastreabilidade da mercadoria.",
   "QuantidadeEmOrdem": "Quantidade do item ainda em carteira, ou seja, pedida na ordem de venda e não convertida em remessa.",
   "DataPrevisaoEntrega": "Data prevista de entrega do item, utilizada para ordenar a alocação do estoque no cálculo ATP.",
   "Rank": "Posição de prioridade do item na fila de alocação do ATP. Quanto menor o valor, mais cedo o item recebe estoque.",
   "EstoqueDisponivel": "Quantidade Total menos a quantidade em remessa do material.",
   "QuantidadeAtendida": "Quantidade de estoque reservado para atender a Ordem.",
   "bq_loaded_at": "Campo técnico de controle: data e hora em que o registro foi carregado no BigQuery pelo processo de ingestão."
  }
 },
 "ft_estoques_de_venda": {
  "descricao": "Fato de posição do estoque disponível para venda por material, lote e centro. O estoque disponível corresponde ao estoque total menos o volume já comprometido em remessas. Granularidade: MATERIAL + BATCH + PLANT.",
  "colunas": {
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "BATCH": "Código do lote (batch) do material, usado para rastreabilidade da mercadoria.",
   "PLANT": "Código do centro (plant) onde o material está fisicamente armazenado ou é produzido.",
   "EstoqueTotal": "Quantidade total de material em estoque disponível para utilização, porém podem estar reservados para remessas.",
   "QuantidadeEmRemessa": "Quantidade do item já convertida em documento de remessa e comprometida para expedição.",
   "EstoqueDisponivel": "Quantidade Total menos a quantidade em remessa do material.",
   "bq_loaded_at": "Campo técnico de controle: data e hora em que o registro foi carregado no BigQuery pelo processo de ingestão."
  }
 },
 "ft_itens_fatura": {
  "descricao": "Fato de itens dos documentos de faturamento (SAP SD — Billing Document Item), versão reduzida com os campos essenciais de quantidade, valor e vínculo com a remessa de origem. Granularidade: BILLINGDOCUMENT + BILLINGDOCUMENTITEM + COMPANYCODE.",
  "colunas": {
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "BILLINGDOCUMENTITEM": "Número do item dentro do documento de faturamento. Junto de BILLINGDOCUMENT, identifica unicamente a linha faturada.",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "BILLINGQUANTITY": "Quantidade efetivamente faturada no item, na unidade de medida de faturamento.",
   "NETAMOUNT": "Valor líquido do item, já descontados abatimentos e antes dos impostos, na moeda da transação.",
   "TOTALAMOUNT": "Valor total da fatura com o valor dos impostos juntos.",
   "ACCOUNTINGEXCHANGERATE": "Taxa de câmbio contábil proveniente do sistema SIT, aplicada na conversão dos valores do item.",
   "BILLINGDOCUMENTTYPE": "Código do tipo de documento de faturamento, que define o comportamento contábil e fiscal da fatura.",
   "BILLINGDOCUMENTDATE": "Data do documento de faturamento, utilizada como data de competência do faturamento.",
   "SALESORGANIZATION": "Código da organização de vendas responsável pelo documento. Define a unidade comercial que responde pela venda no SAP.",
   "TRANSACTIONCURRENCY": "Moeda em que a transação foi registrada, no padrão ISO de três letras.",
   "PAYERPARTY": "Código do parceiro responsável pelo pagamento da fatura (payer).",
   "RULE": "Campo que informa a regra definida com o que ocorre com o valor dessa fatura.",
   "FATURAR": "Campo de verdadeiro ou falso que informa se o fatura deve somar ou não.",
   "FaturamentoBrutoBRL": "Somente Quantidade Realmente faturada em valor bruto."
  }
 },
 "ft_itens_fatura_cortex": {
  "descricao": "Fato de itens dos documentos de faturamento (SAP SD — Billing Document Item), versão completa. Inclui valores líquidos, impostos, taxas de conversão, referências à ordem e à remessa, situação de cancelamento e a regra de negócio que define se o item soma no faturamento (campos RULE e FATURAR). Granularidade: BILLINGDOCUMENT + BILLINGDOCUMENTITEM + COMPANYCODE.",
  "colunas": {
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "BILLINGDOCUMENTITEM": "Número do item dentro do documento de faturamento. Junto de BILLINGDOCUMENT, identifica unicamente a linha faturada.",
   "SALESDOCUMENTITEMCATEGORY": "Categoria do item do documento de vendas, que define o comportamento do item no fluxo (item normal, bonificação, texto, entre outros).",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "PRODUCT": "Código do produto conforme o cadastro de produtos do SAP, equivalente ao material.",
   "BILLINGDOCUMENTITEMTEXT": "Texto descritivo do item do documento de faturamento, normalmente a denominação do material.",
   "BATCH": "Código do lote (batch) do material, usado para rastreabilidade da mercadoria.",
   "FaturamentoBrutoBRL": "Somente Quantidade Realmente faturada em valor bruto.",
   "BILLINGQUANTITY": "Quantidade efetivamente faturada no item, na unidade de medida de faturamento.",
   "BILLINGQUANTITYUNIT": "Unidade de medida em que a quantidade faturada está expressa.",
   "NETAMOUNT": "Valor líquido do item, já descontados abatimentos e antes dos impostos, na moeda da transação.",
   "TOTALAMOUNT": "Valor total da fatura com o valor dos impostos juntos.",
   "TRANSACTIONCURRENCY": "Moeda em que a transação foi registrada, no padrão ISO de três letras.",
   "PRICEDETNEXCHANGERATE": "Taxa de câmbio usada na determinação do preço do item, aplicada na conversão para a moeda da empresa.",
   "ACCOUNTINGEXCHANGERATE": "Taxa de câmbio contábil proveniente do sistema SIT, aplicada na conversão dos valores do item.",
   "TAXAMOUNT": "Valor dos impostos incidentes sobre o item.",
   "COSTAMOUNT": "Valor do custo do item, usado na apuração da margem da venda.",
   "PRICINGDATE": "Data de precificação do item, referência para a determinação de preços e da taxa de câmbio aplicada.",
   "REFERENCESDDOCUMENT": "Número do documento SD de referência que originou este registro, normalmente a ordem de venda ou a remessa antecedente.",
   "REFERENCESDDOCUMENTITEM": "Número do item no documento SD de referência que originou este registro.",
   "CANCELLEDBILLINGDOCUMENT": "Documento de fatura de referencia se está cancelado.",
   "BILLINGDOCUMENTISCANCELLED": "Indica se o documento de faturamento foi cancelado. Documentos cancelados não devem compor o faturamento.",
   "BILLINGDOCUMENTISTEMPORARY": "Se a Fatura é temporária, marcada com X caso for se não campo é nulo.",
   "OVERALLBILLINGSTATUS": "Status geral de faturamento do documento: não faturado, parcialmente faturado ou totalmente faturado.",
   "OVERALLBILLINGSTATUSNAME": "Descrição do status geral do documento de fatura.",
   "RULE": "Campo que informa a regra definida com o que ocorre com o valor dessa fatura.",
   "FATURAR": "Campo de verdadeiro ou falso que informa se o fatura deve somar ou não.",
   "COMPANYCODE": "Código da empresa (company code) no SAP, unidade contábil independente à qual o documento pertence.",
   "SALESORDERREFERENCE": "Número da ordem de venda que originou o item faturado.",
   "SALESORDERITEMREFERENCE": "Número do item da ordem de venda que originou o item faturado.",
   "DELIVERYDOCUMENTREFERENCE": "Número do documento de remessa que originou o item faturado.",
   "DELIVERYDOCUMENTITEMREFERENCE": "Número do item da remessa que originou o item faturado.",
   "CompositeKey": "BILLINGDOCUMENT-BILLINGDOCUMENTITEM-COMPANYCODE.",
   "REMESSA_FK": "Chave estrangeira para os itens de remessa, composta por REFERENCESDDOCUMENT, REFERENCESDDOCUMENTITEM e COMPANYCODE.",
   "FATURA_FK": "Chave estrangeira para a dimensão de faturas, composta por BILLINGDOCUMENT e COMPANYCODE."
  }
 },
 "ft_itens_nota_fiscal": {
  "descricao": "Fato de itens das notas fiscais brasileiras (SAP Localização Brasil — J_1BNFLIN), com quantidade, valores e o vínculo com o item do documento de faturamento que originou a nota. Granularidade: BR_NFDOCNUM + item da nota fiscal.",
  "colunas": {
   "MANDT": "Mandante (client) do SAP ao qual o registro pertence. Identifica o ambiente lógico de origem do dado.",
   "BR_NFDOCNUM": "Número interno do documento de nota fiscal no SAP (chave da tabela J_1BNFDOC). Usado para ligar o cabeçalho aos itens da nota fiscal.",
   "BR_NOTAFISCALITEM": "Número do item dentro da nota fiscal.",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "QUANTITYINBASEUNIT": "Quantidade vendida convertida para a unidade de medida base do material.",
   "NETPRICEAMOUNT": "Preço líquido unitário do item, na moeda da transação.",
   "BR_NFTOTALAMOUNT": "Valor total do item na nota fiscal, incluindo impostos e encargos.",
   "NETVALUEAMOUNT": "Valor líquido do produto na nota fiscal, antes dos impostos.",
   "BR_NFNETFREIGHTAMOUNT": "Valor líquido do frete atribuído ao item da nota fiscal.",
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "BR_NOTAFISCAL": "Número oficial da nota fiscal emitida, conforme a numeração fiscal brasileira."
  }
 },
 "ft_itens_ordem_de_venda": {
  "descricao": "Fato de itens das ordens de venda (SAP SD — Sales Order Item), com quantidades pedidas, preços, condições de moeda, datas previstas e status de processamento do item. Granularidade: SALESORDER + SALESORDERITEM.",
  "colunas": {
   "SALESORDER": "Número da ordem de venda (pedido) no SAP SD. Documento que inicia o ciclo comercial.",
   "SALESORDERITEM": "Número do item dentro da ordem de venda. Junto de SALESORDER, identifica unicamente a linha do pedido.",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "REQUIREMENTSEGMENT": "Segmento de necessidade (requirement segment) usado na segmentação de estoque e no planejamento de disponibilidade.",
   "PLANT": "Código do centro (plant) onde o material está fisicamente armazenado ou é produzido.",
   "STORAGELOCATION": "Código do depósito (storage location) dentro do centro em que o material está armazenado.",
   "ORDERQUANTITY": "Quantidade solicitada pelo cliente no item da ordem de venda.",
   "NETAMOUNT": "Valor líquido do item, já descontados abatimentos e antes dos impostos, na moeda da transação.",
   "NETPRICEAMOUNT": "Preço líquido unitário do item, na moeda da transação.",
   "TAXAMOUNT": "Valor dos impostos incidentes sobre o item.",
   "TRANSACTIONCURRENCY": "Moeda em que a transação foi registrada, no padrão ISO de três letras.",
   "SDPROCESSSTATUS": "Status de processamento do item no fluxo SD.",
   "DELIVERYBLOCKREASON": "Informa o código de bloqueio de remessa, caso não houver a ordem de venda está liberada para seguir para remessa.",
   "SALESORDERTYPE": "Código do tipo da ordem de venda, que define as regras de processamento do pedido (venda normal, bonificação, exportação, entre outros).",
   "PRICINGDATEORDER": "Data de precificação do documento de ordem de venda.",
   "ValorMoedaSIT": "Taxa de conversão da moeda proveniente do sistema SIT, aplicada aos valores do item.",
   "FaturamentoPrevistoBRL": "Valor previsto de faturamento do item em BRL, calculado sobre a quantidade em carteira e o preço da ordem."
  }
 },
 "ft_itens_remessa": {
  "descricao": "Fato de itens dos documentos de remessa (SAP SD — Delivery Document Item), com as quantidades expedidas e a referência ao item da ordem de venda de origem. Granularidade: DELIVERYDOCUMENT + DELIVERYDOCUMENTITEM.",
  "colunas": {
   "DELIVERYDOCUMENT": "Número do documento de remessa (entrega) no SAP SD, gerado a partir da ordem de venda para expedição da mercadoria.",
   "DELIVERYDOCUMENTITEM": "Número do item dentro do documento de remessa. Junto de DELIVERYDOCUMENT, identifica unicamente a linha expedida.",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "ACTUALDELIVERYQUANTITY": "Quantidade efetivamente expedida no item da remessa.",
   "ORIGINALDELIVERYQUANTITY": "Quantidade originalmente prevista no item da remessa, antes de eventuais ajustes de expedição.",
   "SDPROCESSSTATUS": "Status de processamento do item no fluxo SD.",
   "REFERENCESDDOCUMENT": "Número do documento SD de referência que originou este registro, normalmente a ordem de venda ou a remessa antecedente.",
   "REFERENCESDDOCUMENTITEM": "Número do item no documento SD de referência que originou este registro."
  }
 },
 "ft_resumo_carteira_venda_diario": {
  "descricao": "Fato agregado com a fotografia diária da carteira de vendas, valorizada em BRL e em USD. Consolida por dia, mercado e motivo de bloqueio os valores em ordem, em remessa, cobertos por estoque e já faturados, para o mês corrente e para o mês seguinte. A tabela é reprocessada por sobrescrita total (overwrite) a cada execução. Granularidade: Dia + MesAnalise + MERCADO + CodigoBloqueio.",
  "colunas": {
   "Dia": "Data de referência da fotografia diária da carteira.",
   "MesAnalise": "Primeiro dia do mês ao qual os valores agregados se referem. A tabela contém o mês corrente e o mês seguinte.",
   "MERCADO": "Mercado de destino da venda: Interno (mercado nacional) ou Externo (exportação).",
   "CodigoBloqueio": "Código do motivo de bloqueio de remessa do item (DELIVERYBLOCKREASON). Assume o valor \"Sem Bloqueio\" quando o item não possui bloqueio.",
   "ValorEmOrdem": "Valor da carteira em ordem sem bloqueio, em BRL. Calculado pela quantidade em ordem multiplicada pelo preço médio de fatura do item.",
   "ValorEmRemessa": "Valor da carteira já convertido em remessa, em BRL. Calculado pela quantidade em remessa multiplicada pelo preço médio de fatura do item.",
   "ValorEstoque": "Valor da carteira coberta por estoque disponível, correspondente à quantidade reservada no ATP, em BRL.",
   "Faturamento": "Faturamento realizado no mês de análise, em BRL.",
   "ValorEmOrdemDolar": "Valor da carteira em ordem sem bloqueio, em USD. Calculado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "FaturamentoDolar": "Faturamento realizado no mês de análise, em USD. Calculado apenas para o mercado externo."
  }
 },
 "obt_sales_pipeline": {
  "descricao": "One Big Table (OBT) do funil de vendas: uma linha por item de ordem de venda com o documento de remessa, a fatura e a nota fiscal correspondentes já desnormalizados, dispensando joins no consumo por ferramentas de BI. Origem: pipeline DLT obt_sales_department. Granularidade: SALESORDER + SALESORDERITEM, desdobrada pelos documentos subsequentes.",
  "colunas": {
   "SALESORDER": "Número da ordem de venda (pedido) no SAP SD. Documento que inicia o ciclo comercial.",
   "SALESORDERITEM": "Número do item dentro da ordem de venda. Junto de SALESORDER, identifica unicamente a linha do pedido.",
   "SALESORDERTYPE": "Tipo do Pedido de Venda unico, pode ser o Pedido de Venda, remessa ou Fatura.",
   "SALESORDERDATE": "Data de criação da ordem de venda.",
   "SOLDTOPARTY": "Código do cliente emissor da ordem (sold-to party), parceiro que efetua a compra.",
   "SALESORGANIZATION": "Organização de Vendas, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "QuantidadeEmOrdem": "Quantidade do item ainda em carteira, ou seja, pedida na ordem de venda e não convertida em remessa.",
   "PrecoUnitarioOrdem": "Preço unitário do item na ordem de venda, na moeda da transação.",
   "FaturamentoPrevistoBRL": "Valor previsto de faturamento do item em BRL, calculado sobre a quantidade em carteira e o preço da ordem.",
   "DELIVERYBLOCKREASON": "Código do motivo de bloqueio de entrega aplicado ao documento, que impede a geração da remessa até a liberação.",
   "PRICINGDATEORDER": "Data de precificação da ordem de venda, referência para a determinação do preço e da cotação de câmbio.",
   "StatusItemOrdem": "Status geral de processamento do item da ordem de venda no SAP (em aberto, parcialmente processado ou concluído).",
   "SALESORDERTYPENAME": "Nome do Tipo do Pedido de Venda unico, pode ser o Pedido de Venda, remessa ou Fatura.",
   "SOLDTOPARTYNAME": "Nome ou razão social do cliente emissor da ordem de venda (sold-to party).",
   "DELIVERYDOCUMENT": "Número do documento de remessa (entrega) no SAP SD, gerado a partir da ordem de venda para expedição da mercadoria.",
   "QuantidadeEmRemessa": "Quantidade do item já convertida em documento de remessa e comprometida para expedição.",
   "DataCriacaoRemessa": "Data de criação do documento de remessa no SAP.",
   "StatusRemessa": "Status geral de processamento do documento de remessa no SAP.",
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "BILLINGDOCUMENTDATE": "Data do documento de faturamento, utilizada como data de competência do faturamento.",
   "QuantidadeVendida": "Quantidade total efetivamente vendida e faturada no período.",
   "Faturamento": "Valor do faturamento efetivamente realizado para o item, em BRL, considerando apenas as faturas válidas segundo a regra do campo FATURAR.",
   "RULE": "Regra de negócio aplicada ao item, que determina como o valor da fatura é tratado no cálculo do faturamento.",
   "FATURAR": "Indicador que informa se o item deve ou não ser somado no faturamento, conforme a regra apurada no campo RULE.",
   "BR_NOTAFISCAL": "Número oficial da nota fiscal emitida, conforme a numeração fiscal brasileira.",
   "bq_loaded_at": "Campo técnico de controle: data e hora em que o registro foi carregado no BigQuery pelo processo de ingestão."
  }
 },
 "snapshot_sales_order": {
  "descricao": "Histórico SCD Tipo 2 das ordens de venda, criado para preservar a evolução da data de entrega solicitada ao longo do tempo. Cada linha representa o estado da ordem em uma data de snapshot. Granularidade: SALESORDER + __SNAPSHOT_DATE.",
  "colunas": {
   "SALESORDER": "Número da ordem de venda (pedido) no SAP SD. Documento que inicia o ciclo comercial.",
   "REQUESTEDDELIVERYDATE": "Data de entrega solicitada pelo cliente na ordem de venda, na versão vigente do snapshot.",
   "__SNAPSHOT_DATE": "Data do snapshot que originou esta versão do registro no histórico SCD Tipo 2.",
   "__LOADED_AT": "Campo técnico de controle: data e hora em que esta versão do registro foi gravada no histórico."
  }
 },
 "snapshot_schedule_lines": {
  "descricao": "Histórico SCD Tipo 2 das linhas de programação (schedule lines) das ordens de venda, criado para preservar a evolução da data de disponibilidade do produto. Granularidade: SALESORDER + SALESORDERITEM + SCHEDULELINE + __SNAPSHOT_DATE.",
  "colunas": {
   "SALESORDER": "Número da ordem de venda (pedido) no SAP SD. Documento que inicia o ciclo comercial.",
   "SALESORDERITEM": "Número do item dentro da ordem de venda. Junto de SALESORDER, identifica unicamente a linha do pedido.",
   "SCHEDULELINE": "Número da linha de programação (schedule line) do item da ordem de venda, que detalha a divisão da quantidade por data de entrega.",
   "PRODUCTAVAILABILITYDATE": "Data de disponibilidade do produto informada na linha de programação (schedule line) da ordem de venda.",
   "__SNAPSHOT_DATE": "Data do snapshot que originou esta versão do registro no histórico SCD Tipo 2.",
   "__LOADED_AT": "Campo técnico de controle: data e hora em que esta versão do registro foi gravada no histórico."
  }
 }
}
""")


def carregar_cliente():
    try:
        from google.cloud import bigquery
    except ImportError:
        print("Biblioteca ausente. Instale com:\n"
              "    pip install google-cloud-bigquery", file=sys.stderr)
        raise SystemExit(2)

    try:
        return bigquery, bigquery.Client(project=PROJECT)
    except Exception as e:
        print("Não foi possível autenticar na API do BigQuery.\n"
              "Rode uma vez:\n"
              "    gcloud auth application-default login\n"
              "ou aponte uma conta de serviço em GOOGLE_APPLICATION_CREDENTIALS.\n\n"
              f"Detalhe: {e}", file=sys.stderr)
        raise SystemExit(2)


def casar(schema, info):
    """Devolve (novo_schema, aplicadas, ausentes) com as descrições anotadas."""
    from google.cloud import bigquery

    novo, aplicadas, ausentes = [], 0, []
    for campo in schema:
        desc = info["colunas"].get(campo.name)
        if desc is None:
            for k, v in info["colunas"].items():
                if k.lower() == campo.name.lower():
                    desc = v
                    break
        if desc is None:
            ausentes.append(campo.name)
            novo.append(campo)
        else:
            aplicadas += 1
            novo.append(bigquery.SchemaField(
                name=campo.name,
                field_type=campo.field_type,
                mode=campo.mode,
                description=desc,
                fields=campo.fields,
            ))
    return novo, aplicadas, ausentes


def salvar_backup(nome, consulta):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    caminho = os.path.join(BACKUP_DIR, nome + ".sql")
    with io.open(caminho, "w", encoding="utf-8") as f:
        f.write("-- Definição original de %s.%s.%s\n" % (PROJECT, DATASET, nome))
        f.write("-- Salva em %s\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        f.write("CREATE OR REPLACE VIEW `%s.%s.%s` AS\n" % (PROJECT, DATASET, nome))
        f.write(consulta.rstrip().rstrip(";") + ";\n")
    return caminho


def literal_sql(texto):
    """Literal SQL do BigQuery. Escapa barra e aspa simples."""
    return "'" + texto.replace("\\", "\\\\").replace("'", "\\'") + "'"


def recriar_view(client, nome, schema, info, view_query):
    colunas = ",\n".join(
        "  `%s` OPTIONS (description = %s)" % (c.name, literal_sql(c.description))
        for c in schema if c.description
    )
    ddl = (
        "CREATE OR REPLACE VIEW `%s.%s.%s`\n(\n%s\n)\n"
        "OPTIONS (description = %s)\nAS\n%s"
        % (PROJECT, DATASET, nome, colunas,
           literal_sql(info["descricao"]), view_query.rstrip().rstrip(";"))
    )
    client.query(ddl).result()


def aplicar(bigquery, client, nome, info, dry_run, recriar_views):
    ref = "%s.%s.%s" % (PROJECT, DATASET, nome)
    obj = client.get_table(ref)
    tipo = obj.table_type or "TABLE"

    novo_schema, aplicadas, ausentes = casar(obj.schema, info)
    extras = set(info["colunas"]) - {c.name for c in obj.schema}

    status = "  %-33s %-17s %3d/%d colunas" % (nome, tipo, aplicadas, len(obj.schema))
    if ausentes:
        status += " | sem descrição: " + ", ".join(ausentes)
    if extras:
        status += " | no dicionário mas não no objeto: " + ", ".join(sorted(extras))

    if dry_run:
        if tipo == "VIEW" and not recriar_views:
            status += " | VIEW: colunas exigem --recriar-views"
        elif tipo == "MATERIALIZED_VIEW":
            status += " | MATERIALIZED VIEW: só a descrição do objeto"
        print(status)
        return

    obj.description = info["descricao"]

    if tipo == "VIEW":
        client.update_table(obj, ["description"])
        if recriar_views:
            caminho = salvar_backup(nome, obj.view_query)
            recriar_view(client, nome, novo_schema, info, obj.view_query)
            status += " | view recriada (backup em %s)" % caminho
        else:
            status += " | descrição da view aplicada; colunas exigem --recriar-views"
    elif tipo == "MATERIALIZED_VIEW":
        client.update_table(obj, ["description"])
        status += " | materialized view: colunas não suportadas pelo BigQuery"
    else:
        obj.schema = novo_schema
        client.update_table(obj, ["description", "schema"])

    print(status)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="apenas mostra o que seria alterado")
    p.add_argument("--tabela", help="aplica somente em uma tabela ou view")
    p.add_argument("--recriar-views", action="store_true",
                   help="recria as views para gravar as descrições das colunas")
    args = p.parse_args()

    bigquery, client = carregar_cliente()

    alvos = {args.tabela: DESCRICOES[args.tabela]} if args.tabela else DESCRICOES
    modo = "SIMULAÇÃO (nada será alterado)" if args.dry_run else "APLICANDO"
    print("%s — %s.%s — %d objeto(s)" % (modo, PROJECT, DATASET, len(alvos)))
    if not args.recriar_views:
        vistas = [v for v in VIEWS_CONHECIDAS if v in alvos]
        if vistas:
            print("Views no lote (%s): recebem so a descricao do objeto.\n"
                  "As descricoes das colunas exigem --recriar-views.\n"
                  % ", ".join(vistas))
        else:
            print("")
    else:
        print("")

    erros = 0
    for nome, info in alvos.items():
        try:
            aplicar(bigquery, client, nome, info, args.dry_run, args.recriar_views)
        except Exception as e:
            erros += 1
            print("  %-33s ERRO: %s" % (nome, e), file=sys.stderr)

    print("\nConcluído. %d objeto(s) sem erro, %d com erro." % (len(alvos) - erros, erros))
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
