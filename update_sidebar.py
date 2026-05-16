import glob
import os

html_files = glob.glob('templates/*.html')

sidebar_addition = """
            <a class="flex items-center px-4 py-2 space-x-4 rounded-lg text-on-primary-container opacity-70 hover:opacity-100 hover:bg-surface-variant transition-all duration-200 ease-in-out" href="{{ url_for('ui.warehouse_page') }}">
                <span class="material-symbols-outlined">warehouse</span>
                <span class="font-label-md">Gudang</span>
            </a>
            <a class="flex items-center px-4 py-2 space-x-4 rounded-lg text-on-primary-container opacity-70 hover:opacity-100 hover:bg-surface-variant transition-all duration-200 ease-in-out" href="{{ url_for('ui.delivery_page') }}">
                <span class="material-symbols-outlined">local_shipping</span>
                <span class="font-label-md">Pengiriman</span>
            </a>"""

for file in html_files:
    if file in ['templates/warehouse.html', 'templates/delivery.html', 'templates/base.html', 'templates/login.html', 'templates/register.html', 'templates/error.html']:
        continue
        
    with open(file, 'r') as f:
        content = f.read()
        
    if 'ui.warehouse_page' not in content:
        # Cari Inventaris dan sisipkan setelahnya
        target = """<span class="font-label-md">Inventaris</span>
            </a>"""
        
        if target in content:
            new_content = content.replace(target, target + sidebar_addition)
            with open(file, 'w') as f:
                f.write(new_content)
            print(f"Updated {file}")
