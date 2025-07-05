# 1. IMPOR SEMUA YANG DIBUTUHKAN
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
import os
from openai import OpenAI
import random
import math
from datetime import date, timedelta
import json
import time
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# 2. INISIALISASI APLIKASI FLASK DENGAN SESSION STABIL
app = Flask(__name__)

# PERBAIKI: Konfigurasi session yang stabil
if os.getenv('SECRET_KEY'):
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
else:
    app.config['SECRET_KEY'] = 'web-ajaib-secret-key-2025-stable'  # Fixed key untuk development

# Session configuration untuk mencegah logout otomatis
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # 7 hari
app.config['SESSION_COOKIE_SECURE'] = False  # Set True untuk HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

def get_db_connection():
    """Fungsi untuk terhubung ke database PostgreSQL."""
    try:
        if os.getenv("POSTGRES_URL"):
            conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        else:
            conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                database=os.getenv('DB_NAME', 'web_ajaib'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'password'),
                port=os.getenv('DB_PORT', '5432')
            )
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def init_database():
    """Fungsi untuk membuat tabel jika belum ada."""
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return
    
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            nama_lengkap VARCHAR(100),
            poin INTEGER DEFAULT 0,
            kuis_terakhir_dimainkan DATE,
            kuis_dimainkan_hari_ini INTEGER DEFAULT 0,
            avatar_style VARCHAR(50),
            judol_losing_streak INTEGER DEFAULT 0,
            judol_bomb_strike_active INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS daily_quiz (
            tanggal DATE PRIMARY KEY,
            soal_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.close()
    conn.close()
    print("Database PostgreSQL initialized successfully.")

# 3. HELPER FUNCTION UNTUK CEK USER TANPA LOGOUT PAKSA
def get_current_user():
    """Helper function untuk mendapatkan data user saat ini tanpa logout paksa."""
    if 'user_id' not in session:
        return None
    
    user_id = session['user_id']
    conn = get_db_connection()
    if not conn:
        # JANGAN CLEAR SESSION jika database error
        print("Database connection failed, but keeping session")
        return None
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        
        # JANGAN CLEAR SESSION jika user tidak ditemukan
        if not user_data:
            print(f"User {user_id} not found in database, but keeping session")
        
        return user_data
    except Exception as e:
        print(f"Error getting user data: {e}")
        if conn:
            conn.close()
        return None

# 4. FUNGSI AI
def ai_call(year):
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "user", "content": f"Berikan 1 fakta unik mengenai teknologi pada tahun {year} secara singkat menggunakan bahasa indonesia."}
            ],
            max_tokens=150
        )
        ai_output = response.choices[0].message.content
        return ai_output
    except Exception as e:
        print(f"Gagal ambil respon: {e}")
        return "Maaf, tidak bisa memproses permintaan saat ini."

AVATAR_STYLES = [
    'adventurer', 'adventurer-neutral', 'avataaars', 'big-ears', 
    'big-smile', 'bottts', 'croodles', 'fun-emoji', 'icons', 
    'identicon', 'initials', 'lorelei', 'micah', 'miniavs', 
    'open-peeps', 'personas', 'pixel-art', 'shapes'
]

# --- FUNGSI-FUNGSI LOGIKA KUIS ---
def muat_soal_json():
    try:
        with open('kuis.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def generate_kuis_from_ai(jumlah_soal=10):
    topik_list = [
        "sejarah Indonesia", "geografi dunia", "sains dan teknologi", 
        "budaya Indonesia", "olahraga", "matematika dasar", 
        "bahasa Indonesia", "biologi", "fisika", "kimia",
        "sejarah dunia", "astronomi", "ekonomi", "politik",
        "seni dan musik", "kuliner Indonesia", "flora fauna",
        "negara di dunia", "penemuan bersejarah", "tokoh dunia"
    ]
    
    topik_terpilih = random.sample(topik_list, min(3, len(topik_list)))
    topik_str = ", ".join(topik_terpilih)
    
    prompt = f"""
    Buatkan {jumlah_soal} pertanyaan kuis pengetahuan umum yang BERBEDA dan UNIK dalam Bahasa Indonesia.
    Fokus pada topik: {topik_str}
    
    PENTING: 
    - Setiap pertanyaan harus BERBEDA dari yang lain
    - Jangan buat pertanyaan yang mirip
    - Gunakan tingkat kesulitan yang bervariasi
    - Buat pertanyaan yang menarik dan edukatif
    
    Format JSON yang wajib:
    [
      {{
        "pertanyaan": "Pertanyaan yang unik dan menarik",
        "pilihan": ["Pilihan A", "Pilihan B", "Pilihan C", "Pilihan D"],
        "jawaban_benar": "Pilihan yang benar"
      }}
    ]
    
    Berikan HANYA array JSON, tanpa teks tambahan atau penjelasan.
    """
    
    try:
        response = client.chat.completions.create(
            model="gemma2-9b-it",
            messages=[
                {
                    "role": "system", 
                    "content": "Anda adalah guru kreatif yang selalu membuat soal kuis yang berbeda-beda dan menarik. Selalu berikan variasi soal yang tinggi."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.9,
            max_tokens=2000,
            top_p=0.95
        )
        
        ai_response = response.choices[0].message.content.strip()
        print(f"DEBUG: AI Response dengan topik: {topik_str}")
        
        if ai_response.startswith('```json'):
            ai_response = ai_response.replace('```json', '').replace('```', '').strip()
        elif ai_response.startswith('```'):
            ai_response = ai_response.replace('```', '').strip()
        
        list_soal = json.loads(ai_response)
        print(f"DEBUG: Berhasil generate {len(list_soal)} soal dengan topik {topik_str}")
        return list_soal
        
    except Exception as e:
        print(f"Error saat membuat soal dari AI: {e}")
        return get_backup_soal_random(jumlah_soal)

def get_backup_soal_random(jumlah_soal=10):
    """Backup soal dengan variasi tinggi"""
    all_backup = [
        {
            "pertanyaan": "Apa ibu kota Indonesia?",
            "pilihan": ["Jakarta", "Bandung", "Surabaya", "Medan"],
            "jawaban_benar": "Jakarta"
        },
        {
            "pertanyaan": "Siapa penemu bola lampu?",
            "pilihan": ["Thomas Edison", "Nikola Tesla", "Alexander Bell", "Wright Brothers"],
            "jawaban_benar": "Thomas Edison"
        },
        {
            "pertanyaan": "Planet terjauh dari matahari dalam tata surya?",
            "pilihan": ["Uranus", "Neptunus", "Pluto", "Saturnus"],
            "jawaban_benar": "Neptunus"
        },
        {
            "pertanyaan": "Negara dengan penduduk terbanyak di dunia?",
            "pilihan": ["India", "China", "Amerika Serikat", "Indonesia"],
            "jawaban_benar": "China"
        },
        {
            "pertanyaan": "Unsur kimia dengan simbol Au adalah?",
            "pilihan": ["Perak", "Emas", "Aluminium", "Argon"],
            "jawaban_benar": "Emas"
        },
        {
            "pertanyaan": "Bahasa resmi negara Brasil?",
            "pilihan": ["Spanyol", "Portugis", "Inggris", "Prancis"],
            "jawaban_benar": "Portugis"
        },
        {
            "pertanyaan": "Gunung tertinggi di dunia?",
            "pilihan": ["K2", "Everest", "Kilimanjaro", "Fuji"],
            "jawaban_benar": "Everest"
        },
        {
            "pertanyaan": "Berapa detik dalam 1 menit?",
            "pilihan": ["50", "60", "70", "80"],
            "jawaban_benar": "60"
        },
        {
            "pertanyaan": "Benua tempat negara Mesir berada?",
            "pilihan": ["Asia", "Afrika", "Eropa", "Amerika"],
            "jawaban_benar": "Afrika"
        },
        {
            "pertanyaan": "Hewan tercepat di darat?",
            "pilihan": ["Singa", "Cheetah", "Harimau", "Leopard"],
            "jawaban_benar": "Cheetah"
        },
        {
            "pertanyaan": "Nama lain untuk vitamin C?",
            "pilihan": ["Asam folat", "Asam askorbat", "Retinol", "Kalsiferol"],
            "jawaban_benar": "Asam askorbat"
        },
        {
            "pertanyaan": "Penemu teori relativitas?",
            "pilihan": ["Newton", "Einstein", "Galileo", "Darwin"],
            "jawaban_benar": "Einstein"
        },
        {
            "pertanyaan": "Mata uang negara Jepang?",
            "pilihan": ["Won", "Yuan", "Yen", "Rupee"],
            "jawaban_benar": "Yen"
        },
        {
            "pertanyaan": "Organ tubuh yang memproduksi insulin?",
            "pilihan": ["Hati", "Ginjal", "Pankreas", "Limpa"],
            "jawaban_benar": "Pankreas"
        },
        {
            "pertanyaan": "Ibukota negara Australia?",
            "pilihan": ["Sydney", "Melbourne", "Canberra", "Perth"],
            "jawaban_benar": "Canberra"
        },
        {
            "pertanyaan": "Sungai terpanjang di dunia?",
            "pilihan": ["Amazon", "Nil", "Yangtze", "Mississippi"],
            "jawaban_benar": "Nil"
        },
        {
            "pertanyaan": "Siapa pelukis terkenal asal Italia yang melukis Mona Lisa?",
            "pilihan": ["Michelangelo", "Leonardo da Vinci", "Raphael", "Donatello"],
            "jawaban_benar": "Leonardo da Vinci"
        },
        {
            "pertanyaan": "Gas yang paling banyak di atmosfer bumi?",
            "pilihan": ["Oksigen", "Nitrogen", "Karbon dioksida", "Argon"],
            "jawaban_benar": "Nitrogen"
        },
        {
            "pertanyaan": "Tahun berapa Indonesia merdeka?",
            "pilihan": ["1944", "1945", "1946", "1947"],
            "jawaban_benar": "1945"
        },
        {
            "pertanyaan": "Komponen utama air adalah?",
            "pilihan": ["H2O", "CO2", "NaCl", "O2"],
            "jawaban_benar": "H2O"
        }
    ]
    
    random.shuffle(all_backup)
    return all_backup[:jumlah_soal]

def siapkan_kuis_harian():
    random.seed(int(time.time()))
    
    soal_harian = []
    
    if random.randint(1, 100) <= 10:
        try:
            bank_soal_json = muat_soal_json()
            if bank_soal_json:
                jumlah_soal_json = random.randint(1, min(3, len(bank_soal_json)))
                soal_harian.extend(random.sample(bank_soal_json, jumlah_soal_json))
                print(f"DEBUG: Mengambil {jumlah_soal_json} soal dari JSON")
        except Exception as e:
            print(f"DEBUG: Error membaca JSON: {e}")
    
    jumlah_soal_ai = 10 - len(soal_harian)
    if jumlah_soal_ai > 0:
        print(f"DEBUG: Membuat {jumlah_soal_ai} soal dari AI")
        soal_ai = generate_kuis_from_ai(jumlah_soal_ai)
        soal_harian.extend(soal_ai)
    
    random.shuffle(soal_harian)
    print(f"DEBUG: Total soal final: {len(soal_harian)}")
    return soal_harian[:10]

# DEBUG SESSION MIDDLEWARE
@app.before_request
def log_session_info():
    if request.endpoint and request.endpoint not in ['static']:
        print(f"Route: {request.endpoint}, Session User ID: {session.get('user_id', 'Not logged in')}")

# 5. RUTE-RUTE APLIKASI WEB

@app.route("/")
def hello_world():
    """Rute utama: Menampilkan dashboard jika login, atau halaman tamu jika belum."""
    user_data = get_current_user()
    if user_data:
        return render_template('dashboard.html', user=user_data, logged_in=True)
    return render_template('home.html', Web_title="WEB AJAIB")

# --- RUTE-RUTE KUIS ---
@app.route('/kuis')
def halaman_kuis():
    print("DEBUG: Masuk halaman kuis")
    
    if 'user_id' not in session:
        print("DEBUG: User belum login")
        flash('Anda harus login untuk memulai kuis!', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    if not conn:
        flash('Database error!', 'error')
        return redirect(url_for('hello_world'))

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT kuis_terakhir_dimainkan, kuis_dimainkan_hari_ini FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()

    hari_ini = date.today()
    
    if user and user['kuis_terakhir_dimainkan'] != hari_ini:
        cursor.execute('UPDATE users SET kuis_dimainkan_hari_ini = 0 WHERE id = %s', (user_id,))
        print("DEBUG: Reset counter kuis untuk hari baru")
    
    cursor.execute('SELECT kuis_terakhir_dimainkan, kuis_dimainkan_hari_ini FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    
    kuis_dimainkan = user['kuis_dimainkan_hari_ini'] if user else 0
    
    if kuis_dimainkan >= 3:
        print(f"DEBUG: User sudah main {kuis_dimainkan}x hari ini")
        flash(f'Anda sudah mengerjakan kuis 3x hari ini ({kuis_dimainkan}/3). Coba lagi besok!', 'warning')
        cursor.close()
        conn.close()
        return redirect(url_for('hello_world'))
    
    cursor.close()
    conn.close()
    
    print(f"DEBUG: Mulai buat kuis (sesi ke-{kuis_dimainkan + 1})")
    flash(f'Sedang meracik soal kuis untuk sesi ke-{kuis_dimainkan + 1}/3 hari ini...', 'info')
    kuis_harian = siapkan_kuis_harian()

    print(f"DEBUG: Jumlah soal: {len(kuis_harian) if kuis_harian else 0}")
    
    if not kuis_harian or len(kuis_harian) < 10:
        print("DEBUG: Gagal buat kuis")
        flash('Maaf, gagal membuat kuis saat ini. Coba lagi nanti.', 'error')
        return redirect(url_for('hello_world'))
    
    print("DEBUG: Kuis berhasil, simpan ke session")
    session['kuis_harian'] = kuis_harian
    session['soal_kuis_idx'] = 0
    session['skor_kuis'] = 0
    return redirect(url_for('kerjakan_kuis'))

@app.route('/kuis/kerjakan', methods=['GET', 'POST'])
def kerjakan_kuis():
    print("DEBUG: Masuk kerjakan kuis")
    
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    kuis_harian = session.get('kuis_harian', [])
    if not kuis_harian:
        print("DEBUG: Tidak ada kuis di session")
        return redirect(url_for('halaman_kuis'))
    
    total_soal = len(kuis_harian)
    print(f"DEBUG: Total soal: {total_soal}")

    if request.method == 'POST':
        print("DEBUG: POST request")
        jawaban_user = request.form.get('pilihan')
        idx_soal_sebelumnya = session.get('soal_kuis_idx', 0)
        
        if jawaban_user == kuis_harian[idx_soal_sebelumnya]['jawaban_benar']:
            session['skor_kuis'] += 10
            print("DEBUG: Jawaban benar, skor +10")

        session['soal_kuis_idx'] += 1

    idx_soal_sekarang = session.get('soal_kuis_idx', 0)
    print(f"DEBUG: Soal ke: {idx_soal_sekarang + 1}")

    if idx_soal_sekarang >= total_soal:
        print("DEBUG: Kuis selesai")
        skor_akhir = session.get('skor_kuis', 0)
        user_id = session['user_id']
        hari_ini = date.today()

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute('UPDATE users SET poin = poin + %s WHERE id = %s', (skor_akhir, user_id))
            cursor.execute('UPDATE users SET kuis_terakhir_dimainkan = %s WHERE id = %s', (hari_ini, user_id))
            cursor.execute('UPDATE users SET kuis_dimainkan_hari_ini = kuis_dimainkan_hari_ini + 1 WHERE id = %s', (user_id,))
            
            cursor.execute('SELECT kuis_dimainkan_hari_ini FROM users WHERE id = %s', (user_id,))
            user_data = cursor.fetchone()
            cursor.close()
            conn.close()
        
        sisa_main = 3 - user_data['kuis_dimainkan_hari_ini']

        # Hapus data kuis dari session
        session.pop('kuis_harian', None)
        session.pop('soal_kuis_idx', None)
        session.pop('skor_kuis', None)
        
        return render_template('kuis.html', 
                             selesai=True, 
                             skor=skor_akhir, 
                             total_soal=total_soal * 10,
                             sisa_main=sisa_main,
                             sudah_main=user_data['kuis_dimainkan_hari_ini'])
    else:
        print("DEBUG: Tampilkan soal")
        soal_sekarang = kuis_harian[idx_soal_sekarang]
        return render_template('kuis.html', 
                             soal=soal_sekarang, 
                             nomor_soal=idx_soal_sekarang + 1, 
                             total_soal=total_soal, 
                             selesai=False)

# --- RUTE-RUTE LAINNYA ---
@app.route("/about")
def about():
    user_data = get_current_user()
    return render_template('about.html', Web_title="Halaman About", user=user_data)

@app.route("/docs")
def docs():
    return render_template('docs.html', Web_title="Halaman Docs")

@app.route("/usia", methods=['GET', 'POST'])
def usia():
    print(f"Usia route - Session user_id: {session.get('user_id')}")
    
    if 'user_id' not in session:
        flash('Anda harus login untuk mengakses halaman ini.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        tahun_lahir = request.form['tahun_lahir']
        if not tahun_lahir:
            flash('Tahun lahir tidak boleh kosong!', 'error')
            return redirect(url_for('usia'))
        
        tahun_sekarang = 2025
        usia = tahun_sekarang - int(tahun_lahir)
        ai_output = ai_call(tahun_lahir)
        return render_template('usia.html', usia=usia, ai_output=ai_output, Web_title="Halaman Usia")
        
    return render_template('usia.html', usia=None, ai_output=None, Web_title="Halaman Usia")

@app.route("/login", methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('hello_world'))

    if request.method == 'POST':
        username = request.form['Username']
        password = request.form['Password']
        
        if not username or not password:
            flash('Username dan Password tidak boleh kosong!', 'error')
            return redirect(url_for('login'))

        conn = get_db_connection()
        user = None

        if conn:
            try:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                user = cursor.fetchone()
                cursor.close()
                conn.close()
            except Exception as e:
                print(f"Login error: {e}")
                if conn:
                    conn.close()
        
        if user and check_password_hash(user['password'], password):
            # Set session dengan permanent=True untuk durability
            session['user_id'] = user['id']
            session.permanent = True
            
            flash('Login berhasil!', 'success')
            print(f"User {user['username']} logged in successfully with session ID: {session['user_id']}")
            return redirect(url_for('hello_world'))
        else:
            flash('Username atau Password salah!', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route("/daftar", methods=['GET', 'POST'])
def daftar():
    if 'user_id' in session:
        return redirect(url_for('hello_world'))

    if request.method == 'POST':
        username = request.form['Username']
        password = request.form['Password']
        nama_lengkap = request.form['NamaLengkap']
        
        if not username or not password or not nama_lengkap:
            flash('Semua kolom harus diisi!', 'error')
            return redirect(url_for('daftar'))

        random_avatar_style = random.choice(AVATAR_STYLES)
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    'INSERT INTO users (username, password, nama_lengkap, avatar_style) VALUES (%s, %s, %s, %s)',
                    (username, hashed_password, nama_lengkap, random_avatar_style)
                )
                flash('Pendaftaran berhasil! Silakan login.', 'success')
                cursor.close()
                conn.close()
                return redirect(url_for('login'))
            except psycopg2.IntegrityError:
                flash('Username sudah terdaftar!', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('daftar'))
            except Exception as e:
                print(f"Registration error: {e}")
                flash('Terjadi kesalahan saat mendaftar!', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('daftar'))

    return render_template('daftar.html')

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    if not conn:
        flash('Database error!', 'error')
        return redirect(url_for('hello_world'))

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == 'POST':
        nama_lengkap = request.form['NamaLengkap']
        cursor.execute('UPDATE users SET nama_lengkap = %s WHERE id = %s', (nama_lengkap, user_id))
        flash('Profil berhasil diperbarui!', 'success')
    
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('edit_profile.html', user=user_data)

@app.route('/stop_judol', methods=['GET', 'POST'])
def stop_judol():
    if 'user_id' not in session:
        flash('Anda harus login untuk mengakses halaman ini', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    if not conn:
        if request.method == 'POST':
            return jsonify({'sukses': False, 'pesan': 'Database error!'})
        else:
            flash('Database error!', 'error')
            return redirect(url_for('hello_world'))

    if request.method == 'POST':
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            data = request.get_json()
            bet_amount = data.get('bet_amount')

            if not isinstance(bet_amount, int):
                return jsonify({'sukses': False, 'pesan': 'Jumlah taruhan tidak valid.'})
            
            if bet_amount < 10:
                return jsonify({'sukses': False, 'pesan': 'Taruhan minimal adalah 10 poin.'})

            cursor.execute('SELECT poin, judol_losing_streak, judol_bomb_strike_active FROM users WHERE id = %s', (user_id,))
            user = cursor.fetchone()

            if not user:
                return jsonify({'sukses': False, 'pesan': 'User tidak ditemukan.'})

            if user['poin'] < bet_amount:
                return jsonify({'sukses': False, 'pesan': f'Poin Anda ({user["poin"]}) tidak cukup untuk bertaruh {bet_amount} poin.'})

            losing_streak = user['judol_losing_streak']
            bomb_strike_active = user['judol_bomb_strike_active']
            
            jenis_kemenangan = "kalah"
            if bomb_strike_active and random.random() < 0.70:
                jenis_kemenangan = "bom_jackpot"
            elif losing_streak >= 3 and random.random() < 0.40:
                jenis_kemenangan = "normal_jackpot"
            elif random.random() < 0.01:
                 jenis_kemenangan = "bom_jackpot"
            elif random.random() < 0.05: 
                jenis_kemenangan = "13_jackpot"
            elif random.random() < 0.15:
                jenis_kemenangan = "normal_jackpot"
            
            # PERBAIKI: Konsistensi nama file dengan J besar
            simbol_normal = ['Judol1.png', 'Judol2.png', 'Judol4.png', 'Judol6.png']
            hasil_spin = []
            pesan = ""
            
            cursor.execute('UPDATE users SET judol_bomb_strike_active = 0 WHERE id = %s', (user_id,))

            if jenis_kemenangan == "bom_jackpot":
                hasil_spin = ['Judol3.png', 'Judol3.png', 'Judol3.png']
                poin_hilang = math.floor(user['poin'] * 0.5)
                pesan = f"BOOM! Anda kehilangan {poin_hilang} poin. Risiko besar tidak selalu membawa hasil baik."
                cursor.execute('UPDATE users SET poin = poin - %s, judol_losing_streak = 0 WHERE id = %s', (poin_hilang, user_id))
            
            elif jenis_kemenangan == "13_jackpot":
                hasil_spin = ['Judol5.png', 'Judol5.png', 'Judol5.png']
                pesan = "Angka 13... Sesuatu yang buruk akan terjadi."
                cursor.execute('UPDATE users SET poin = poin - %s, judol_losing_streak = 0, judol_bomb_strike_active = 1 WHERE id = %s', (bet_amount, user_id))

            elif jenis_kemenangan == "normal_jackpot":
                simbol_jackpot = random.choice(simbol_normal)
                hasil_spin = [simbol_jackpot, simbol_jackpot, simbol_jackpot]
                poin_didapat = bet_amount * 2 
                pesan = f"Selamat! Anda memenangkan {poin_didapat} poin. Dewi fortuna tersenyum pada mu."
                cursor.execute('UPDATE users SET poin = poin + %s, judol_losing_streak = 0 WHERE id = %s', (poin_didapat, user_id))
            
            else:
                if bet_amount == user['poin']:
                    pesan = f"Anda mempertaruhkan segalanya ({bet_amount} poin) dan kehilangan semuanya. Inilah pelajaran paling pahit dari judi."
                else:
                    pesan = "Sayang sekali, kamu kurang beruntung. Mau Coba lagi? Bandar selalu suka orang yang optimis."
                
                while True:
                    # PERBAIKI: Konsistensi nama file
                    hasil_spin = random.choices(simbol_normal + ['Judol3.png', 'Judol5.png'], k=3, weights=[20,20,20,20,5,5])
                    if not (hasil_spin[0] == hasil_spin[1] == hasil_spin[2]):
                        break
                
                cursor.execute('UPDATE users SET poin = poin - %s, judol_losing_streak = judol_losing_streak + 1 WHERE id = %s', (bet_amount, user_id))

            cursor.execute('SELECT poin FROM users WHERE id = %s', (user_id,))
            user_terbaru = cursor.fetchone()

            return jsonify({
                'sukses': True,
                'hasil_spin': hasil_spin,
                'pesan': pesan, 
                'poin_terbaru': user_terbaru['poin']
            })
            
        except Exception as e:
            print(f"Stop Judol error: {e}")
            return jsonify({'sukses': False, 'pesan': 'Terjadi kesalahan server.'})
        finally:
            cursor.close()
            conn.close()
    else:
        # GET request - tampilkan halaman
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user_data:
            flash('Data user tidak ditemukan!', 'error')
            return redirect(url_for('hello_world'))
            
        return render_template('judol.html', user=user_data)
                    
@app.route("/logout")
def logout():
    session.clear()
    flash('Anda telah berhasil logout.', 'success')
    return redirect(url_for('hello_world'))

# 6. MENJALANKAN APLIKASI
if __name__ == "__main__":
    init_database()
    app.run(debug=True)