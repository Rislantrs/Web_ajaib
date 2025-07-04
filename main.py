# 1. IMPOR SEMUA YANG DIBUTUHKAN
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from openai import OpenAI
import random
import math
from datetime import date
import json
import time
from dotenv import load_dotenv
load_dotenv()


client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# 2. INISIALISASI APLIKASI FLASK
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)


def get_db_connection():
    # Path yang benar untuk Vercel adalah /tmp
    db_path = os.path.join('/tmp', 'database.db')

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
def init_database():
    conn = get_db_connection()
    # Perintah SQL untuk membuat tabel users
    # IF NOT EXISTS penting agar tidak error jika tabel sudah ada
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            nama_lengkap TEXT,
            poin INTEGER DEFAULT 0,
            kuis_terakhir_dimainkan TEXT,
            kuis_dimainkan_hari_ini INTEGER DEFAULT 0,
            avatar_style TEXT,
            judol_losing_streak INTEGER DEFAULT 0,
            judol_bomb_strike_active INTEGER DEFAULT 0
        );
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

# 3. FUNGSI AI
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

# 4. FUNGSI BANTU DAN KONFIGURASI
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

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
    # BUAT TOPIK RANDOM UNTUK VARIASI TINGGI
    topik_list = [
        "sejarah Indonesia", "geografi dunia", "sains dan teknologi", 
        "budaya Indonesia", "olahraga", "matematika dasar", 
        "bahasa Indonesia", "biologi",
        "sejarah dunia", "astronomi", "ekonomi", "politik",
        "seni dan musik", "kuliner Indonesia", "flora fauna",
        "negara di dunia", "penemuan bersejarah", "tokoh dunia"
    ]
    
    topik_terpilih = random.sample(topik_list, min(3, len(topik_list)))
    topik_str = ", ".join(topik_terpilih)
    
    # PROMPT DENGAN VARIASI TINGGI
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
            temperature=0.9,  # TINGGI UNTUK VARIASI MAKSIMAL
            max_tokens=2000,
            top_p=0.95       # TAMBAH TOP_P UNTUK VARIASI
        )
        
        ai_response = response.choices[0].message.content.strip()
        print(f"DEBUG: AI Response dengan topik: {topik_str}")
        
        # BERSIHKAN RESPONSE DARI MARKDOWN
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
    
    # SHUFFLE DAN AMBIL SESUAI KEBUTUHAN
    random.shuffle(all_backup)
    return all_backup[:jumlah_soal]

def siapkan_kuis_harian():
    # GUNAKAN WAKTU SEBAGAI SEED UNTUK VARIASI
    random.seed(int(time.time()))
    
    soal_harian = []
    
    # 10% peluang ambil dari JSON (maksimal 1-3 soal)
    if random.randint(1, 100) <= 10:
        try:
            bank_soal_json = muat_soal_json()
            if bank_soal_json:
                jumlah_soal_json = random.randint(1, min(3, len(bank_soal_json)))
                soal_harian.extend(random.sample(bank_soal_json, jumlah_soal_json))
                print(f"DEBUG: Mengambil {jumlah_soal_json} soal dari JSON")
        except Exception as e:
            print(f"DEBUG: Error membaca JSON: {e}")
    
    # Sisa soal dari AI dengan variasi tinggi
    jumlah_soal_ai = 10 - len(soal_harian)
    if jumlah_soal_ai > 0:
        print(f"DEBUG: Membuat {jumlah_soal_ai} soal dari AI")
        soal_ai = generate_kuis_from_ai(jumlah_soal_ai)
        soal_harian.extend(soal_ai)
    
    # Shuffle final untuk acak urutan
    random.shuffle(soal_harian)
    print(f"DEBUG: Total soal final: {len(soal_harian)}")
    return soal_harian[:10]  # PASTIKAN HANYA 10 SOAL

# 5. RUTE-RUTE APLIKASI WEB

@app.route("/")
def hello_world():
    """
    Rute utama: Menampilkan dashboard jika login, atau halaman tamu jika belum.
    """
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_db_connection()
        user_data = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        
        if user_data:
            return render_template('dashboard.html', user=user_data, logged_in=True)
        else:
            session.clear()

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
    user = conn.execute('SELECT kuis_terakhir_dimainkan, kuis_dimainkan_hari_ini FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()

    hari_ini = date.today().isoformat()
    
    # Cek apakah hari berbeda, jika ya reset counter
    if user and user['kuis_terakhir_dimainkan'] != hari_ini:
        conn = get_db_connection()
        conn.execute('UPDATE users SET kuis_dimainkan_hari_ini = 0 WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        print("DEBUG: Reset counter kuis untuk hari baru")
    
    # Ambil data terbaru setelah reset
    conn = get_db_connection()
    user = conn.execute('SELECT kuis_terakhir_dimainkan, kuis_dimainkan_hari_ini FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    
    kuis_dimainkan = user['kuis_dimainkan_hari_ini'] if user else 0
    
    # Cek batas 3x sehari
    if kuis_dimainkan >= 3:
        print(f"DEBUG: User sudah main {kuis_dimainkan}x hari ini")
        flash(f'Anda sudah mengerjakan kuis 3x hari ini ({kuis_dimainkan}/3). Coba lagi besok!', 'warning')
        return redirect(url_for('hello_world'))
    
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
        hari_ini = date.today().isoformat()

        conn = get_db_connection()
        # Update poin
        conn.execute('UPDATE users SET poin = poin + ? WHERE id = ?', (skor_akhir, user_id))
        # Update tanggal terakhir main
        conn.execute('UPDATE users SET kuis_terakhir_dimainkan = ? WHERE id = ?', (hari_ini, user_id))
        # Tambah counter jumlah main hari ini
        conn.execute('UPDATE users SET kuis_dimainkan_hari_ini = kuis_dimainkan_hari_ini + 1 WHERE id = ?', (user_id,))
        conn.commit()
        
        # Ambil jumlah main yang terbaru
        user_data = conn.execute('SELECT kuis_dimainkan_hari_ini FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        
        sisa_main = 3 - user_data['kuis_dimainkan_hari_ini']

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
    user_data = None
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_db_connection()
        user_data = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        if not user_data:
            session.clear()

    return render_template('about.html', Web_title="Halaman About", user=user_data)

@app.route("/docs")
def docs():
    return render_template('docs.html', Web_title="Halaman Docs")

@app.route("/usia", methods=['GET', 'POST'])
def usia():
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
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user_id'] = user['id']
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
        try:
            conn.execute(
                'INSERT INTO users (username, password, nama_lengkap, avatar_style) VALUES (?, ?, ?, ?)',
                (username, hashed_password, nama_lengkap, random_avatar_style)
            )
            conn.commit()
            flash('Pendaftaran berhasil! Silakan login.', 'success')
        except sqlite3.IntegrityError:
            flash('Username sudah terdaftar!', 'error')
            return redirect(url_for('daftar'))
        finally:
            conn.close()
        return redirect(url_for('login'))

    return render_template('daftar.html')

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()

    if request.method == 'POST':
        nama_lengkap = request.form['NamaLengkap']
        conn.execute('UPDATE users SET nama_lengkap = ? WHERE id = ?', (nama_lengkap, user_id))
        conn.commit()
        flash('Profil berhasil diperbarui!', 'success')
    
    user_data = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return render_template('edit_profile.html', user=user_data)

@app.route('/stop_judol', methods=['GET', 'POST'])
def stop_judol():
    if 'user_id' not in session:
        flash('Anda harus login untuk mengakses halaman ini', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()

    if request.method == 'POST':
        # 1. Ambil dan validasi taruhan dari frontend
        data = request.get_json()
        bet_amount = data.get('bet_amount')

        if not isinstance(bet_amount, int):
            conn.close()
            return jsonify({'sukses': False, 'pesan': 'Jumlah taruhan tidak valid.'})
        
        if bet_amount < 10:
            conn.close()
            return jsonify({'sukses': False, 'pesan': 'Taruhan minimal adalah 10 poin.'})

        # 2. Ambil data pengguna dan validasi poin
        user = conn.execute('SELECT poin, judol_losing_streak, judol_bomb_strike_active FROM users WHERE id = ?', (user_id,)).fetchone()

        if user['poin'] < bet_amount:
            conn.close()
            return jsonify({'sukses': False, 'pesan': f'Poin Anda ({user["poin"]}) tidak cukup untuk bertaruh {bet_amount} poin.'})

        # 3. Logika probabilitas dinamis
        losing_streak = user['judol_losing_streak']
        bomb_strike_active = user['judol_bomb_strike_active']
        
        jenis_kemenangan = "kalah" # Default
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
        
        # 4. Logika hasil, hadiah, dan pesan
        simbol_normal = ['judol1.png', 'judol2.png', 'judol4.png', 'judol6.png']
        hasil_spin = []
        pesan = ""
        
        # Reset status bom strike setelah digunakan
        conn.execute('UPDATE users SET judol_bomb_strike_active = 0 WHERE id = ?', (user_id,))

        if jenis_kemenangan == "bom_jackpot":
            hasil_spin = ['judol3.png', 'judol3.png', 'judol3.png']
            poin_hilang = math.floor(user['poin'] * 0.5)
            pesan = f"BOOM! Anda kehilangan {poin_hilang} poin. Risiko besar tidak selalu membawa hasil baik."
            conn.execute('UPDATE users SET poin = poin - ?, judol_losing_streak = 0 WHERE id = ?', (poin_hilang, user_id))
        
        elif jenis_kemenangan == "13_jackpot":
            hasil_spin = ['judol5.png', 'judol5.png', 'judol5.png']
            # PERBAIKAN: Menggunakan pesan yang lebih sesuai dengan logika
            pesan = "Angka 13... Sesuatu yang buruk akan terjadi."
            conn.execute('UPDATE users SET poin = poin - ?, judol_losing_streak = 0, judol_bomb_strike_active = 1 WHERE id = ?', (bet_amount, user_id))

        elif jenis_kemenangan == "normal_jackpot":
            # PERBAIKAN: random.choice(simbol_normal)
            simbol_jackpot = random.choice(simbol_normal)
            hasil_spin = [simbol_jackpot, simbol_jackpot, simbol_jackpot]
            # PERBAIKAN: Hadiah berdasarkan taruhan
            poin_didapat = bet_amount * 2 
            pesan = f"Selamat! Anda memenangkan {poin_didapat} poin. Dewi fortuna tersenyum pada mu."
            conn.execute('UPDATE users SET poin = poin + ?, judol_losing_streak = 0 WHERE id = ?', (poin_didapat, user_id))
        
        else: # Kalah
            # Cek skenario "ALL-IN" dan kalah
            if bet_amount == user['poin']:
                pesan = f"Anda mempertaruhkan segalanya ({bet_amount} poin) dan kehilangan semuanya. Inilah pelajaran paling pahit dari judi."
            else:
                pesan = "Sayang sekali, kamu kurang beruntung. Mau Coba lagi? Bandar selalu suka orang yang optimis."
            
            while True:
                hasil_spin = random.choices(simbol_normal + ['judol3.png', 'judol5.png'], k=3, weights=[20,20,20,20,5,5])
                if not (hasil_spin[0] == hasil_spin[1] == hasil_spin[2]):
                    break
            
            conn.execute('UPDATE users SET poin = poin - ?, judol_losing_streak = judol_losing_streak + 1 WHERE id = ?', (bet_amount, user_id))

        # 5. Ambil data terbaru dan kirim respons JSON
        user_terbaru = conn.execute('SELECT poin FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.commit()
        conn.close()

        return jsonify({
            'sukses': True,
            'hasil_spin': hasil_spin,
            'pesan': pesan, 
            'poin_terbaru': user_terbaru['poin']
        })

    # Tampilan awal halaman (GET request)
    user_data = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return render_template('judol.html', user=user_data)
                    
@app.route("/logout")
def logout():
    session.clear()
    flash('Anda telah berhasil logout.', 'success')
    return redirect(url_for('hello_world'))

# 6. MENJALANKAN APLIKASI
if __name__ == "__main__":
    app.run(debug=True)