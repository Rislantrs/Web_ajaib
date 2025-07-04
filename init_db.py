import sqlite3

# Membuat koneksi ke database. File ini akan dibuat jika belum ada.
connection = sqlite3.connect('database.db')
cursor = connection.cursor()

# Menghapus tabel 'users' jika sudah ada, untuk memastikan skema baru yang bersih
cursor.execute('DROP TABLE IF EXISTS users')

# Membuat tabel 'users' dengan semua kolom yang kita butuhkan
cursor.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        nama_lengkap TEXT,
        poin INTEGER DEFAULT 0,
        avatar_style TEXT,
        kuis_terakhir_dimainkan TEXT, 
    )
''')

# Menyimpan perubahan dan menutup koneksi
connection.commit()
connection.close()

print("DATABASE BARU DENGAN SKEMA YANG BENAR TELAH DIBUAT.")
