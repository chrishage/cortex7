#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confere cada coluna descrita no script contra o esquema real de producao.
Uma coluna inexistente derruba o ALTER inteiro do objeto."""
import csv, io, re, json, sys

script_path, csv_path = sys.argv[1], sys.argv[2]

# esquema real
prod = {}
with io.open(csv_path, encoding='utf-8-sig', newline='') as fh:
    for row in csv.DictReader(fh):
        prod.setdefault(row['table_name'], []).append(row['column_name'])

# descricoes do script
s = io.open(script_path, encoding='utf-8').read()
m = re.search(r'DESCRICOES = json\.loads\(r"""(.*?)"""\)', s, re.S)
desc = json.loads(m.group(1))

print('objetos no script: %d | tabelas em prod: %d\n' % (len(desc), len(prod)))

problemas = 0
for nome in sorted(desc):
    if nome not in prod:
        print('[FALTA EM PROD] %s' % nome)
        problemas += 1
        continue
    reais = prod[nome]
    descritas = list(desc[nome].get('colunas', {}))
    fantasma = [c for c in descritas if c not in reais]
    sem_desc = [c for c in reais if c not in descritas]
    if fantasma or sem_desc:
        print('%s  (%d colunas em prod, %d descritas)' % (nome, len(reais), len(descritas)))
        if fantasma:
            print('   ERRO  descrita mas NAO existe: %s' % ', '.join(fantasma))
            problemas += 1
        if sem_desc:
            print('   falta descricao: %s' % ', '.join(sem_desc))

print('\n%s' % ('OK - nenhuma coluna fantasma' if problemas == 0
                else '%d objeto(s) com problema bloqueante' % problemas))
