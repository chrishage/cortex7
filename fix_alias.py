import os, glob, re

js_files = glob.glob('src/data_modules/custom_tramontina/sap/products/*/definitions/*.js')
for jf in js_files:
    if 'nota_fiscal' in jf or 'customers_ext' in jf or 'sales_documents_ext' in jf or 'incoterms' in jf:
        continue
        
    with open(jf, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex to find: FROM ${ctx.ref(moduleConfig.sources.sapRaw.datasetId, "tablename")}
    # and append AS tablename if not already there
    
    def replacer(match):
        table_name = match.group(1)
        # Avoid double 'AS' if it was already run
        full_match = match.group(0)
        return f'{full_match} AS {table_name}'
        
    # Negative lookahead to ensure we don't add "AS" if it's already there
    new_content = re.sub(r'(FROM \$\{ctx\.ref\([^,]+,\s*"([^"]+)"\)\})(?!\s+AS)', replacer, content)
    
    with open(jf, 'w', encoding='utf-8') as f:
        f.write(new_content)

print('Done fixing FROM alias.')
