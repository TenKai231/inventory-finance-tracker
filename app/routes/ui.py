from flask import Blueprint, render_template, redirect, url_for
from flask_jwt_extended import verify_jwt_in_request
from functools import wraps

ui_bp = Blueprint('ui', __name__)

def login_required_ui(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            # Proteksi dashboard: Cek JWT di cookies atau headers.
            # Jika user belum login, lempar kembali ke halaman login.
            verify_jwt_in_request(locations=["cookies", "headers"])
        except:
            return redirect(url_for('ui.login'))
        return f(*args, **kwargs)
    return decorated

@ui_bp.route('/')
def index():
    """Landing page publik — tidak memerlukan login."""
    return render_template('index.html')

@ui_bp.route('/dashboard')
@login_required_ui
def dashboard():
    return render_template('dashboard.html')

@ui_bp.route('/inventory')
@login_required_ui
def inventory():
    return render_template('inventory.html')

@ui_bp.route('/transactions')
@login_required_ui
def transactions():
    return render_template('transactions.html')

@ui_bp.route('/finance')
@login_required_ui
def finance_page():
    return render_template('finance.html')

@ui_bp.route('/export')
@login_required_ui
def export_page():
    return render_template('export.html')

@ui_bp.route('/settings')
@login_required_ui
def settings_page():
    return render_template('settings.html')

@ui_bp.route('/inventory/empty')
@login_required_ui
def inventory_empty():
    return render_template('inventory_empty.html')

@ui_bp.route('/inventory/loading')
@login_required_ui
def inventory_loading():
    return render_template('loading.html')

@ui_bp.route('/login')
def login():
    return render_template('login.html')

@ui_bp.route('/register')
def register():
    return render_template('register.html')

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
