#!/usr/bin/env python3
"""
apply_iceberg_settings.py — injeta o bloco bigquery.iceberg em cada tabela dos
table_settings dos produtos Cortex, preservando comentários e formatação (ruamel.yaml).

USO:
  pip install ruamel.yaml
  python apply_iceberg_settings.py --src src [--sections s4 ecc] [--dry-run]

Para cada table_settings*.yaml dos produtos em PRODUCTS, e para cada seção
(s4/ecc), adiciona em cada tabela:
    bigquery:
      iceberg:
        connection: "<CONNECTION>"
        bucketName: "<BUCKET>"
        fileFormat: "PARQUET"

Idempotente: se a tabela já tem bigquery.iceberg, pula.
Se já existe um 'bigquery' (ex.: labels), faz merge (adiciona iceberg dentro).
"""
import argparse, sys
from pathlib import Path
try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
except ImportError:
    print("ERRO: instale ruamel.yaml -> pip install ruamel.yaml")
    sys.exit(1)

PRODUCTS = [
    "customers", "materials", "business_partners", "global_settings",
    "material_batches", "sales_documents", "billing_documents",
    "delivery_documents", "universal_journal", "accounts_receivable",
    "materials_movement",
]

CONNECTION = "tra-prd-cortex-aecorsoft.US.cortex_iceberg_conn"
BUCKET     = "tra-cortex-iceberg-dev"
FILEFORMAT = "PARQUET"

def make_iceberg_block():
    ice = CommentedMap()
    ice["connection"] = CONNECTION
    ice["bucketName"] = BUCKET
    ice["fileFormat"] = FILEFORMAT
    bq = CommentedMap()
    bq["iceberg"] = ice
    return bq

def process_file(path: Path, sections, dry_run):
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    data = yaml.load(path.read_text(encoding="utf-8"))
    if data is None:
        return 0
    added = 0
    for sec in sections:
        if sec not in data or data[sec] is None:
            continue
        for tbl_name, tbl_cfg in data[sec].items():
            if not isinstance(tbl_cfg, dict):
                continue
            existing_bq = tbl_cfg.get("bigquery")
            if isinstance(existing_bq, dict) and "iceberg" in existing_bq:
                continue  # já tem
            ice = CommentedMap()
            ice["connection"] = CONNECTION
            ice["bucketName"] = BUCKET
            ice["fileFormat"] = FILEFORMAT
            if isinstance(existing_bq, dict):
                existing_bq["iceberg"] = ice  # merge no bigquery existente
            else:
                bq = CommentedMap()
                bq["iceberg"] = ice
                # inserir 'bigquery' logo após materializationType, se existir
                tbl_cfg["bigquery"] = bq
            added += 1
    if added and not dry_run:
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(data, f)
    return added

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--sections", nargs="+", default=["s4"],
                    help="seções a alterar (default: s4). Use: --sections s4 ecc")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = Path(args.src) / "data_modules" / "cortex" / "sap" / "products"
    if not base.exists():
        print(f"ERRO: {base} não existe"); sys.exit(1)

    total = 0
    for prod in PRODUCTS:
        pdir = base / prod
        if not pdir.exists():
            print(f"aviso: {prod} não encontrado"); continue
        for ts in pdir.glob("table_settings*.yaml"):
            n = process_file(ts, args.sections, args.dry_run)
            total += n
            print(f"  {'[dry] ' if args.dry_run else ''}{ts}: +{n} tabela(s) com iceberg")
    print(f"\nTotal de tabelas com bloco iceberg adicionado: {total}")
    print(f"Seções processadas: {args.sections}")
    if args.dry_run:
        print("(DRY-RUN — nada foi salvo)")

if __name__ == "__main__":
    main()
