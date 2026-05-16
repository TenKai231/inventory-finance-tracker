import glob
import re

replacements = {
    r'href="#"\s*>\s*<span class="material-symbols-outlined">receipt_long</span>\s*<span class="font-label-md">Transaksi</span>': r'href="{{ url_for(\'ui.transactions\') }}">\n                <span class="material-symbols-outlined">receipt_long</span>\n                <span class="font-label-md">Transaksi</span>',
    r'href="#"\s*>\s*<span class="material-symbols-outlined">payments</span>\s*<span class="font-label-md">Keuangan</span>': r'href="{{ url_for(\'ui.finance_page\') }}">\n                <span class="material-symbols-outlined">payments</span>\n                <span class="font-label-md">Keuangan</span>',
    r'href="#"\s*>\s*<span class="material-symbols-outlined">ios_share</span>\s*<span class="font-label-md">Ekspor</span>': r'href="{{ url_for(\'ui.export_page\') }}">\n                <span class="material-symbols-outlined">ios_share</span>\n                <span class="font-label-md">Ekspor</span>',
    r'href="#"\s*>\s*<span class="material-symbols-outlined">settings</span>\s*<span class="font-label-md">Pengaturan</span>': r'href="{{ url_for(\'ui.settings_page\') }}">\n                <span class="material-symbols-outlined">settings</span>\n                <span class="font-label-md">Pengaturan</span>'
}

html_files = glob.glob('/mnt/DATA/proyek/inventory-finance-tracker/templates/*.html')
for file_path in html_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    for pattern, replacement in replacements.items():
        content = re.sub(pattern, replacement, content)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {file_path}")
