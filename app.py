import pandas as pd
import io
from flask import send_file
from sqlalchemy import func
import json
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from weasyprint import HTML, CSS
from datetime import datetime
from functools import wraps
from flask import jsonify
from datetime import datetime, timedelta



# ============== KONFIGURASI APLIKASI ==============
app = Flask(__name__)
app.config['SECRET_KEY'] = 'kunci-rahasia-yang-sangat-aman' # Ganti dengan kunci rahasia Anda
# Format URI: 'mysql+pymysql://user:password@host/dbname'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@localhost/db_kasir' # Sesuaikan dengan konfigurasi DB Anda
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ============== INISIALISASI EXTENSIONS ==============
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
login_manager.login_message = "Silakan login untuk mengakses halaman ini."

# ============== MODEL DATABASE (SQLALCHEMY) ==============
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='kasir') # <-- TAMBAHKAN BARIS INI


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kode_produk = db.Column(db.String(50), unique=True, nullable=False)
    nama = db.Column(db.String(100), nullable=False)
    harga = db.Column(db.Integer, nullable=False)
    stok = db.Column(db.Integer, nullable=False)
    stok_minimum = db.Column(db.Integer, nullable=False, default=5) # <-- TAMBAHKAN INI
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tanggal = db.Column(db.DateTime, default=datetime.utcnow)
    subtotal = db.Column(db.Integer, nullable=False) # Ganti dari total_harga
    diskon = db.Column(db.Integer, nullable=False, default=0) # Kolom baru
    grand_total = db.Column(db.Integer, nullable=False) # Kolom baru
    nama_kasir = db.Column(db.String(100), nullable=False)
    details = db.relationship('TransactionDetail', backref='transaction', lazy=True, cascade="all, delete-orphan")


class TransactionDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    jumlah = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Integer, nullable=False)
    product = db.relationship('Product')


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), unique=True, nullable=False)
    products = db.relationship('Product', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.nama}>'


class StockHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    jumlah_perubahan = db.Column(db.Integer, nullable=False)
    stok_sebelum = db.Column(db.Integer, nullable=False)
    stok_sesudah = db.Column(db.Integer, nullable=False)
    tipe_kegiatan = db.Column(db.String(50), nullable=False) # 'Penjualan', 'Penambahan Stok', 'Koreksi Manual'
    keterangan = db.Column(db.Text, nullable=True)
    tanggal_perubahan = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    product = db.relationship('Product')
    user = db.relationship('User')

@app.context_processor
def inject_low_stock_count():
    if current_user.is_authenticated:
        low_stock_count = Product.query.filter(Product.stok <= Product.stok_minimum).count()
        return dict(low_stock_count=low_stock_count) # <-- PERBAIKI BARIS INI
    return dict(low_stock_count=0)


# ============== FUNGSI UNTUK FLASK-LOGIN ==============
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Decorator untuk memastikan hanya admin yang bisa mengakses
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Akses ditolak. Halaman ini hanya untuk admin.', 'danger')
            return redirect(url_for('kasir'))
        return f(*args, **kwargs)
    return decorated_function


# ============== ROUTES & LOGIKA APLIKASI ==============

# --- Rute Autentikasi ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Bagian ini sudah benar, user yang sudah login tidak perlu ke halaman login lagi
    if current_user.is_authenticated:
        # Jika admin, arahkan ke dashboard, jika kasir ke kasir
        if current_user.role == 'admin':
            return redirect(url_for('dashboard'))
        return redirect(url_for('kasir'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        # Ini adalah blok pengecekan utama
        if user and bcrypt.check_password_hash(user.password, password):
            # --- JIKA LOGIN BERHASIL ---
            login_user(user)
            flash(f'Selamat datang kembali, {user.username}!', 'success')
            
            # Pengecekan role dan redirect diletakkan DI DALAM blok ini
            if user.role == 'admin':
                return redirect(url_for('dashboard'))
            else: # Berarti rolenya 'kasir'
                return redirect(url_for('kasir'))
        else:
            # --- JIKA LOGIN GAGAL ---
            # Ini adalah satu-satunya 'else' untuk blok pengecekan utama
            flash('Login gagal. Periksa kembali username dan password Anda.', 'danger')
            # Tidak perlu redirect, biarkan halaman me-render form login lagi di bawah

    # Baris ini akan dieksekusi jika:
    # 1. Metodenya GET (pengguna baru membuka halaman login)
    # 2. Metodenya POST tapi login gagal
    return render_template('login.html')


# ----Route Dashboard ---
@app.route('/dashboard')
@login_required
@admin_required
def dashboard():
    # --- 1. Statistik Penjualan Hari Ini ---
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())

    sales_today = db.session.query(
        func.sum(Transaction.grand_total),
        func.count(Transaction.id)
    ).filter(Transaction.tanggal.between(start_of_day, end_of_day)).first()

    pendapatan_hari_ini = sales_today[0] or 0
    transaksi_hari_ini = sales_today[1] or 0

    # --- 2. Produk dengan Stok Rendah ---
    produk_stok_rendah = Product.query.filter(Product.stok <= Product.stok_minimum).order_by(Product.stok.asc()).limit(5).all()

    # --- 3. Transaksi Terakhir ---
    transaksi_terakhir = Transaction.query.order_by(Transaction.tanggal.desc()).limit(5).all()

    # --- 4. Data untuk Grafik Penjualan 7 Hari Terakhir ---
    sales_labels = []
    sales_data = []
    sales_by_day = {}

    # Query data penjualan yang dikelompokkan per hari
    last_7_days_sales = db.session.query(
        func.date(Transaction.tanggal).label('sale_date'),
        func.sum(Transaction.grand_total).label('total_sales')
    ).filter(Transaction.tanggal >= today - timedelta(days=6))\
     .group_by('sale_date').all()

    # Masukkan hasil query ke dictionary agar mudah diakses
    for sale in last_7_days_sales:
        sales_by_day[sale.sale_date] = sale.total_sales

    # Loop 7 hari ke belakang untuk memastikan semua hari ada (termasuk yang penjualannya 0)
    for i in range(7):
        current_date = today - timedelta(days=6-i)
        sales_labels.append(current_date.strftime('%d %b')) # Format tanggal (e.g., '13 Jun')
        sales_data.append(sales_by_day.get(current_date, 0)) # Ambil data penjualan, atau 0 jika tidak ada

    return render_template(
        'dashboard.html',
        title="Dashboard",
        pendapatan_hari_ini=pendapatan_hari_ini,
        transaksi_hari_ini=transaksi_hari_ini,
        produk_stok_rendah=produk_stok_rendah,
        transaksi_terakhir=transaksi_terakhir,
        sales_labels=sales_labels,
        sales_data=sales_data
    )



@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah berhasil logout.', 'success')
    return redirect(url_for('login'))

# --- Rute Utama & Kasir ---
@app.route('/')
@login_required
def kasir():
    # Ambil parameter dari URL
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '', type=str)
    category_id = request.args.get('category', '', type=str)

    # Query dasar untuk produk
    products_query = Product.query

    # Terapkan filter jika ada
    if search_query:
        # Mencari di kode produk atau nama produk
        search_term = f"%{search_query}%"
        products_query = products_query.filter(
            db.or_(Product.kode_produk.like(search_term), Product.nama.like(search_term))
        )
    
    if category_id and category_id.isdigit():
        products_query = products_query.filter_by(category_id=int(category_id))

    # Lakukan paginasi setelah semua filter diterapkan
    pagination = products_query.order_by(Product.nama).paginate(page=page, per_page=12, error_out=False)
    products_on_page = pagination.items

    categories = Category.query.order_by(Category.nama).all()
    
    return render_template(
        'kasir.html', 
        products=products_on_page, 
        categories=categories,
        pagination=pagination,
        search_query=search_query,
        active_category_id=category_id
    )



@app.route('/proses_transaksi', methods=['POST'])
@login_required
def proses_transaksi():
    try:
        cart_data = json.loads(request.form.get('cart'))
        subtotal = int(request.form.get('subtotal'))
        diskon = int(request.form.get('diskon'))
        grand_total = int(request.form.get('grand_total'))

        if not cart_data:
            flash('Keranjang belanja kosong!', 'warning')
            return redirect(url_for('kasir'))

        # Buat transaksi baru dengan data diskon
        new_transaction = Transaction(
            subtotal=subtotal,
            diskon=diskon,
            grand_total=grand_total,
            nama_kasir=current_user.username
        )
        db.session.add(new_transaction)
        db.session.flush()

        # Simpan detail transaksi dan kurangi stok
        for item in cart_data:
            product = Product.query.get(item['id'])
            if product and product.stok >= item['quantity']:
                stok_sebelum = product.stok
                product.stok -= item['quantity']
                
                detail = TransactionDetail(
                    transaction_id=new_transaction.id,
                    product_id=product.id,
                    jumlah=item['quantity'],
                    subtotal=item['price'] * item['quantity']
                )
                db.session.add(detail)
                
                # Buat history stok untuk setiap item
                history_entry = StockHistory(
                    product_id=product.id,
                    jumlah_perubahan=-item['quantity'],
                    stok_sebelum=stok_sebelum,
                    stok_sesudah=product.stok,
                    tipe_kegiatan='Penjualan',
                    keterangan=f'Transaksi #{new_transaction.id}',
                    user_id=current_user.id
                )
                db.session.add(history_entry)

            else:
                db.session.rollback()
                flash(f'Stok produk {product.nama} tidak mencukupi!', 'danger')
                return redirect(url_for('kasir'))

        db.session.commit()
        flash('Transaksi berhasil disimpan!', 'success')
        return redirect(url_for('cetak_struk', transaction_id=new_transaction.id))

    except Exception as e:
        db.session.rollback()
        flash(f'Terjadi kesalahan saat memproses transaksi: {e}', 'danger')
        return redirect(url_for('kasir'))



# --- Rute Manajemen Produk ---
@app.route('/produk')
@login_required
def produk():
    products = Product.query.all()
    return render_template('produk.html', products=products)


@app.route('/produk/tambah', methods=['GET', 'POST'])
@login_required
def tambah_produk():
    if request.method == 'POST':
        kode_produk = request.form.get('kode_produk')
        nama = request.form.get('nama')
        harga = request.form.get('harga')
        stok = request.form.get('stok')
        stok_minimum = request.form.get('stok_minimum')
        category_id = request.form.get('category_id')


        if Product.query.filter_by(kode_produk=kode_produk).first():
            flash('Kode produk sudah ada.', 'warning')
            # Kita perlu mengirim ulang daftar kategori jika terjadi error
            categories = Category.query.all()
            return render_template('produk_form.html', title="Tambah Produk", form_action=url_for('tambah_produk'), categories=categories)

        # Membuat objek produk baru dengan semua data yang diperlukan
        new_product = Product(
            kode_produk=kode_produk, 
            nama=nama, 
            harga=harga, 
            stok=stok, 
            stok_minimum=stok_minimum,
            category_id=category_id
        )
        db.session.add(new_product)
        db.session.commit()
        flash('Produk berhasil ditambahkan!', 'success')
        return redirect(url_for('produk'))
    
    # Bagian GET request (tetap sama)
    categories = Category.query.all()
    return render_template('produk_form.html', title="Tambah Produk", form_action=url_for('tambah_produk'), categories=categories)


@app.route('/produk/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_produk(id):
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.kode_produk = request.form.get('kode_produk')
        product.nama = request.form.get('nama')
        product.harga = request.form.get('harga')
        product.stok = request.form.get('stok')
        product.stok_minimum = request.form.get('stok_minimum')
        product.category_id = request.form.get('category_id')
        db.session.commit()
        flash('Produk berhasil diperbarui!', 'success')
        return redirect(url_for('produk'))
    categories = Category.query.all() # <-- ambil daftar kategori
    return render_template('produk_form.html', title="Edit Produk", product=product, form_action=url_for('edit_produk', id=id), categories=categories) # <-- kirim ke template


@app.route('/produk/hapus/<int:id>', methods=['POST'])
@login_required
def hapus_produk(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('Produk berhasil dihapus!', 'success')
    return redirect(url_for('produk'))

# ... (kode route yang sudah ada sebelumnya) ...

# --- Rute Laporan Penjualan ---

@app.route('/laporan', methods=['GET'])
@login_required
def laporan():
    today = datetime.today()
    start_date_str = request.args.get('start_date', today.replace(day=1).strftime('%Y-%m-%d'))
    end_date_str = request.args.get('end_date', today.strftime('%Y-%m-%d'))

    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

    transactions_in_range = Transaction.query.filter(Transaction.tanggal.between(start_date, end_date))

    # --- PERBAIKAN DI SINI ---
    total_pendapatan = transactions_in_range.with_entities(func.sum(Transaction.grand_total)).scalar() or 0
    jumlah_transaksi = transactions_in_range.count()
    
    total_barang_terjual = db.session.query(func.sum(TransactionDetail.jumlah)).join(Transaction).filter(Transaction.tanggal.between(start_date, end_date)).scalar() or 0

    top_products_query = db.session.query(
        Product.nama,
        func.sum(TransactionDetail.jumlah).label('total_terjual')
    ).join(TransactionDetail, Product.id == TransactionDetail.product_id)\
     .join(Transaction, Transaction.id == TransactionDetail.transaction_id)\
     .filter(Transaction.tanggal.between(start_date, end_date))\
     .group_by(Product.nama)\
     .order_by(func.sum(TransactionDetail.jumlah).desc())\
     .limit(5).all()

    top_products_labels = [item.nama for item in top_products_query]
    top_products_data = [item.total_terjual for item in top_products_query]

    statistik = {
        'total_pendapatan': total_pendapatan,
        'jumlah_transaksi': jumlah_transaksi,
        'total_barang_terjual': total_barang_terjual
    }
    
    return render_template(
        'laporan.html', 
        title="Laporan Penjualan",
        statistik=statistik,
        top_products=top_products_query,
        top_products_labels=top_products_labels,
        top_products_data=top_products_data,
        start_date=start_date_str,
        end_date=end_date_str
    )


# --- Rute untuk Ekspor Data ---
@app.route('/export/laporan')
@login_required
@admin_required
def export_laporan():
    # Ambil parameter tanggal dari URL untuk memastikan data yang diekspor sesuai dengan yang ditampilkan
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

    # Query untuk mengambil data produk terlaris (sama seperti di halaman laporan)
    top_products_query = db.session.query(
        Product.nama,
        Category.nama.label('kategori'),
        func.sum(TransactionDetail.jumlah).label('total_terjual'),
        func.sum(TransactionDetail.subtotal).label('total_pendapatan')
    ).join(TransactionDetail, Product.id == TransactionDetail.product_id)\
     .join(Category, Product.category_id == Category.id)\
     .join(Transaction, Transaction.id == TransactionDetail.transaction_id)\
     .filter(Transaction.tanggal.between(start_date, end_date))\
     .group_by(Product.nama, Category.nama)\
     .order_by(func.sum(TransactionDetail.jumlah).desc()).all()

    # Buat Pandas DataFrame dari hasil query
    df = pd.DataFrame(top_products_query, columns=['Nama Produk', 'Kategori', 'Total Terjual (Unit)', 'Total Pendapatan (Rp)'])

    # Buat file Excel di dalam memori
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name='Laporan Penjualan')
    writer.close()
    output.seek(0)

    # Kirim file ke browser sebagai download
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'laporan_penjualan_{start_date_str}_sd_{end_date_str}.xlsx'
    )


@app.route('/export/riwayat')
@login_required
def export_riwayat():
    # Ambil semua data riwayat transaksi
    transactions = Transaction.query.order_by(Transaction.tanggal.desc()).all()
    
    # Siapkan list untuk diubah ke DataFrame
    data_to_export = []
    for trx in transactions:
        for detail in trx.details:
            data_to_export.append({
                'ID Transaksi': trx.id,
                'Tanggal': trx.tanggal.strftime('%Y-%m-%d %H:%M:%S'),
                'Kasir': trx.nama_kasir,
                'Kode Produk': detail.product.kode_produk,
                'Nama Produk': detail.product.nama,
                'Kategori': detail.product.category.nama,
                'Jumlah': detail.jumlah,
                'Harga Satuan': detail.product.harga,
                'Subtotal Item': detail.subtotal,
                'Diskon Transaksi': trx.diskon,
                'Grand Total Transaksi': trx.grand_total,
            })

    if not data_to_export:
        flash('Tidak ada data riwayat untuk diekspor.', 'warning')
        return redirect(url_for('riwayat'))

    df = pd.DataFrame(data_to_export)

    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name='Riwayat Transaksi')
    writer.close()
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='riwayat_transaksi_lengkap.xlsx'
    )


@app.route('/riwayat/hapus/<int:id>', methods=['POST'])
@login_required
@admin_required
def hapus_riwayat(id):
    trx = Transaction.query.get_or_404(id)
    db.session.delete(trx)
    db.session.commit()
    flash(f'Transaksi #{id} berhasil dihapus.', 'success')
    return redirect(url_for('riwayat'))

@app.route('/riwayat/hapus_semua', methods=['POST'])
@login_required
@admin_required
def hapus_semua_riwayat():
    try:
        # Hapus semua detail dulu, baru transaksinya
        db.session.query(TransactionDetail).delete()
        db.session.query(Transaction).delete()
        db.session.commit()
        flash('Semua riwayat transaksi berhasil dikosongkan.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Gagal mengosongkan riwayat: {e}', 'danger')
    return redirect(url_for('riwayat'))


# --- API Endpoint untuk Barcode Scanner ---
@app.route('/api/produk_by_kode/<kode_produk>')
@login_required
def get_produk_by_kode(kode_produk):
    product = Product.query.filter_by(kode_produk=kode_produk).first()
    if product:
        return jsonify({
            'id': product.id,
            'nama': product.nama,
            'harga': product.harga,
            'stok': product.stok
        })
    else:
        return jsonify({'error': 'Produk tidak ditemukan'}), 404



# --- Rute Manajemen User (Hanya untuk Admin) ---

# --- Rute Manajemen Kategori (Hanya untuk Admin) ---

@app.route('/kategori')
@login_required
@admin_required
def kategori():
    all_categories = Category.query.order_by(Category.nama).all()
    return render_template('kategori.html', title="Manajemen Kategori", categories=all_categories)

@app.route('/kategori/tambah', methods=['GET', 'POST'])
@login_required
@admin_required
def tambah_kategori():
    if request.method == 'POST':
        nama = request.form.get('nama_kategori')
        if Category.query.filter_by(nama=nama).first():
            flash('Nama kategori sudah ada.', 'warning')
        else:
            new_category = Category(nama=nama)
            db.session.add(new_category)
            db.session.commit()
            flash('Kategori baru berhasil ditambahkan!', 'success')
        return redirect(url_for('kategori'))
    return render_template('kategori_form.html', title="Tambah Kategori", form_action=url_for('tambah_kategori'))

@app.route('/kategori/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_kategori(id):
    category = Category.query.get_or_404(id)
    if request.method == 'POST':
        category.nama = request.form.get('nama_kategori')
        db.session.commit()
        flash('Kategori berhasil diperbarui!', 'success')
        return redirect(url_for('kategori'))
    return render_template('kategori_form.html', title="Edit Kategori", category=category, form_action=url_for('edit_kategori', id=id))

@app.route('/kategori/hapus/<int:id>', methods=['POST'])
@login_required
@admin_required
def hapus_kategori(id):
    # Cek apakah kategori masih digunakan oleh produk
    if Product.query.filter_by(category_id=id).first():
        flash('Kategori tidak bisa dihapus karena masih digunakan oleh produk.', 'danger')
        return redirect(url_for('kategori'))

    category = Category.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    flash('Kategori berhasil dihapus.', 'success')
    return redirect(url_for('kategori'))


@app.route('/users')
@login_required
@admin_required
def users():
    all_users = User.query.all()
    return render_template('users.html', title="Manajemen User", users=all_users)

@app.route('/users/tambah', methods=['GET', 'POST'])
@login_required
@admin_required
def tambah_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        if User.query.filter_by(username=username).first():
            flash('Username sudah ada.', 'warning')
            return redirect(url_for('tambah_user'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('User baru berhasil ditambahkan!', 'success')
        return redirect(url_for('users'))
        
    return render_template('user_form.html', title="Tambah User", form_action=url_for('tambah_user'))


@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    user_to_edit = User.query.get_or_404(id)
    if request.method == 'POST':
        user_to_edit.username = request.form.get('username')
        user_to_edit.role = request.form.get('role')
        
        new_password = request.form.get('password')
        if new_password:
            user_to_edit.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        
        db.session.commit()
        flash('Data user berhasil diperbarui!', 'success')
        return redirect(url_for('users'))

    return render_template('user_form.html', title="Edit User", user=user_to_edit, form_action=url_for('edit_user', id=id))

@app.route('/users/hapus/<int:id>', methods=['POST'])
@login_required
@admin_required
def hapus_user(id):
    user_to_delete = User.query.get_or_404(id)

    # Pencegahan agar admin tidak bisa menghapus dirinya sendiri
    if user_to_delete.id == current_user.id:
        flash('Anda tidak bisa menghapus akun Anda sendiri.', 'danger')
        return redirect(url_for('users'))

    db.session.delete(user_to_delete)
    db.session.commit()
    flash('User berhasil dihapus.', 'success')
    return redirect(url_for('users'))

# --- Rute Produk Koreksi Stok ---
@app.route('/produk/koreksi_stok/<int:id>', methods=['POST'])
@login_required
@admin_required
def koreksi_stok(id):
    product = Product.query.get_or_404(id)
    perubahan = int(request.form.get('jumlah_perubahan'))
    keterangan = request.form.get('keterangan')

    stok_sebelum = product.stok
    product.stok += perubahan
    stok_sesudah = product.stok

    history_entry = StockHistory(
        product_id=id,
        jumlah_perubahan=perubahan,
        stok_sebelum=stok_sebelum,
        stok_sesudah=stok_sesudah,
        tipe_kegiatan='Koreksi Manual',
        keterangan=keterangan,
        user_id=current_user.id
    )
    db.session.add(history_entry)
    db.session.commit()

    flash(f'Stok produk {product.nama} berhasil dikoreksi.', 'success')
    return redirect(url_for('produk'))


# ... (lanjutan kode lainnya)

# ... (lanjutan kode route riwayat, cetak_struk, dll.) ...

# --- Rute Riwayat & Struk ---
@app.route('/riwayat')
@login_required
def riwayat():
    transactions = Transaction.query.order_by(Transaction.tanggal.desc()).all()
    return render_template('riwayat.html', transactions=transactions)

@app.route('/cetak_struk/<int:transaction_id>')
@login_required
def cetak_struk(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    # Render template HTML untuk struk
    rendered_html = render_template('struk.html', trx=transaction)
    
    # Buat PDF menggunakan WeasyPrint
    pdf = HTML(string=rendered_html).write_pdf()
    
    return Response(pdf, mimetype='application/pdf', headers={
        'Content-Disposition': f'inline; filename=struk_{transaction_id}.pdf'
    })

# app.py
@app.route('/produk/riwayat_stok/<int:id>')
@login_required
@admin_required
def riwayat_stok(id):
    product = Product.query.get_or_404(id)
    history = StockHistory.query.filter_by(product_id=id).order_by(StockHistory.tanggal_perubahan.desc()).all()
    return render_template('riwayat_stok.html', title=f"Riwayat Stok {product.nama}", product=product, history=history)



# ============== JALANKAN APLIKASI ==============
if __name__ == '__main__':
    # Untuk pertama kali, jalankan ini untuk membuat tabel
    # with app.app_context():
    #    db.create_all()
      app.run(debug=True)

