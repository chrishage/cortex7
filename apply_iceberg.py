#!/usr/bin/env python3
"""
apply_iceberg.py — aplica o wrapper iceberg_helper.publishProduct() nos arquivos
.js dos produtos Cortex, e injeta o bloco bigquery.iceberg no table_settings.

USO:
  python apply_iceberg.py --src <caminho_src> [--dry-run]

O script:
  1. Para cada .js de produto (em sap/products/<produto>/definitions/**),
     que ainda usa publish(...).query(...):
       - adiciona: const iceberg_helper = require("includes/iceberg_helper.js");
       - troca:    publish(NOME, publishConfig).query(
         por:      iceberg_helper.publishProduct(\n  NOME,\n  publishConfig,\n  tableConfig,
  2. NÃO altera table_settings automaticamente (indentação varia) — apenas
     LISTA os table_settings a editar e o bloco a inserir.

Idempotente: se o arquivo já tem iceberg_helper, pula.
"""
import argparse, re, sys
from pathlib import Path

# Produtos a converter (ajuste conforme necessário)
PRODUCTS = [
    "customers", "materials", "business_partners", "global_settings",
    "material_batches", "sales_documents", "billing_documents",
    "delivery_documents", "universal_journal", "accounts_receivable",
    "materials_movement",
]

REQUIRE_LINE = 'const iceberg_helper = require("includes/iceberg_helper.js");'

def transform_js(text: str) -> tuple[str, bool]:
    if "iceberg_helper" in text:
        return text, False  # já aplicado

    # 1. adicionar o require após o sql_helper require
    m = re.search(r'(const\s+sql_helper\s*=\s*require\("includes/sql_helper\.js"\);)', text)
    if m:
        text = text[:m.end()] + "\n" + REQUIRE_LINE + text[m.end():]
    else:
        # fallback: após qualquer require de publish_config
        m = re.search(r'(const\s+publish_config\s*=\s*require\([^)]+\);)', text)
        if not m:
            return text, False
        text = text[:m.end()] + "\n" + REQUIRE_LINE + text[m.end():]

    # 2. trocar publish(<args>).query(  por  iceberg_helper.publishProduct(<args>, tableConfig,
    # captura: publish(  <NAME>  ,  publishConfig  ).query(
    pattern = re.compile(
        r'publish\(\s*(?P<name>[^,]+?)\s*,\s*(?P<cfg>[A-Za-z_][\w]*)\s*\)\s*\.query\(',
        re.DOTALL)
    def repl(mm):
        name = mm.group("name").strip()
        cfg = mm.group("cfg").strip()
        return (f"iceberg_helper.publishProduct(\n"
                f"  {name},\n"
                f"  {cfg},\n"
                f"  tableConfig,")
    new_text, n = pattern.subn(repl, text)
    if n == 0:
        return text, False
    return new_text, True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="caminho para src/ (ex: C:/git/.../src)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = Path(args.src)
    base = src / "data_modules" / "cortex" / "sap" / "products"
    if not base.exists():
        print(f"ERRO: {base} não existe"); sys.exit(1)

    changed, skipped, settings_todo = [], [], []
    for prod in PRODUCTS:
        pdir = base / prod / "definitions"
        if not pdir.exists():
            print(f"aviso: produto {prod} não encontrado"); continue
        # .js em definitions e s4 (ignorar ecc)
        for js in pdir.rglob("*.js"):
            if "/ecc/" in js.as_posix() or "\\ecc\\" in str(js):
                continue
            txt = js.read_text(encoding="utf-8")
            new, did = transform_js(txt)
            if did:
                changed.append(js)
                if not args.dry_run:
                    js.write_text(new, encoding="utf-8")
            else:
                skipped.append(js)
        # registrar o table_settings do produto
        for ts in (base / prod).glob("table_settings*.yaml"):
            settings_todo.append(ts)

    print(f"\n=== RESULTADO {'(DRY-RUN)' if args.dry_run else ''} ===")
    print(f"Arquivos .js transformados: {len(changed)}")
    for c in changed: print(f"  ✓ {c}")
    print(f"\nArquivos pulados (já aplicados ou sem publish): {len(skipped)}")
    print(f"\n=== TABLE_SETTINGS a editar manualmente (adicionar bloco iceberg) ===")
    for ts in sorted(set(settings_todo)):
        print(f"  {ts}")
    print(f"""
Bloco iceberg a adicionar em cada tabela do table_settings (sob s4:), no MESMO
nível de materializationType:
    bigquery:
      iceberg:
        connection: "tra-prd-cortex-aecorsoft.US.cortex_iceberg_conn"
        bucketName: "tra-cortex-iceberg-dev"
        fileFormat: "PARQUET"
""")

if __name__ == "__main__":
    main()
