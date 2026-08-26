import os, glob, re

# Fix manifest.yaml files
manifest_files = glob.glob('src/data_modules/custom_tramontina/sap/products/*/manifest.yaml')
for mf in manifest_files:
    if 'nota_fiscal' in mf or 'customers_ext' in mf or 'sales_documents_ext' in mf:
        continue
        
    with open(mf, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We want to lowercase any table under `common:`
    def lowercase_tables(match):
        lines = match.group(1).split('\n')
        new_lines = []
        for line in lines:
            if line.strip().startswith('- '):
                new_lines.append(line.lower())
            else:
                new_lines.append(line)
        return 'common:\n' + '\n'.join(new_lines)
        
    new_content = re.sub(r'common:\n(.*?)(?=\n\w|$)', lowercase_tables, content, flags=re.DOTALL)
    
    with open(mf, 'w', encoding='utf-8') as f:
        f.write(new_content)

# Fix .js files
js_files = glob.glob('src/data_modules/custom_tramontina/sap/products/*/definitions/*.js')
for jf in js_files:
    if 'nota_fiscal' in jf or 'customers_ext' in jf or 'sales_documents_ext' in jf:
        continue
        
    with open(jf, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Replace ctx.ref(..., "TABLE") with lowercase "table"
    new_content = re.sub(r'ctx\.ref\([^,]+,\s*"([^"]+)"\)', lambda m: m.group(0).replace(m.group(1), m.group(1).lower()), content)
    # Replace incremental.getFilter(ctx, ["TABLE"]) with lowercase "table"
    new_content = re.sub(r'incremental\.getFilter\([^,]+,\s*\[([^\]]+)\]\)', lambda m: m.group(0).lower(), new_content)
    
    with open(jf, 'w', encoding='utf-8') as f:
        f.write(new_content)

print('Done fixing case.')
