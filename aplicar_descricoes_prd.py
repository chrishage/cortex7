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

PROJECT = "tra-prd-cortex"
DATASET = "data_consumption"
BACKUP_DIR = "backup_views"

# Confirmado via `bq ls`: apenas estes tres objetos sao views. Usado so para
# avisar no inicio da execucao; o tipo real e sempre lido da API.
VIEWS_CONHECIDAS = []  # confirmado via `bq ls`: os 13 objetos sao tabelas

DESCRICOES = json.loads(r"""
{
 "dim_fatura": {
  "descricao": "Dimensão de cabeçalho dos documentos de faturamento (SAP SD — Billing Document). Um registro por documento de fatura por empresa, com dados da organização de vendas, do pagador, condições de pagamento, Incoterms, valores totais e status. Granularidade: BILLINGDOCUMENT + COMPANYCODE (campo CompositeKey).",
  "colunas": {
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "SDDOCUMENTCATEGORY": "Categoria do documento SD, que classifica o tipo de documento no fluxo de vendas (ordem, remessa, fatura, entre outros).",
   "BILLINGDOCUMENTCATEGORY": "Categoria do documento de faturamento, que distingue fatura, nota de crédito, nota de débito e demais tipos.",
   "BILLINGDOCUMENTTYPE": "Código do tipo de documento de faturamento, que define o comportamento contábil e fiscal da fatura.",
   "BILLINGDOCUMENTTYPENAME": "Descrição textual do tipo de documento de faturamento.",
   "CREATIONDATE": "Data de criação do documento no SAP.",
   "SALESORGANIZATION": "Código da organização de vendas responsável pelo documento. Define a unidade comercial que responde pela venda no SAP.",
   "DISTRIBUTIONCHANNEL": "Código do canal de distribuição pelo qual o produto chega ao cliente (por exemplo venda direta ou distribuidor).",
   "DISTRIBUTIONCHANNELNAME": "Descrição textual do canal de distribuição.",
   "DIVISION": "Código da divisão de produtos à qual o documento está associado.",
   "DIVISIONNAME": "Descrição textual da divisão de produtos.",
   "BILLINGDOCUMENTDATE": "Data do documento de faturamento, utilizada como data de competência do faturamento.",
   "BILLINGDOCUMENTISCANCELLED": "Indica se o documento de faturamento foi cancelado. Documentos cancelados não devem compor o faturamento.",
   "TOTALNETAMOUNT": "Valor líquido total do documento, somando todos os itens antes dos impostos.",
   "TOTALTAXAMOUNT": "Valor total dos impostos incidentes sobre o documento.",
   "TRANSACTIONCURRENCY": "Moeda em que a transação foi registrada, no padrão ISO de três letras.",
   "PRICELISTTYPE": "Tipo de lista de preços aplicada ao documento, que determina a tabela de preços utilizada.",
   "TAXDEPARTURECOUNTRY": "País de partida considerado para a apuração tributária da operação.",
   "INCOTERMSCLASSIFICATION": "Classificação dos Incoterms acordada, que define a divisão de responsabilidades e custos de transporte entre vendedor e comprador.",
   "INCOTERMSCLASSIFICATIONNAME": "Descrição textual da classificação dos Incoterms.",
   "PAYERPARTY": "Código do parceiro responsável pelo pagamento da fatura (payer).",
   "CUSTOMERPAYMENTTERMS": "Código das condições de pagamento acordadas com o cliente, que definem prazo e forma de quitação.",
   "CUSTOMERPAYMENTTERMSNAME": "Descrição textual das condições de pagamento do cliente.",
   "SDPRICINGPROCEDURE": "Procedimento de precificação SD aplicado ao documento, que determina o conjunto de condições de preço utilizadas.",
   "FISCALYEAR": "Ano fiscal ao qual o documento foi atribuído na contabilidade.",
   "DOCUMENTREFERENCEID": "Identificador do documento de referência externo associado ao faturamento.",
   "COUNTRY": "País associado ao endereço do parceiro do documento.",
   "REGION": "Região ou unidade federativa associada ao endereço do parceiro do documento.",
   "SALESDISTRICT": "Código do distrito de vendas, usado para segmentação geográfica da carteira comercial.",
   "INVOICELISTTYPE": "Tipo da lista de faturas usada para agrupar documentos em uma cobrança consolidada.",
   "COMPANYCODE": "Código da empresa (company code) no SAP, unidade contábil independente à qual o documento pertence.",
   "COMPOSITEKEY": "Chave composta para ligar a tabela (BILLINGDOCUMENT-COMPANYCODE)."
  }
 },
 "dim_nota_fiscal": {
  "descricao": "Dimensão de cabeçalho das notas fiscais brasileiras (SAP Localização Brasil — J_1BNFDOC, com dados da NF-e vindos de BR_NOTA_FISCAL_ACTIVE). Restrita à empresa 1407. Reúne numeração, série, modelo, protocolo de autorização e situação de cancelamento. Granularidade: BR_NOTAFISCAL + COMPANY_CODE (campo CompositeKey).",
  "colunas": {
   "BR_NOTAFISCAL": "Número oficial da nota fiscal emitida, conforme a numeração fiscal brasileira.",
   "NOTA_FISCAL_TYPE": "Código do tipo da nota fiscal, que classifica a operação fiscal (venda, devolução, remessa, entre outras).",
   "DOCUMENT_DATE": "Data de emissão do documento fiscal.",
   "MODEL_OF_NOTA_FISCAL": "Modelo do documento fiscal conforme a legislação brasileira (por exemplo 55 para NF-e).",
   "SERIES": "Série da nota fiscal, usada junto do número para identificar o documento perante a SEFAZ.",
   "SD_DOCUMENT_CURRENCY": "Moeda do documento de vendas que originou a nota fiscal, no padrão ISO de três letras.",
   "COMPANY_CODE": "Código da empresa (company code) no SAP. Esta tabela é restrita à empresa 1407.",
   "BR_NFEDOCUMENTSTATUS": "Status da NF-e no processo de autorização junto à SEFAZ.",
   "BR_NFENUMBER": "Número da NF-e atribuído na emissão do documento eletrônico.",
   "BR_NFESERIES": "Série da NF-e atribuída na emissão do documento eletrônico.",
   "BR_NFERANDOMNUMBER": "Código numérico aleatório que compõe a chave de acesso da NF-e.",
   "BR_NFECHECKDIGIT": "Dígito verificador da chave de acesso da NF-e.",
   "BR_NFAUTHZNPROTOCOLNUMBER": "Número do protocolo de autorização devolvido pela SEFAZ na aprovação da NF-e.",
   "BR_NFENVIRONMENTTYPE": "Ambiente de emissão da NF-e: produção ou homologação.",
   "BR_NFAUTHENTICATIONDATE": "Data e hora em que a SEFAZ autorizou a NF-e.",
   "REGION": "Região ou unidade federativa associada ao endereço do parceiro do documento.",
   "BR_NFEMODEL": "Modelo do documento eletrônico emitido, conforme a tabela da SEFAZ.",
   "BR_NFISCANCELED": "Indica se a nota fiscal foi cancelada perante a SEFAZ.",
   "ISSUINGTYPE": "Tipo de emissão da NF-e, que indica o modo de autorização usado (normal, contingência ou demais formas previstas pela SEFAZ).",
   "CompositeKey": "Chave composta que identifica unicamente o registro, formada pela concatenação dos campos-chave do documento."
  }
 },
 "dim_ordem_de_venda": {
  "descricao": "Dimensão de cabeçalho das ordens de venda (SAP SD — Sales Order). Reúne dados comerciais, organizacionais, do cliente, condições de pagamento e datas de entrega solicitadas. Granularidade: SALESORDER (um registro por ordem de venda).",
  "colunas": {
   "SALESORDER": "Número da ordem de venda (pedido) no SAP SD. Documento que inicia o ciclo comercial.",
   "SALESORDERTYPE": "Código do tipo da ordem de venda, que define as regras de processamento do pedido (venda normal, bonificação, exportação, entre outros).",
   "SALESORDERTYPENAME": "Descrição textual do tipo da ordem de venda.",
   "CREATIONDATE": "Data de criação do documento no SAP.",
   "CREATIONTIME": "Hora de criação do documento no SAP.",
   "REQUESTEDDELIVERYDATE": "Data de requisição de entrega (Data de Previsão de Remessa do cabeçalho).",
   "SALESORGANIZATION": "Código da organização de vendas responsável pelo documento. Define a unidade comercial que responde pela venda no SAP.",
   "SALESORGANIZATIONNAME": "Descrição textual da organização de vendas.",
   "DISTRIBUTIONCHANNEL": "Código do canal de distribuição pelo qual o produto chega ao cliente (por exemplo venda direta ou distribuidor).",
   "DISTRIBUTIONCHANNELNAME": "Descrição textual do canal de distribuição.",
   "ORGANIZATIONDIVISION": "Código da divisão da organização de vendas, usado para agrupar linhas de produto.",
   "ORGANIZATIONDIVISIONNAME": "Descrição textual da divisão da organização de vendas.",
   "SALESGROUP": "Código do grupo de vendas responsável pelo atendimento comercial do documento.",
   "SALESOFFICE": "Código do escritório de vendas responsável pela região comercial do documento.",
   "SALESDISTRICT": "Código do Distrito de vendas (Região do Brasil que um CD atende.) na ordem de venda.",
   "SALESDISTRICTNAME": "Descrição do Distrito de vendas (Região do Brasil que um CD atende.) na ordem de venda.",
   "SOLDTOPARTY": "Código do cliente emissor da ordem (sold-to party), parceiro que efetua a compra.",
   "SALESORDERDATE": "Data de criação da ordem de venda.",
   "PURCHASEORDERBYCUSTOMER": "Número do pedido de compra informado pelo cliente, usado como referência externa da ordem.",
   "TRANSACTIONCURRENCY": "Moeda em que a transação foi registrada, no padrão ISO de três letras.",
   "PRICEDETNEXCHANGERATE": "Taxa de câmbio usada na determinação do preço do item, aplicada na conversão para a moeda da empresa.",
   "PRICINGDATE": "Data de precificação do item, referência para a determinação de preços e da taxa de câmbio aplicada.",
   "SDPRICINGPROCEDURE": "Procedimento de precificação SD aplicado ao documento, que determina o conjunto de condições de preço utilizadas.",
   "PRICELISTTYPE": "Tipo de lista de preços aplicada ao documento, que determina a tabela de preços utilizada.",
   "SALESORDERCONDITION": "Condição comercial aplicada à ordem de venda.",
   "TOTALNETAMOUNT": "Valor líquido total do documento, somando todos os itens antes dos impostos.",
   "SHIPPINGCONDITION": "Condição de expedição acordada, que define o modal e a forma de transporte.",
   "INCOTERMSCLASSIFICATION": "Classificação dos Incoterms acordada, que define a divisão de responsabilidades e custos de transporte entre vendedor e comprador.",
   "INCOTERMSCLASSIFICATIONNAME": "Descrição textual da classificação dos Incoterms.",
   "CUSTOMERPAYMENTTERMS": "Código das condições de pagamento acordadas com o cliente, que definem prazo e forma de quitação.",
   "CUSTOMERPAYMENTTERMSNAME": "Descrição textual das condições de pagamento do cliente.",
   "OVERALLSDPROCESSSTATUS": "Status geral de processamento do documento no fluxo SD: em aberto, parcialmente processado ou concluído.",
   "OVERALLSDPROCESSSTATUSNAME": "Descrição textual do status geral do processo SD.",
   "OVERALLSDDOCUMENTREJECTIONSTS": "Status geral de rejeição do documento SD.",
   "OVERALLSDDOCUMENTREJECTIONSTSNAME": "Nome do status geral de rejeição do documento SD.",
   "OVERALLDELIVERYSTATUS": "Status geral de entrega do documento: não entregue, parcialmente entregue ou totalmente entregue.",
   "OVERALLDELIVERYSTATUSNAME": "Descrição textual do status geral da entrega."
  }
 },
 "dim_remessa": {
  "descricao": "Dimensão de cabeçalho dos documentos de remessa/entrega (SAP SD — Delivery Document), com dados de expedição, centro fornecedor, transporte e status de picking e de movimentação de mercadoria. Granularidade: DELIVERYDOCUMENT.",
  "colunas": {
   "DELIVERYDOCUMENT": "Número do documento de remessa (entrega) no SAP SD, gerado a partir da ordem de venda para expedição da mercadoria.",
   "SDDOCUMENTCATEGORY": "Categoria do documento SD, que classifica o tipo de documento no fluxo de vendas (ordem, remessa, fatura, entre outros).",
   "DELIVERYDOCUMENTTYPE": "Código do tipo de documento de remessa, que define as regras de expedição aplicadas.",
   "CREATIONDATE": "Data de criação do documento no SAP.",
   "SHIPPINGPOINT": "Código do local de expedição responsável pela saída física da mercadoria.",
   "TRANSPORTATIONPLANNINGDATE": "Data prevista para o planejamento do transporte da remessa.",
   "SHIPPINGPOINTNAME": "Descrição textual do local de expedição.",
   "SALESORGANIZATION": "Código da organização de vendas responsável pelo documento. Define a unidade comercial que responde pela venda no SAP.",
   "SALESORGANIZATIONNAME": "Descrição textual da organização de vendas.",
   "SALESOFFICE": "Código do escritório de vendas responsável pela região comercial do documento.",
   "DELIVERYPRIORITY": "Prioridade de entrega atribuída ao documento, usada para ordenar o atendimento.",
   "WAREHOUSE": "Código do armazém (warehouse) onde a mercadoria é manuseada.",
   "SHIPTOPARTY": "Código do cliente recebedor da mercadoria (ship-to party), parceiro que recebe a entrega.",
   "INCOTERMSCLASSIFICATION": "Classificação dos Incoterms acordada, que define a divisão de responsabilidades e custos de transporte entre vendedor e comprador.",
   "INCOTERMSCLASSIFICATIONNAME": "Descrição textual da classificação dos Incoterms.",
   "PAYMENTGUARANTEEPROCEDURE": "Procedimento de garantia de pagamento aplicado à ordem, que define as exigências de crédito.",
   "DEPRECIATIONPERCENTAGE": "Percentual de depreciação aplicado ao valor do item.",
   "CONTROLLINGAREACURRENCY": "Moeda da área de controle (controlling area), usada na contabilidade gerencial.",
   "OVERALLDELIVRELTDBILLGSTATUS": "Status de faturamento relacionado à remessa, indicando o quanto da entrega já foi faturado.",
   "OVERALLDELIVRELTDBILLGSTATUSNAME": "Descrição do status de faturamento da remessa.",
   "COMPOSITEKEY": "Chave composta que identifica unicamente o registro, formada pela concatenação dos campos-chave do documento."
  }
 },
 "ft_acompanhamento_de_vendas": {
  "descricao": "Fato de acompanhamento diário do ciclo de vendas. Consolida, no nível do item da ordem, o encadeamento ordem → remessa → fatura → nota fiscal, somando a reserva de estoque calculada pelo ATP, o agendamento de transporte e o status do funil (Sankey). É a base analítica principal da área comercial. Granularidade: item da ordem de venda na data de análise.",
  "colunas": {
   "SALESORDER": "Número da ordem de venda (pedido) no SAP SD. Documento que inicia o ciclo comercial.",
   "SALESORDERITEM": "Número do item dentro da ordem de venda. Junto de SALESORDER, identifica unicamente a linha do pedido.",
   "DELIVERYDOCUMENT": "Número do documento de remessa (entrega) no SAP SD, gerado a partir da ordem de venda para expedição da mercadoria.",
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "BR_NOTAFISCAL": "Número oficial da nota fiscal emitida, conforme a numeração fiscal brasileira.",
   "BR_NFENUMBER": "Número da NF-e atribuído na emissão do documento eletrônico.",
   "BR_NFESERIES": "Série da NF-e atribuída na emissão do documento eletrônico.",
   "TRANSPORTATIONFU": "Código da unidade de frete que está relacionado a remessa.",
   "TRANSPORTATIONORDER": "Código da orden de frete que está relacionado a unidade de frete.",
   "DataPrevistaItemOrdem": "Data de previsão para o item dentro da ordem/remessa ser faturado.",
   "AnoMesPrevisaoExpo": "Data de previsão para o item dentro da ordem/remessa ser faturado indicado pelo SIT.",
   "CREATIONDATEDELIVERY": "Data de criação do documento de remessa no SAP.",
   "CREATIONDATESALESORDER": "Data de criação do documento de ordem de venda.",
   "TRANSPORDCREATIONDATE": "Data de criação do documento de transporte.",
   "DATEFIRSTACTION": "Data de primeira atividade da ordem de frete. (Agendamento da remessa ser faturada).",
   "PRICINGDATEORDER": "Data de precificação do documento de ordem de venda.",
   "PRICINGDATEBILLING": "Data de precificação do documento de faturamento.",
   "SALESORDERTYPE": "Código do tipo da ordem de venda, que define as regras de processamento do pedido (venda normal, bonificação, exportação, entre outros).",
   "SALESORDERTYPENAME": "Descrição textual do tipo da ordem de venda.",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "BATCH": "Código do lote (batch) do material, usado para rastreabilidade da mercadoria.",
   "SALESORDERITEMCATEGORY": "Categoria do item da ordem de venda, que define o comportamento do item no fluxo (item normal, bonificação, texto, entre outros).",
   "Moeda": "Sigla da moeda utilizada na transação, no padrão ISO de três letras.",
   "TRANSACTIONCURRENCYPRICE": "Valor da cotação da moeda utilizada na fatura.",
   "TaxaConversaoDolar": "Taxa de conversão para dólar aplicada ao item, obtida na cotação da data de precificação.",
   "StatusRejeitado": "Indica se a ordem de venda foi rejeitada.",
   "DISTRIBUTIONCHANNEL": "Código do canal de distribuição pelo qual o produto chega ao cliente (por exemplo venda direta ou distribuidor).",
   "DISTRIBUTIONCHANNELNAME": "Descrição textual do canal de distribuição.",
   "PRICELISTTYPEORDER": "Código da Lista de preço utilizado na ordem de venda.",
   "PrecoLiquidoEmbalagem": "Preço Liquido da Embalagem.",
   "PrecoFaturaItemOrdem": "Preço com impostos do item dentro da ordem de venda.",
   "PrecoFaturaItemOrdemDolar": "Preço com impostos convertido para dolar dentro da ordem de venda.",
   "QuantidadeEmOrdem": "Quantidade do item ainda em carteira, ou seja, pedida na ordem de venda e não convertida em remessa.",
   "QuantidadeEmRemessa": "Quantidade do item já convertida em documento de remessa e comprometida para expedição.",
   "QuantidadeOriginalRemessa": "Quantidade de produtos na remessa mesmo ja faturado.",
   "QuantidadeReservadaATP": "Quantidade de estoque reservado pelo ATP para gerar remessa de ordem de venda.",
   "PrecoFaturaEmbalagemOrdem": "Preco com impostos da embaalgem do item dentro da ordem de venda.",
   "PrecoLiquidoConvertido": "Preço liquido pela conversão de quantidade do item na ordem de venda.",
   "ValorTotalProdutoOrdem": "Valor total liquido do produto dentro da ordem de venda.",
   "FaturaTotalProdutoOrdem": "Valor total com impostos do produto dentro da ordem de venda.",
   "FaturaTotalProdutoRemessa": "Valor total com impostos do produto dentro da remessa.",
   "ValorMercadoriaBRLAtual": "Valor do item em Mercadoria pela ordem de frete.",
   "FaturaTotalProdutoOrdemDolar": "Valor total com impostos do produto dentro da ordem convertido em dolar.",
   "FaturaTotalProdutoOrdemSit": "Fatura total com impostos do produto convertido pelo dolar do sit.",
   "PrecoLiquidoProdutoUnitario": "Preço liquido do produto na fatura.",
   "ValorTotalOrdem": "Valor liquido total da ordem.",
   "ValorTotalPedidoRemessa": "Valor Total do pedido em remessa.",
   "ValorTotalPedidoFaturado": "Valor Total do pedido faturado.",
   "QuantidadeVendida": "Quantidade total efetivamente vendida e faturada no período.",
   "ValorDevolucao": "Valor de devolução.",
   "QtdeDevolucao": "Quantidade de devolução.",
   "ValorFaturamento": "Valor de faturamento.",
   "QtdeFaturamento": "Quantidade de faturamento.",
   "VOLUMEORDER": "Volume do item na ordem de venda.",
   "ITEMVOLUMEORDER": "Volume do item na ordem de venda.",
   "ITEMNETWEIGHTORDER": "Peso Líquido do item na ordem de venda.",
   "ITEMGROSSWEIGHTORDER": "Peso Bruto do item na ordem de venda.",
   "ITEMWEIGHTUNITORDER": "Unidade de peso do item na ordem de venda.",
   "BILLINGDOCUMENTDATE": "Data do documento de faturamento, utilizada como data de competência do faturamento.",
   "FATURAR": "Indicador que informa se o item deve ou não ser somado no faturamento, conforme a regra apurada no campo RULE.",
   "MERCADO": "Mercado de destino da venda: Interno (mercado nacional) ou Externo (exportação).",
   "SALESGROUP": "Código do grupo de vendas responsável pelo atendimento comercial do documento.",
   "SALESOFFICE": "Código do escritório de vendas responsável pela região comercial do documento.",
   "SALESDISTRICT": "Código do distrito de vendas, usado para segmentação geográfica da carteira comercial.",
   "DELIVERYBLOCKREASON": "Código do motivo de bloqueio de entrega aplicado ao documento, que impede a geração da remessa até a liberação.",
   "REGION": "Região ou unidade federativa associada ao endereço do parceiro do documento.",
   "COUNTRY": "País associado ao endereço do parceiro do documento.",
   "PAYERPARTY": "Código do parceiro responsável pelo pagamento da fatura (payer).",
   "NomeCliente": "Nome fantasia do cliente associado ao documento.",
   "CNPJ": "CNPJ do cliente, no cadastro de parceiros do SAP.",
   "CITYNAME": "Nome da cidade do endereço do cliente.",
   "Faturamento": "Valor de faturamento final da venda.",
   "ValorLiquidoNF": "Valor líquido do item na nota fiscal, antes dos impostos.",
   "ValorBrutoNF": "Valor bruto do item na nota fiscal, incluindo impostos e encargos.",
   "PrecoUnitarioItem": "Preço unitario do item com base no faturamento.",
   "PrecoUnitarioLiquidoItemNF": "Preço unitario do item com base no valor liquido da nota fiscal.",
   "PrecoUnitarioBrutoItemNF": "Preço unitario do item com base no valor bruto da nota fiscal.",
   "SALESGROUPNAME": "Descrição textual do grupo de vendas.",
   "SALESOFFICENAME": "Descrição textual do escritório de vendas.",
   "SALESDISTRICTNAME": "Descrição textual do distrito de vendas.",
   "COUNTRYNAME": "Nome do país do endereço do cliente.",
   "REGIONNAME": "Nome da região ou unidade federativa do endereço do cliente.",
   "REGIONMATRIZNAME": "Nome da região ou unidade federativa da matriz do cliente.",
   "DiasEmOrdem": "Dias em ordem. Diferença entre datas (Data de criação Remessa - Data de criação ordem de venda).",
   "DiasEmOrdemPrevisao": "Dias em previsão de remessa. Diferença entre datas (Data de criação Remessa - Data de previsão de remessa ou divisão da remessa).",
   "DiasEmPlanejamento": "Dias em planejamento. Diferença entre datas (Data de criação ordem de frete - Data de criação remessa).",
   "DiasEmAgendamento": "Dias em agendamento. Diferença entre datas (Data de Fatura - Data de criação de ordem de frete).",
   "TMStatus": "Descrição do Status acomulado na etapa que o item do pedido está no faturamento.",
   "SankeyStatus": "Descrição do status em que parte do sankey a linha se encaixa.",
   "IndicadorPedidoCarteiraMesPassado": "Indicador com 1 ou 0 se o pedido está pendente do Mês passado.",
   "IndicadorPedidoCarteiraMesesAnteriores": "Indicador com 1 ou 0 se o pedido está pendente a mais de um mês.",
   "IndicadorPedidoIncompleto": "Indicador com 1 ou 0 se o pedido está incompleto de estar todo em remessa.",
   "IndicadorPedidoCompleto": "Indicador com 1 ou 0 se o pedido esta completamente faturado, ou se ainda reste itens em remessa ou ordem para concluir.",
   "CodigoFamilia": "Codigo da familia do material, usado para agrupar produtos na analise comercial da carteira.",
   "DescricaoFamilia": "Descricao textual da familia do material.",
   "TipoEstoque": "Classificacao do estoque que atende o item: livre para venda ou especial, quando reservado para uma ordem de venda especifica.",
   "FK_Estoque": "Chave estrangeira para a COMPOSITEKEY da ft_estoque_venda. Liga o item da carteira a posicao de estoque correspondente (material, embalagem e, no estoque especial, a ordem de venda)."
  }
 },
 "ft_atp_carteira": {
  "descricao": "Fato de ATP (Available to Promise) da carteira: simula a alocacao do estoque disponivel entre os itens de ordem em aberto. Os itens sao ranqueados por data de previsao de entrega e numero da ordem, e o estoque e consumido nessa sequencia ate se esgotar. Responde quanto de cada item pode ser prometido hoje. Granularidade: SALESORDER + SALESORDERITEM + MATERIAL + BATCH.",
  "colunas": {
   "Rank": "Ordem de prioridade do item na fila de atendimento do material, calculada por FIFO: primeiro a data de previsao de entrega, depois o numero da ordem de venda. Define quem consome o estoque disponivel primeiro.",
   "SALESORDER": "Numero da ordem de venda no SAP SD.",
   "SALESORDERITEM": "Numero do item dentro da ordem de venda.",
   "MATERIAL": "Codigo do material solicitado no item, sem os zeros a esquerda.",
   "BATCH": "Codigo da embalagem do material atribuida ao atendimento. Vazio quando o estoque nao e controlado por lote.",
   "DELIVERYPRIORITY": "Prioridade de entrega definida no cadastro do cliente ou na ordem, usada como criterio de negocio no sequenciamento.",
   "DataAgendadaRemessa": "Data de disponibilidade do produto prevista nas linhas de programacao da ordem. Base do ordenamento FIFO da fila.",
   "DataHoraCriado": "Data de criacao do registro de ordem considerado na apuracao.",
   "QuantidadeEmOrdem": "Quantidade do item ainda em carteira, sem bloqueio de remessa e nao faturada.",
   "QuantidadeAgendadoRemessa": "Quantidade do item ja programada em remessa.",
   "QuantidadeAtendida": "Quantidade que este item efetivamente recebe do estoque disponivel, apos os itens de prioridade maior consumirem sua parte. Zero quando o estoque se esgota antes de chegar neste item."
  }
 },
 "ft_atp_carteira_sit": {
  "descricao": "Fato de ATP da carteira restrito aos pedidos originados no sistema legado SIT. Mesma mecanica de alocacao da ft_atp_carteira, aplicada ao subconjunto de mercado externo com numeracao SIT. Granularidade: SALESORDER + SALESORDERITEM + MATERIAL + BATCH.",
  "colunas": {
   "Rank": "Ordem de prioridade do item na fila de atendimento do material, calculada por FIFO: primeiro a data de previsao de entrega, depois o numero da ordem de venda. Define quem consome o estoque disponivel primeiro.",
   "SALESORDER": "Numero da ordem de venda no SAP SD.",
   "SALESORDERITEM": "Numero do item dentro da ordem de venda.",
   "MATERIAL": "Codigo do material solicitado no item, sem os zeros a esquerda.",
   "BATCH": "Codigo da embalagem do material atribuida ao atendimento. Vazio quando o estoque nao e controlado por lote.",
   "DELIVERYPRIORITY": "Prioridade de entrega definida no cadastro do cliente ou na ordem, usada como criterio de negocio no sequenciamento.",
   "DataAgendadaRemessa": "Data de disponibilidade do produto prevista nas linhas de programacao da ordem. Base do ordenamento FIFO da fila.",
   "DataHoraCriado": "Data de criacao do registro de ordem considerado na apuracao.",
   "QuantidadeEmOrdem": "Quantidade do item ainda em carteira, sem bloqueio de remessa e nao faturada.",
   "QuantidadeAgendadoRemessa": "Quantidade do item ja programada em remessa.",
   "QuantidadeAtendida": "Quantidade que este item efetivamente recebe do estoque disponivel, apos os itens de prioridade maior consumirem sua parte. Zero quando o estoque se esgota antes de chegar neste item."
  }
 },
 "ft_atp_sap": {
  "descricao": "Fato de ATP calculado sobre os pedidos SAP em aberto, sem bloqueio de remessa e ainda nao faturados. Ranqueia os itens por data de disponibilidade e distribui o estoque livre em ordem de prioridade. Alimenta o acompanhamento de carteira. Granularidade: SALESORDER + SALESORDERITEM + MATERIAL + BATCH.",
  "colunas": {
   "Rank": "Ordem de prioridade do item na fila de atendimento do material, calculada por FIFO: primeiro a data de previsao de entrega, depois o numero da ordem de venda. Define quem consome o estoque disponivel primeiro.",
   "SALESORDER": "Numero da ordem de venda no SAP SD.",
   "SALESORDERITEM": "Numero do item dentro da ordem de venda.",
   "MATERIAL": "Codigo do material solicitado no item, sem os zeros a esquerda.",
   "BATCH": "Codigo da embalagem do material atribuida ao atendimento. Vazio quando o estoque nao e controlado por lote.",
   "DELIVERYPRIORITY": "Prioridade de entrega definida no cadastro do cliente ou na ordem, usada como criterio de negocio no sequenciamento.",
   "DataAgendadaRemessa": "Data de disponibilidade do produto prevista nas linhas de programacao da ordem. Base do ordenamento FIFO da fila.",
   "DataHoraCriado": "Data de criacao do registro de ordem considerado na apuracao.",
   "QuantidadeEmOrdem": "Quantidade do item ainda em carteira, sem bloqueio de remessa e nao faturada.",
   "QuantidadeAgendadoRemessa": "Quantidade do item ja programada em remessa.",
   "QuantidadeAtendida": "Quantidade que este item efetivamente recebe do estoque disponivel, apos os itens de prioridade maior consumirem sua parte. Zero quando o estoque se esgota antes de chegar neste item."
  }
 },
 "ft_atp_sap_completo": {
  "descricao": "Fato de ATP sobre a base completa de pedidos SAP, sem os filtros de bloqueio e faturamento aplicados na ft_atp_sap. Usado para conferencia e analise de cobertura total da carteira. Granularidade: SALESORDER + SALESORDERITEM + MATERIAL + BATCH.",
  "colunas": {
   "Rank": "Ordem de prioridade do item na fila de atendimento do material, calculada por FIFO: primeiro a data de previsao de entrega, depois o numero da ordem de venda. Define quem consome o estoque disponivel primeiro.",
   "SALESORDER": "Numero da ordem de venda no SAP SD.",
   "SALESORDERITEM": "Numero do item dentro da ordem de venda.",
   "MATERIAL": "Codigo do material solicitado no item, sem os zeros a esquerda.",
   "BATCH": "Codigo da embalagem do material atribuida ao atendimento. Vazio quando o estoque nao e controlado por lote.",
   "DELIVERYPRIORITY": "Prioridade de entrega definida no cadastro do cliente ou na ordem, usada como criterio de negocio no sequenciamento.",
   "DataAgendadaRemessa": "Data de disponibilidade do produto prevista nas linhas de programacao da ordem. Base do ordenamento FIFO da fila.",
   "DataHoraCriado": "Data de criacao do registro de ordem considerado na apuracao.",
   "QuantidadeEmOrdem": "Quantidade do item ainda em carteira, sem bloqueio de remessa e nao faturada.",
   "QuantidadeAgendadoRemessa": "Quantidade do item ja programada em remessa.",
   "QuantidadeAtendida": "Quantidade que este item efetivamente recebe do estoque disponivel, apos os itens de prioridade maior consumirem sua parte. Zero quando o estoque se esgota antes de chegar neste item."
  }
 },
 "ft_estoque_venda": {
  "descricao": "Fato com a posicao de estoque disponivel para venda por material. Confronta o estoque total em deposito com a quantidade ja comprometida em remessas emitidas, resultando no saldo efetivamente livre para novos compromissos. Alimenta o calculo de ATP (Available to Promise). Granularidade: MATERIAL + BATCH + SALESORDER (campo COMPOSITEKEY).",
  "colunas": {
   "COMPOSITEKEY": "Composicao de chaves primarias, formada por MATERIAL, BATCH e SALESORDER.",
   "MATERIAL": "Codigo do material em estoque.",
   "BATCH": "Codigo da embalagem do material em estoque.",
   "SALESORDER": "Caso o estoque seja especial, informa o codigo da ordem de venda em que ele esta presente.",
   "EstoqueTotal": "Quantidade total de material em estoque disponivel para utilizacao, porem podem estar reservados para remessas.",
   "QuantidadeEmRemessa": "Quantidade total do material em remessas ja emitidas.",
   "EstoqueDisponivel": "Quantidade total menos a quantidade em remessa do material."
  }
 },
 "ft_itens_fatura": {
  "descricao": "Fato de itens dos documentos de faturamento (SAP SD — Billing Document Item). Inclui valores líquidos, impostos, taxas de conversão, referências à ordem e à remessa, situação de cancelamento e a regra de negócio que define se o item soma no faturamento (campos RULE e FATURAR). Granularidade: BILLINGDOCUMENT + BILLINGDOCUMENTITEM + COMPANYCODE (campo CompositeKey).",
  "colunas": {
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "BILLINGDOCUMENTITEM": "Número do item dentro do documento de faturamento. Junto de BILLINGDOCUMENT, identifica unicamente a linha faturada.",
   "SALESDOCUMENTITEMCATEGORY": "Categoria do item do documento de vendas, que define o comportamento do item no fluxo (item normal, bonificação, texto, entre outros).",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "PRODUCT": "Código do produto conforme o cadastro de produtos do SAP, equivalente ao material.",
   "BILLINGDOCUMENTITEMTEXT": "Texto do item do documento de faturamento.",
   "BATCH": "Código do lote (batch) do material, usado para rastreabilidade da mercadoria.",
   "FaturamentoBrutoBRL": "Valor bruto faturado do item em BRL, antes de deduções.",
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
   "CANCELLEDBILLINGDOCUMENT": "Número do documento de faturamento cancelado ao qual este registro se refere.",
   "BILLINGDOCUMENTISCANCELLED": "Indica se o documento de faturamento foi cancelado. Documentos cancelados não devem compor o faturamento.",
   "BILLINGDOCUMENTISTEMPORARY": "Se a Fatura é Temporaria, marcada com X caso for se não campo é nulo.",
   "OVERALLBILLINGSTATUS": "Status geral de faturamento do documento: não faturado, parcialmente faturado ou totalmente faturado.",
   "OVERALLBILLINGSTATUSNAME": "Descrição textual do status geral de faturamento.",
   "RULE": "Campo que informa a regra definida com o que ocorre com o valor dessa fatura.",
   "FATURAR": "Campo de verdadeiro ou falso que informa se o fatura deve somar ou não.",
   "COMPANYCODE": "Código da empresa (company code) no SAP, unidade contábil independente à qual o documento pertence.",
   "SALESORDERREFERENCE": "Código de referência a sales order document.",
   "SALESORDERITEMREFERENCE": "Código de referência ao item na sales order document.",
   "DELIVERYDOCUMENTREFERENCE": "Código de referência a delivery document.",
   "DELIVERYDOCUMENTITEMREFERENCE": "Código de referência ao item na delivery document.",
   "CompositeKey": "Chave composta que identifica unicamente o registro, formada pela concatenação dos campos-chave do documento.",
   "REMESSA_FK": "Chave estrangeira para os itens de remessa, composta por REFERENCESDDOCUMENT, REFERENCESDDOCUMENTITEM e COMPANYCODE.",
   "FATURA_FK": "Chave estrangeira para a dimensão de faturas, composta por BILLINGDOCUMENT e COMPANYCODE."
  }
 },
 "ft_itens_nota_fiscal": {
  "descricao": "Fato de itens das notas fiscais brasileiras (SAP Localização Brasil — J_1BNFLIN), com quantidade, valores, frete e o vínculo com o item do documento de faturamento que originou a nota. Granularidade: BR_NOTAFISCAL + BR_NOTAFISCALITEM.",
  "colunas": {
   "BR_NOTAFISCAL": "Número oficial da nota fiscal emitida, conforme a numeração fiscal brasileira.",
   "BR_NOTAFISCALITEM": "Número do item dentro da nota fiscal.",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "BATCH": "Código do lote (batch) do material, usado para rastreabilidade da mercadoria.",
   "BASEUNIT": "Unidade de medida base do material, na qual o estoque é controlado.",
   "QUANTITYINBASEUNIT": "Quantidade vendida convertida para a unidade de medida base do material.",
   "NETPRICEAMOUNT": "Preço líquido unitário do item, na moeda da transação.",
   "BR_NFTOTALAMOUNT": "Valor total do item na nota fiscal, incluindo impostos e encargos.",
   "NETVALUEAMOUNT": "Valor líquido do produto na Nota Fiscal.",
   "BR_NFNETFREIGHTAMOUNT": "Valor líquido do frete atribuído ao item da nota fiscal.",
   "BR_NFNETINSURANCEAMOUNT": "Valor líquido do seguro atribuído ao item da nota fiscal.",
   "BR_NFNETOTHEREXPENSESAMOUNT": "Valor líquido de outras despesas acessórias atribuídas ao item da nota fiscal.",
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "BILLINGDOCUMENTITEM": "Número do item dentro do documento de faturamento. Junto de BILLINGDOCUMENT, identifica unicamente a linha faturada.",
   "COMPANYCODE": "Código da empresa (company code) no SAP, unidade contábil independente à qual o documento pertence.",
   "CompositeKey": "Chave composta que identifica unicamente o registro, formada pela concatenação dos campos-chave do documento.",
   "Fatura_fk": "Chave composta para foreign key com fatura (BILLINGDOCUMENT-BILLINGDOCUMENTITEM-COMPANYCODE)."
  }
 },
 "ft_itens_ordem_de_venda": {
  "descricao": "Fato de itens das ordens de venda (SAP SD — Sales Order Item), com quantidades pedidas, preços, condições de moeda, datas previstas e status de processamento do item. Granularidade: SALESORDER + SALESORDERITEM (campo CompositeKey).",
  "colunas": {
   "SALESORDER": "Número da ordem de venda (pedido) no SAP SD. Documento que inicia o ciclo comercial.",
   "SALESORDERITEM": "Número do item dentro da ordem de venda. Junto de SALESORDER, identifica unicamente a linha do pedido.",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "SALESORDERITEMTEXT": "Texto do item da ordem de vendas.",
   "SALESORDERITEMCATEGORY": "Categoria do item da ordem de venda, que define o comportamento do item no fluxo (item normal, bonificação, texto, entre outros).",
   "SALESORDERITEMCATEGORYTEXT": "Descrição textual da categoria do item da ordem de venda.",
   "REQUIREMENTSEGMENT": "Segmento de necessidade (requirement segment) usado na segmentação de estoque e no planejamento de disponibilidade.",
   "CREATIONDATE": "Data de criação do documento no SAP.",
   "PLANT": "Código do centro (plant) onde o material está fisicamente armazenado ou é produzido.",
   "PLANTNAME": "Descrição textual do centro (plant).",
   "STORAGELOCATION": "Código do depósito (storage location) dentro do centro em que o material está armazenado.",
   "STORAGELOCATIONNAME": "Descrição textual do depósito (storage location).",
   "SHIPPINGPOINT": "Código do local de expedição responsável pela saída física da mercadoria.",
   "SHIPPINGPOINTNAME": "Descrição textual do local de expedição.",
   "FaturamentoPrevistoBRL": "Valor previsto de faturamento do item em BRL, calculado sobre a quantidade em carteira e o preço da ordem.",
   "ORDERQUANTITY": "Quantidade solicitada pelo cliente no item da ordem de venda.",
   "CONFDDELIVQTYINORDERQTYUNIT": "Quantidade de entrega confirmada pelo SAP, expressa na unidade de medida da ordem.",
   "ORDERQUANTITYUNIT": "Unidade da quantidade do pedido.",
   "NETAMOUNT": "Valor líquido do item, já descontados abatimentos e antes dos impostos, na moeda da transação.",
   "NETPRICEAMOUNT": "Preço líquido unitário do item, na moeda da transação.",
   "NETPRICEQUANTITY": "Quantidade de conversão do preço liquido do produto.",
   "TAXAMOUNT": "Valor dos impostos incidentes sobre o item.",
   "TRANSACTIONCURRENCY": "Moeda em que a transação foi registrada, no padrão ISO de três letras.",
   "PRICEDETNEXCHANGERATE": "Taxa de câmbio usada na determinação do preço do item, aplicada na conversão para a moeda da empresa.",
   "PRICINGDATE": "Data de precificação do item, referência para a determinação de preços e da taxa de câmbio aplicada.",
   "ITEMVOLUME": "Volume do item.",
   "ITEMNETWEIGHT": "Peso líquido do item.",
   "ITEMGROSSWEIGHT": "Peso bruto do item.",
   "ITEMWEIGHTUNIT": "Unidade de peso do item.",
   "PROFITCENTER": "Centro de lucro ao qual o resultado do item é atribuído na contabilidade gerencial.",
   "SDPROCESSSTATUS": "Status de processamento do item no fluxo SD.",
   "SDDOCUMENTREJECTIONSTATUS": "Status de rejeição do documento SD, que indica se a ordem foi total ou parcialmente rejeitada.",
   "DELIVERYBLOCKREASON": "Informa o código de bloqueio de remessa, caso não houver a ordem de venda está liberada para seguir para remessa.",
   "SDDOCUMENTREASON": "Motivo do documento SD, que justifica a criação da ordem (devolução, bonificação, entre outros).",
   "DELIVERYPRIORITY": "Prioridade de entrega atribuída ao documento, usada para ordenar o atendimento.",
   "COMPANYCODE": "Código da empresa (company code) no SAP, unidade contábil independente à qual o documento pertence.",
   "FKSALESORDER": "Foreign key de conexão a dimensão das ordem de vendas (Cabecalho), (SALESORDER-COMPANYCODE).",
   "CompositeKey": "Chave composta que identifica unicamente o registro, formada pela concatenação dos campos-chave do documento."
  }
 },
 "ft_itens_remessa": {
  "descricao": "Fato de itens dos documentos de remessa (SAP SD — Delivery Document Item), com as quantidades expedidas e a referência ao item da ordem de venda de origem. Granularidade: DELIVERYDOCUMENT + DELIVERYDOCUMENTITEM (campo CompositeKey).",
  "colunas": {
   "DELIVERYDOCUMENT": "Número do documento de remessa (entrega) no SAP SD, gerado a partir da ordem de venda para expedição da mercadoria.",
   "DELIVERYDOCUMENTITEM": "Número do item dentro do documento de remessa. Junto de DELIVERYDOCUMENT, identifica unicamente a linha expedida.",
   "SDDOCUMENTCATEGORY": "Categoria do documento SD, que classifica o tipo de documento no fluxo de vendas (ordem, remessa, fatura, entre outros).",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "DELIVERYDOCUMENTITEMTEXT": "Texto do item do documento de entrega.",
   "BATCH": "Código do lote (batch) do material, usado para rastreabilidade da mercadoria.",
   "DISTRIBUTIONCHANNEL": "Código do canal de distribuição pelo qual o produto chega ao cliente (por exemplo venda direta ou distribuidor).",
   "DIVISION": "Código da divisão de produtos à qual o documento está associado.",
   "SALESGROUP": "Código do grupo de vendas responsável pelo atendimento comercial do documento.",
   "SALESOFFICE": "Código do escritório de vendas responsável pela região comercial do documento.",
   "ACTUALDELIVERYQUANTITY": "Quantidade efetivamente expedida no item da remessa.",
   "ORIGINALDELIVERYQUANTITY": "Quantidade originalmente prevista no item da remessa, antes de eventuais ajustes de expedição.",
   "DELIVERYQUANTITYUNIT": "Unidade da quantidade de entrega.",
   "SDPROCESSSTATUS": "Status de processamento do item no fluxo SD.",
   "REFERENCESDDOCUMENT": "Número do documento SD de referência que originou este registro, normalmente a ordem de venda ou a remessa antecedente.",
   "REFERENCESDDOCUMENTITEM": "Número do item no documento SD de referência que originou este registro.",
   "CompositeKey": "Chave composta que identifica unicamente o registro, formada pela concatenação dos campos-chave do documento.",
   "ORDEM_VENDA_FK": "(REFERENCESDDOCUMENT-REFERENCESDDOCUMENTITEM).",
   "FK_REMESSA": "Chave estrangeira para a dimensão de remessas, formada por DELIVERYDOCUMENT e COMPANYCODE."
  }
 },
 "ft_resumo_carteira_venda": {
  "descricao": "Fato agregado com o histórico da carteira de vendas valorizada, em BRL e em USD. Consolida por dia, mercado e motivo de bloqueio os valores em ordem, em remessa, cobertos por estoque, agendados e já faturados. Acumula a série histórica; a visão do dia corrente fica em ft_resumo_carteira_venda_diario. Granularidade: Dia + MERCADO + CodigoBloqueio.",
  "colunas": {
   "Dia": "Data de referência da apuração da carteira.",
   "ValorEmOrdem": "Valor da carteira em ordem de venda sem bloqueio, ainda não convertida em remessa, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorEmOrdemDolar": "Valor da carteira em ordem de venda sem bloqueio, ainda não convertida em remessa, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorEmOrdemBloqueado": "Valor da carteira em ordem de venda com bloqueio de remessa ZR, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorEmOrdemBloqueadoDolar": "Valor da carteira em ordem de venda com bloqueio de remessa ZR, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorEmRemessa": "Valor da carteira já convertida em documento de remessa, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorEmRemessaDolar": "Valor da carteira já convertida em documento de remessa, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorEstoque": "Valor da carteira coberta por estoque disponível, conforme a quantidade reservada no ATP, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorEstoqueDolar": "Valor da carteira coberta por estoque disponível, conforme a quantidade reservada no ATP, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorNegativo": "Valor da carteira sem cobertura de estoque no mês corrente (estoque negativo do mês atual), em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorNegativoDolar": "Valor da carteira sem cobertura de estoque no mês corrente (estoque negativo do mês atual), em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorNegativoMesPassado": "Valor da carteira sem cobertura de estoque arrastada do mês anterior, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorNegativoMesPassadoDolar": "Valor da carteira sem cobertura de estoque arrastada do mês anterior, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorNegativoMesesAnteriores": "Valor da carteira sem cobertura de estoque arrastada de meses anteriores, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorNegativoMesesAnterioresDolar": "Valor da carteira sem cobertura de estoque arrastada de meses anteriores, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorAgendada": "Valor da carteira com transporte agendado ou já concluído, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorAgendadaDolar": "Valor da carteira com transporte agendado ou já concluído, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorNaoAgendada": "Valor da carteira sem agendamento de transporte, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorNaoAgendadaDolar": "Valor da carteira sem agendamento de transporte, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorAguardandoRestante": "Valor da carteira aguardando o saldo restante do item, apenas em ordens do tipo ZVME, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorAguardandoRestanteDolar": "Valor da carteira aguardando o saldo restante do item, apenas em ordens do tipo ZVME, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorBloqueada": "Valor da carteira com transporte bloqueado, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorBloqueadaDolar": "Valor da carteira com transporte bloqueado, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorAgendadaHoje": "Valor da carteira com transporte agendado para a data de referência, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorAgendadaHojeDolar": "Valor da carteira com transporte agendado para a data de referência, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorAgendadaD1": "Valor da carteira com transporte agendado para o dia seguinte (D+1), em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorAgendadaD1Dolar": "Valor da carteira com transporte agendado para o dia seguinte (D+1), em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorAgendadaDn": "Valor da carteira com transporte agendado para datas posteriores (D+N), em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorAgendadaDnDolar": "Valor da carteira com transporte agendado para datas posteriores (D+N), em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "Faturamento": "Faturamento realizado no mês de análise, em BRL.",
   "FaturamentoDolar": "Faturamento realizado no mês de análise, em USD. Apurado apenas para o mercado externo.",
   "MERCADO": "Mercado de destino da venda: Interno (mercado nacional) ou Externo (exportação).",
   "CodigoBloqueio": "Código do motivo de bloqueio de remessa do item (DELIVERYBLOCKREASON). Assume o valor \"Sem Bloqueio\" quando o item não possui bloqueio."
  }
 },
 "ft_resumo_carteira_venda_diario": {
  "descricao": "Fato agregado com a fotografia diária da carteira de vendas, valorizada em BRL e em USD. Consolida por dia, mercado e motivo de bloqueio os valores em ordem, em remessa, cobertos por estoque, agendados e já faturados, para o mês corrente e para o mês seguinte. A tabela é reprocessada por sobrescrita total (overwrite) a cada execução. Granularidade: Dia + MERCADO + CodigoBloqueio.",
  "colunas": {
   "Dia": "Data de referência da apuração da carteira.",
   "ValorEmOrdem": "Valor da carteira em ordem de venda sem bloqueio, ainda não convertida em remessa, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorEmOrdemDolar": "Valor da carteira em ordem de venda sem bloqueio, ainda não convertida em remessa, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorEmOrdemBloqueado": "Valor da carteira em ordem de venda com bloqueio de remessa ZR, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorEmOrdemBloqueadoDolar": "Valor da carteira em ordem de venda com bloqueio de remessa ZR, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorEmRemessa": "Valor da carteira já convertida em documento de remessa, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorEmRemessaDolar": "Valor da carteira já convertida em documento de remessa, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorEstoque": "Valor da carteira coberta por estoque disponível, conforme a quantidade reservada no ATP, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorEstoqueDolar": "Valor da carteira coberta por estoque disponível, conforme a quantidade reservada no ATP, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorNegativo": "Valor da carteira sem cobertura de estoque no mês corrente (estoque negativo do mês atual), em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorNegativoDolar": "Valor da carteira sem cobertura de estoque no mês corrente (estoque negativo do mês atual), em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorNegativoMesPassado": "Valor da carteira sem cobertura de estoque arrastada do mês anterior, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorNegativoMesPassadoDolar": "Valor da carteira sem cobertura de estoque arrastada do mês anterior, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorNegativoMesesAnteriores": "Valor da carteira sem cobertura de estoque arrastada de meses anteriores, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorNegativoMesesAnterioresDolar": "Valor da carteira sem cobertura de estoque arrastada de meses anteriores, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorAgendada": "Valor da carteira com transporte agendado ou já concluído, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorAgendadaDolar": "Valor da carteira com transporte agendado ou já concluído, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorNaoAgendada": "Valor da carteira sem agendamento de transporte, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorNaoAgendadaDolar": "Valor da carteira sem agendamento de transporte, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorAguardandoRestante": "Valor da carteira aguardando o saldo restante do item, apenas em ordens do tipo ZVME, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorAguardandoRestanteDolar": "Valor da carteira aguardando o saldo restante do item, apenas em ordens do tipo ZVME, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorBloqueada": "Valor da carteira com transporte bloqueado, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorBloqueadaDolar": "Valor da carteira com transporte bloqueado, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorAgendadaHoje": "Valor da carteira com transporte agendado para a data de referência, em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorAgendadaHojeDolar": "Valor da carteira com transporte agendado para a data de referência, em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorAgendadaD1": "Valor da carteira com transporte agendado para o dia seguinte (D+1), em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorAgendadaD1Dolar": "Valor da carteira com transporte agendado para o dia seguinte (D+1), em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "ValorAgendadaDn": "Valor da carteira com transporte agendado para datas posteriores (D+N), em BRL. Calculado pela quantidade correspondente multiplicada pelo preço médio de fatura do item.",
   "ValorAgendadaDnDolar": "Valor da carteira com transporte agendado para datas posteriores (D+N), em USD. Apurado apenas para o mercado externo, usando a cotação do dólar da data de precificação da ordem.",
   "Faturamento": "Faturamento realizado no mês de análise, em BRL.",
   "FaturamentoDolar": "Faturamento realizado no mês de análise, em USD. Apurado apenas para o mercado externo.",
   "MERCADO": "Mercado de destino da venda: Interno (mercado nacional) ou Externo (exportação).",
   "CodigoBloqueio": "Código do motivo de bloqueio de remessa do item (DELIVERYBLOCKREASON). Assume o valor \"Sem Bloqueio\" quando o item não possui bloqueio."
  }
 },
 "obt_resume_sales_department": {
  "descricao": "One Big Table (OBT) resumida da área de vendas: mesma visão de obt_sales_department, porém com os documentos consolidados e apenas os campos necessários à análise comercial, o que reduz o volume e o custo de consulta. Granularidade: item da ordem de venda.",
  "colunas": {
   "SALESORDER": "Número da ordem de venda (pedido) no SAP SD. Documento que inicia o ciclo comercial.",
   "DELIVERYDOCUMENT": "Número do documento de remessa (entrega) no SAP SD, gerado a partir da ordem de venda para expedição da mercadoria.",
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "BR_NOTAFISCAL": "Número oficial da nota fiscal emitida, conforme a numeração fiscal brasileira.",
   "BR_NFENUMBER": "Número da NF-e atribuído na emissão do documento eletrônico.",
   "BR_NFESERIES": "Série da NF-e atribuída na emissão do documento eletrônico.",
   "SALESORDERTYPE": "Código do tipo da ordem de venda, que define as regras de processamento do pedido (venda normal, bonificação, exportação, entre outros).",
   "SALESORDERTYPENAME": "Descrição textual do tipo da ordem de venda.",
   "SALESORDERITEM": "Número do item dentro da ordem de venda. Junto de SALESORDER, identifica unicamente a linha do pedido.",
   "SCHEDULELINE": "Número da linha de programação (schedule line) do item da ordem de venda, que detalha a divisão da quantidade por data de entrega.",
   "MATERIAL": "Código do material (SKU) comercializado, conforme cadastro de materiais do SAP.",
   "BATCH": "Código do lote (batch) do material, usado para rastreabilidade da mercadoria.",
   "SALESORDERITEMCATEGORY": "Categoria do item da ordem de venda, que define o comportamento do item no fluxo (item normal, bonificação, texto, entre outros).",
   "MERCADO": "Mercado de destino da venda: Interno (mercado nacional) ou Externo (exportação).",
   "GLACCOUNT": "Conta contabil de devolução ou faturamento.",
   "DataPrevistaItemOrdem": "Data prevista do item da ordem de venda.",
   "AnoMesPrevisaoExpo": "Data prevista do item da ordem de venda faturar conforme documento de pedido do SIT.",
   "CREATIONDATESALESORDER": "Data de criação da ordem de venda.",
   "CREATIONDATEORDER": "Data de criação da ordem de venda no SAP.",
   "CREATIONTIMEORDER": "Hora de criação da ordem de venda no SAP.",
   "TRANSPORTATIONPLANNINGDATE": "Data prevista para o planejamento do transporte da remessa.",
   "CREATIONDATEDELIVERY": "Data de criação do documento de remessa no SAP.",
   "BILLINGDOCUMENTDATE": "Data do documento de faturamento, utilizada como data de competência do faturamento.",
   "PRICINGDATEORDER": "Data de precificação do documento de ordem de venda.",
   "PRICINGDATEBILLING": "Data de precificação do documento de faturamento.",
   "NETPRICEQUANTITYORDER": "Quantidade correspondente ao valor \"unitario\" do preço líquido da ordem de venda.",
   "Moeda": "Sigla da moeda utilizada na transação, no padrão ISO de três letras.",
   "StatusRejeitado": "Indica se a ordem de venda foi rejeitada.",
   "StatusOrdem": "Status consolidado da ordem de venda no acompanhamento comercial.",
   "DISTRIBUTIONCHANNEL": "Código do canal de distribuição pelo qual o produto chega ao cliente (por exemplo venda direta ou distribuidor).",
   "DISTRIBUTIONCHANNELNAME": "Descrição textual do canal de distribuição.",
   "SALESGROUP": "Código do grupo de vendas responsável pelo atendimento comercial do documento.",
   "SALESOFFICE": "Código do escritório de vendas responsável pela região comercial do documento.",
   "SALESDISTRICT": "Código do distrito de vendas, usado para segmentação geográfica da carteira comercial.",
   "SALESDISTRICTNAME": "Descrição textual do distrito de vendas.",
   "DIVISION": "Divisão, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "DIVISIONNAME": "Nome da Divisão, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "CUSTOMERPAYMENTTERMS": "Condições de Pagamento do Cliente, que pode ser do Pedido de Venda ou Fatura.",
   "CUSTOMERPAYMENTTERMSNAME": "Nome das Condições de Pagamento do Cliente, que pode ser do Pedido de Venda.",
   "INCOTERMSCLASSIFICATION": "Classificação Incoterms, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "INCOTERMSCLASSIFICATIONNAME": "Nome da Classificação Incoterms, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "DELIVERYBLOCKREASON": "Código de motivo para o pedido não estar apto a ser gerado remessa.",
   "SDDOCUMENTREASON": "Motivo do documento SD, que justifica a criação da ordem (devolução, bonificação, entre outros).",
   "DELIVERYPRIORITY": "Prioridade de entrega atribuída ao documento, usada para ordenar o atendimento.",
   "PRICELISTTYPEORDER": "Código da lista de preços usada na ordem de venda.",
   "FATURAR": "Indicador que informa se o item deve ou não ser somado no faturamento, conforme a regra apurada no campo RULE.",
   "PAYERPARTY": "Código do parceiro responsável pelo pagamento da fatura (payer).",
   "NomeCliente": "Nome fantasia do cliente associado ao documento.",
   "CNPJ": "CNPJ do cliente, no cadastro de parceiros do SAP.",
   "CITYNAME": "Nome da cidade do endereço do cliente.",
   "REGION": "Região ou unidade federativa associada ao endereço do parceiro do documento.",
   "REGIONMATRIZ": "Código da região ou unidade federativa da matriz do cliente.",
   "COUNTRY": "País associado ao endereço do parceiro do documento.",
   "PrecoFaturaItemOrdem": "Preço de fatura do item da ordem de venda.",
   "PrecoFaturaItemOrdemDolar": "Preço de fatura do item da ordem de venda em dólar.",
   "QuantidadeEmOrdem": "Quantidade do item ainda em carteira, ou seja, pedida na ordem de venda e não convertida em remessa.",
   "RevisarPedidoItemSistema": "Indicador apurado pelo sistema de que o item do pedido precisa de revisão. CONFIRMAR: campo ainda sem comentario declarado no pipeline.",
   "MotivoRevisaoPedidoItem": "Motivo pelo qual o item do pedido foi marcado para revisão. CONFIRMAR: campo ainda sem comentario declarado no pipeline.",
   "QuantidadeVendida": "Quantidade total efetivamente vendida e faturada no período.",
   "ValorDevolucao": "Valor de devolução.",
   "QtdeDevolucao": "Quantidade de devolução.",
   "ValorFaturamento": "Valor de faturamento.",
   "QtdeFaturamento": "Quantidade de faturamento.",
   "VOLUMEORDER": "Volume da quantidade remanescente na ordem.",
   "ITEMVOLUMEORDER": "Volume do item total na ordem.",
   "ITEMNETWEIGHTORDER": "Peso líquido do item total na ordem.",
   "ITEMGROSSWEIGHTORDER": "Peso bruto do item total na ordem.",
   "ITEMWEIGHTUNITORDER": "Unidade de peso do item total na ordem.",
   "BILLINGPRICE": "Preço do item no documento de fatura.",
   "TRANSACTIONCURRENCYPRICE": "Valor da moeda no documento de fatura.",
   "QuantidadeEmRemessa": "Quantidade do item já convertida em documento de remessa e comprometida para expedição.",
   "QuantidadeOriginalRemessa": "Quantidade de produtos na remessa mesmo ja faturado.",
   "Faturamento": "Valor de faturamento.",
   "ValorLiquidoNF": "Valor líquido do item na nota fiscal, antes dos impostos.",
   "ValorBrutoNF": "Valor bruto do item na nota fiscal, incluindo impostos e encargos.",
   "PrecoUnitarioItem": "Preço unitario do item com base no faturamento.",
   "PrecoUnitarioLiquidoItemNF": "Preço unitario do item com base no valor liquido da nota fiscal.",
   "PrecoUnitarioBrutoItemNF": "Preço unitario do item com base no valor bruto da nota fiscal.",
   "PrecoFaturaEmbalagemOrdem": "Preço de fatura da embalagem da ordem de venda.",
   "ValorTotalProdutoOrdem": "Valor total do produto na ordem de venda.",
   "FaturaTotalProdutoOrdem": "Valor total de fatura do produto na ordem de venda.",
   "FaturaTotalProdutoRemessa": "Valor total de fatura do produto na remessa.",
   "FaturaTotalProdutoOrdemDolar": "Valor total de fatura do produto na ordem de venda em dólar.",
   "FaturaTotalProdutoOrdemSit": "Valor total de fatura do produto com valor do dolar do SIT.",
   "PrecoLiquidoProdutoUnitario": "Preço líquido do produto unitário.",
   "PrecoLiquidoEmbalagem": "Preço líquido da embalagem.",
   "PrecoLiquidoConvertido": "Preço líquido convertido.",
   "ValorTotalOrdem": "Valor total da ordem de venda."
  }
 },
 "obt_sales_department": {
  "descricao": "One Big Table (OBT) completa da área de vendas do SAP: uma linha por item de ordem de venda com ordem, remessa, fatura, nota fiscal, cliente, material e transporte já desnormalizados, dispensando joins no consumo por ferramentas de BI. Granularidade: item da ordem de venda, desdobrada pelos documentos subsequentes.",
  "colunas": {
   "SALESORDER": "Número da ordem de venda (pedido) no SAP SD. Documento que inicia o ciclo comercial.",
   "SALESORDERITEM": "Número do item dentro da ordem de venda. Junto de SALESORDER, identifica unicamente a linha do pedido.",
   "DELIVERYDOCUMENT": "Número do documento de remessa (entrega) no SAP SD, gerado a partir da ordem de venda para expedição da mercadoria.",
   "ITEMUNIQUE": "Item Único, que pode ser o Item do Pedido de Venda, Item da Remessa ou Item da Fatura.",
   "BILLINGDOCUMENT": "Número do documento de faturamento no SAP SD. Chave do cabeçalho da fatura e ligação com os itens faturados.",
   "BILLINGDOCUMENTITEM": "Número do item dentro do documento de faturamento. Junto de BILLINGDOCUMENT, identifica unicamente a linha faturada.",
   "BR_NOTAFISCAL": "Número oficial da nota fiscal emitida, conforme a numeração fiscal brasileira.",
   "BR_NOTAFISCALITEM": "Número do item dentro da nota fiscal.",
   "BR_NFENUMBER": "Número da NF-e atribuído na emissão do documento eletrônico.",
   "BR_NFESERIES": "Série da NF-e atribuída na emissão do documento eletrônico.",
   "SALESORDERTYPE": "Tipo do Pedido de Venda unico, pode ser o Pedido de Venda, remessa ou Fatura.",
   "SALESORDERTYPENAME": "Nome do Tipo do Pedido de Venda unico, pode ser o Pedido de Venda, remessa ou Fatura.",
   "SCHEDULELINE": "Número da linha de programação (schedule line) do item da ordem de venda, que detalha a divisão da quantidade por data de entrega.",
   "SALESDOCUMENTITEMCATEGORY": "Categoria do item do documento de vendas, que define o comportamento do item no fluxo (item normal, bonificação, texto, entre outros).",
   "MATERIALUNIQUE": "Código do Item do Pedido de Venda, remessa ou Fatura.",
   "BATCHUNIQUE": "Embalagem do Item do Pedido de Venda, remessa ou Fatura.",
   "DATEUNIQUE": "Data Única, que pode ser a Data do Documento de Fatura, Data de Criação da Remessa ou Data do Pedido de Venda.",
   "OPERATIONDATE": "Data da Operação, que pode ser a Data do Documento de Fatura ou Data Prevista do Item do Pedido de Venda.",
   "DataPrevistaItemOrdem": "Ano e Mês de previsão do faturamento do item na ordem de venda. (Ano e Mês da primeira situação.).",
   "AnoMesPrevisaoExpo": "Ano e Mês da previsão de faturamento de um item na exportação do SIT.",
   "PAYERPARTY": "Parte Pagadora, que pode ser o Cliente do Pedido de Venda ou do Documento de Fatura.",
   "SALESORGANIZATION": "Organização de Vendas, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "SALESORGANIZATIONNAME": "Nome da Organização de Vendas, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "SHIPPINGPOINT": "Ponto de Expedição, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "SHIPPINGPOINTNAME": "Nome do Ponto de Expedição, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "DIVISION": "Divisão, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "DIVISIONNAME": "Nome da Divisão, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "DISTRIBUTIONCHANNEL": "Canal de Distribuição, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "DISTRIBUTIONCHANNELNAME": "Nome do Canal de Distribuição, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "INCOTERMSCLASSIFICATION": "Classificação Incoterms, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "INCOTERMSCLASSIFICATIONNAME": "Nome da Classificação Incoterms, que pode ser do Pedido de Venda, Remessa ou Fatura.",
   "CUSTOMERPAYMENTTERMS": "Condições de Pagamento do Cliente, que pode ser do Pedido de Venda ou Fatura.",
   "CUSTOMERPAYMENTTERMSNAME": "Nome das Condições de Pagamento do Cliente, que pode ser do Pedido de Venda ou Fatura.",
   "SALESDISTRICT": "Distrito de Vendas, que pode ser do Pedido de Venda ou Fatura.",
   "SALESDISTRICTNAMEORDER": "Nome do Distrito de Vendas, que pode ser do Pedido de Venda ou Fatura.",
   "NOTAQUANTITY": "Quantidade do item registrada na nota fiscal.",
   "NETPRICEAMOUNTNOTA": "Valor Líquido do Produto na Nota Fiscal.",
   "NETVALUEAMOUNTNOTA": "Valor Total Líquido do Produto na Nota Fiscal.",
   "BR_NFTOTALAMOUNT": "Valor total do item na nota fiscal, incluindo impostos e encargos.",
   "BR_NFNETFREIGHTAMOUNT": "Valor líquido do frete atribuído ao item da nota fiscal.",
   "BR_NFNETINSURANCEAMOUNT": "Valor líquido do seguro atribuído ao item da nota fiscal.",
   "BR_NFNETOTHEREXPENSESAMOUNT": "Valor líquido de outras despesas acessórias atribuídas ao item da nota fiscal.",
   "NOTA_FISCAL_TYPE": "Código do tipo da nota fiscal, que classifica a operação fiscal (venda, devolução, remessa, entre outras).",
   "DOCUMENT_DATE": "Data de emissão do documento fiscal.",
   "SERIES": "Série da nota fiscal, usada junto do número para identificar o documento perante a SEFAZ.",
   "BR_NFISCANCELED": "Indica se a nota fiscal foi cancelada perante a SEFAZ.",
   "FaturamentoBrutoBRL": "Valor bruto faturado do item em BRL, antes de deduções.",
   "TOTALAMOUNT": "Valor total da fatura gravada na nota fiscal do SAP.",
   "BILLINGQUANTITY": "Quantidade efetivamente faturada no item, na unidade de medida de faturamento.",
   "BILLINGQUANTITYUNIT": "Unidade de medida em que a quantidade faturada está expressa.",
   "NETAMOUNTBILLING": "Valor Líquido do Faturamento.",
   "TRANSACTIONCURRENCYBILLING": "Moeda da Transação de Faturamento.",
   "ACCOUNTINGEXCHANGERATE": "Taxa de câmbio contábil proveniente do sistema SIT, aplicada na conversão dos valores do item.",
   "TAXAMOUNTBILLING": "Valor de Impostos do Faturamento.",
   "COSTAMOUNTBILLING": "Valor de Custo do Faturamento.",
   "PRICINGDATEBILLING": "Data de Precificação do Faturamento.",
   "CANCELLEDBILLINGDOCUMENT": "Número do documento de faturamento cancelado ao qual este registro se refere.",
   "BILLINGDOCUMENTISCANCELLED": "Indica se o documento de faturamento foi cancelado. Documentos cancelados não devem compor o faturamento.",
   "OVERALLBILLINGSTATUS": "Status geral de faturamento do documento: não faturado, parcialmente faturado ou totalmente faturado.",
   "OVERALLBILLINGSTATUSNAME": "Descrição textual do status geral de faturamento.",
   "RULE": "Regra de negócio aplicada ao item, que determina como o valor da fatura é tratado no cálculo do faturamento.",
   "FATURAR": "Indicador que informa se o item deve ou não ser somado no faturamento, conforme a regra apurada no campo RULE.",
   "SDDOCUMENTCATEGORY": "Categoria do documento SD, que classifica o tipo de documento no fluxo de vendas (ordem, remessa, fatura, entre outros).",
   "BILLINGDOCUMENTCATEGORY": "Categoria do documento de faturamento, que distingue fatura, nota de crédito, nota de débito e demais tipos.",
   "BILLINGDOCUMENTTYPE": "Código do tipo de documento de faturamento, que define o comportamento contábil e fiscal da fatura.",
   "BILLINGDOCUMENTTYPENAME": "Descrição textual do tipo de documento de faturamento.",
   "CREATIONDATE": "Data de criação do documento no SAP.",
   "BILLINGDOCUMENTDATE": "Data do documento de faturamento, utilizada como data de competência do faturamento.",
   "TOTALNETAMOUNTBILLING": "Valor Total Líquido do Faturamento.",
   "TOTALTAXAMOUNTBILLING": "Valor Total de Impostos do Faturamento.",
   "PRICELISTTYPE": "Tipo de lista de preços aplicada ao documento, que determina a tabela de preços utilizada.",
   "TAXDEPARTURECOUNTRY": "País de partida considerado para a apuração tributária da operação.",
   "SDPRICINGPROCEDURE": "Procedimento de precificação SD aplicado ao documento, que determina o conjunto de condições de preço utilizadas.",
   "FISCALYEAR": "Ano fiscal ao qual o documento foi atribuído na contabilidade.",
   "COUNTRY": "País associado ao endereço do parceiro do documento.",
   "REGION": "Região ou unidade federativa associada ao endereço do parceiro do documento.",
   "INVOICELISTTYPE": "Tipo da lista de faturas usada para agrupar documentos em uma cobrança consolidada.",
   "COMPANYCODEBILLING": "Código da Empresa de Faturamento.",
   "DISTRIBUTIONCHANNELDELIVERY": "Canal de Distribuição da Remessa.",
   "DIVISIONDELIVERY": "Divisão da Remessa.",
   "SALESGROUPDELIVERY": "Grupo de Vendas da Remessa.",
   "SALESOFFICEDELIVERY": "Escritório de Vendas da Remessa.",
   "ACTUALDELIVERYQUANTITY": "Quantidade efetivamente expedida no item da remessa.",
   "ORIGINALDELIVERYQUANTITY": "Quantidade originalmente prevista no item da remessa, antes de eventuais ajustes de expedição.",
   "DELIVERYQUANTITYUNIT": "Unidade da Quantidade Entregue.",
   "SDPROCESSSTATUSDELIVERY": "Status do Processo SD da Remessa.",
   "SDDOCUMENTCATEGORYDELIVERY": "Categoria do Documento SD da Remessa.",
   "DELIVERYDOCUMENTTYPE": "Código do tipo de documento de remessa, que define as regras de expedição aplicadas.",
   "TRANSPORTATIONPLANNINGDATE": "Data prevista para o planejamento do transporte da remessa.",
   "CREATIONDATEDELIVERY": "Data de criação do documento de remessa no SAP.",
   "DELIVERYPRIORITY": "Prioridade de entrega atribuída ao documento, usada para ordenar o atendimento.",
   "WAREHOUSEDELIVDELIVERY": "Código do armazém responsável pela remessa.",
   "SHIPTOPARTYDELIVERY": "Destinatário da Remessa.",
   "PAYMENTGUARANTEEPROCEDURE": "Procedimento de garantia de pagamento aplicado à ordem, que define as exigências de crédito.",
   "DEPRECIATIONPERCENTAGE": "Percentual de depreciação aplicado ao valor do item.",
   "CONTROLLINGAREACURRENCY": "Moeda da área de controle (controlling area), usada na contabilidade gerencial.",
   "OVERALLDELIVRELTDBILLGSTATUS": "Status de faturamento relacionado à remessa, indicando o quanto da entrega já foi faturado.",
   "OVERALLDELIVRELTDBILLGSTATUSNAME": "Nome do Status Geral de Faturamento Relacionado à Entrega.",
   "SALESORDERITEMTEXT": "Texto do Item do Pedido de Venda.",
   "SALESORDERITEMCATEGORY": "Categoria do item da ordem de venda, que define o comportamento do item no fluxo (item normal, bonificação, texto, entre outros).",
   "SALESORDERITEMCATEGORYTEXT": "Texto da Categoria do Item do Pedido de Venda.",
   "CREATIONDATESALESORDER": "Data de Criação do Pedido de Venda.",
   "PLANTORDER": "Código do centro (plant) informado na ordem de venda, responsável pelo fornecimento do item.",
   "PLANTNAMEORDER": "Descrição textual do centro (plant) informado na ordem de venda.",
   "STORAGELOCATION": "Código do depósito (storage location) dentro do centro em que o material está armazenado.",
   "STORAGELOCATIONNAME": "Descrição textual do depósito (storage location).",
   "FaturamentoPrevistoBRL": "Valor previsto de faturamento do item em BRL, calculado sobre a quantidade em carteira e o preço da ordem.",
   "ORDERQUANTITY": "Quantidade solicitada pelo cliente no item da ordem de venda.",
   "RevisarPedidoItemSistema": "Indicador apurado pelo sistema de que o item do pedido precisa de revisão. CONFIRMAR: campo ainda sem comentario declarado no pipeline.",
   "MotivoRevisaoPedidoItem": "Motivo pelo qual o item do pedido foi marcado para revisão. CONFIRMAR: campo ainda sem comentario declarado no pipeline.",
   "CONFDDELIVQTYINORDERQTYUNIT": "Quantidade de entrega confirmada pelo SAP, expressa na unidade de medida da ordem.",
   "ORDERQUANTITYUNIT": "Unidade da Quantidade do Pedido.",
   "NETAMOUNTORDER": "Valor Líquido do Pedido de Venda.",
   "NETPRICEAMOUNTORDER": "Valor Líquido do Preço do Pedido de Venda.",
   "NETPRICEQUANTITYORDER": "Quantidade para Preço Líquido do Pedido de Venda.",
   "TAXAMOUNT": "Valor dos impostos incidentes sobre o item.",
   "TRANSACTIONCURRENCYORDER": "Moeda da Transação do Pedido de Venda.",
   "PRICINGDATEORDER": "Data de Precificação do Pedido de Venda.",
   "ITEMVOLUMEORDER": "Volume do Item do Pedido de Venda.",
   "ITEMNETWEIGHTORDER": "Peso Líquido do Item do Pedido de Venda.",
   "ITEMGROSSWEIGHTORDER": "Peso Bruto do Item do Pedido de Venda.",
   "ITEMWEIGHTUNITORDER": "Unidade de Peso do Item do Pedido de Venda.",
   "PROFITCENTERORDER": "Centro de lucro informado na ordem de venda, ao qual o resultado do item é atribuído.",
   "SDPROCESSSTATUSORDER": "Status do Processo SD do Pedido de Venda.",
   "SDDOCUMENTREJECTIONSTATUS": "Status de rejeição do documento SD, que indica se a ordem foi total ou parcialmente rejeitada.",
   "CREATIONDATEORDER": "Data de criação da ordem de venda no SAP.",
   "CREATIONTIMEORDER": "Hora de criação da ordem de venda no SAP.",
   "SALESGROUPORDER": "Grupo de Vendas do Pedido de Venda.",
   "SALESOFFICEORDER": "Escritório de Vendas do Pedido de Venda.",
   "SOLDTOPARTYORDER": "Cliente do Pedido de Venda.",
   "SALESORDERDATE": "Data de criação da ordem de venda.",
   "PURCHASEORDERBYCUSTOMERORDER": "Pedido de Compra do Cliente no Pedido de Venda.",
   "PRICEDETNEXCHANGERATEORDER": "Taxa de Câmbio de Determinação de Preço do Pedido de Venda.",
   "SDPRICINGPROCEDUREORDER": "Procedimento de Precificação SD do Pedido de Venda.",
   "PRICELISTTYPEORDER": "Tipo de Lista de Preço do Pedido de Venda.",
   "SALESORDERCONDITION": "Condição comercial aplicada à ordem de venda.",
   "TOTALNETAMOUNT": "Valor líquido total do documento, somando todos os itens antes dos impostos.",
   "SHIPPINGCONDITION": "Condição de expedição acordada, que define o modal e a forma de transporte.",
   "DELIVERYBLOCKREASON": "Código do motivo de bloqueio de entrega aplicado ao documento, que impede a geração da remessa até a liberação.",
   "SDDOCUMENTREASON": "Motivo do documento SD, que justifica a criação da ordem (devolução, bonificação, entre outros).",
   "DELIVERYPRIORITYORDER": "Prioridade da Entrega do Pedido de Venda.",
   "OVERALLSDPROCESSSTATUS": "Status geral de processamento do documento no fluxo SD: em aberto, parcialmente processado ou concluído.",
   "OVERALLSDPROCESSSTATUSNAME": "Descrição textual do status geral do processo SD.",
   "OVERALLSDDOCUMENTREJECTIONSTS": "Status Geral de Rejeição do Documento SD.",
   "OVERALLSDDOCUMENTREJECTIONSTSNAME": "Nome do Status Geral de Rejeição do Documento SD.",
   "CompositeKey": "Chave composta que junta SALESORDER-SALESORDERITEM-DELIVERYDOCUMENT-BILLINGDOCUMENT-BILLINGDOCUMENTITEM."
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
