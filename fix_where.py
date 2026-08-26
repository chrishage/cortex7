import os, glob, re

js_files = glob.glob('src/data_modules/custom_tramontina/sap/products/*/definitions/*.js')
for jf in js_files:
    if 'nota_fiscal' in jf or 'customers_ext' in jf or 'sales_documents_ext' in jf:
        continue
        
    with open(jf, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex to find the pattern:
    # ])}
    # AND (.*mandt = '400')
    # and replace with
    #   , "GROUP_1"
    # ])}
    
    # Let's match it precisely
    def replacer(match):
        alias_mandt = match.group(1).strip()
        return f', "{alias_mandt}"\n])}}'

    new_content = re.sub(r'\]\)\}\s*AND\s+(.*?mandt = \'400\')', replacer, content)
    
    with open(jf, 'w', encoding='utf-8') as f:
        f.write(new_content)

print('Done fixing WHERE clause syntax.')
