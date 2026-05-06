from flask import Blueprint, render_template

ui_bp = Blueprint('ui', __name__)

@ui_bp.route('/')
def dashboard():
    return render_template('dashboard.html')

@ui_bp.route('/inventory')
def inventory():
    return render_template('inventory.html')

@ui_bp.route('/inventory/empty')
def inventory_empty():
    return render_template('inventory_empty.html')

@ui_bp.route('/inventory/loading')
def inventory_loading():
    return render_template('loading.html')

@ui_bp.route('/login')
def login():
    return render_template('login.html')

@ui_bp.app_errorhandler(404)
def page_not_found(e):
    return render_template('error.html', 
                           page_title="Halaman Tidak Ditemukan", 
                           page_subtitle="404 Error",
                           error_icon="search_off",
                           error_title="Halaman Tidak Ditemukan",
                           error_message="Halaman yang Anda cari mungkin telah dihapus, diubah namanya, atau tidak tersedia sementara."), 404

@ui_bp.app_errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', 
                           page_title="Server Error", 
                           page_subtitle="500 Error",
                           error_icon="cloud_off",
                           error_title="Gagal memuat data",
                           error_message="Terjadi kesalahan sistem di server kami. Silakan coba lagi nanti."), 500
