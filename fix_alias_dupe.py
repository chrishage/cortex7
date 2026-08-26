import os, glob, re

js_files = glob.glob('src/data_modules/custom_tramontina/sap/products/*/definitions/*.js')
for jf in js_files:
    if 'nota_fiscal' in jf or 'customers_ext' in jf or 'sales_documents_ext' in jf or 'incoterms' in jf:
        continue
        
    with open(jf, 'r', encoding='utf-8') as f:
        content = f.read()

    # The bad output is something like:
    # FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "tvgrt")} AS FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "tvgrt")}
    # We want to change it to:
    # FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "tvgrt")} AS tvgrt

    def fix_bad(match):
        from_str = match.group(1)
        table_name = match.group(2)
        return f'{from_str} AS {table_name}'

    # Regex to find the duplicate bad AS pattern
    new_content = re.sub(r'(FROM \$\{ctx\.ref\([^,]+,\s*"([^"]+)"\)\})\s+AS\s+FROM \$\{ctx\.ref\([^,]+,\s*"\2"\)\}', fix_bad, content)
    
    with open(jf, 'w', encoding='utf-8') as f:
        f.write(new_content)

print('Done fixing FROM alias duplication.')
