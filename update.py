# Buat file update_db.py
import sqlite3

connection = sqlite3.connect('database.db')
cursor = connection.cursor()

# Tambah kolom baru
try:
    cursor.execute('ALTER TABLE users ADD COLUMN judol_losing_streak INTEGER DEFAULT 0')
    cursor.execute('ALTER TABLE users ADD COLUMN judol_bomb_strike_active INTEGER DEFAULT 0')
    print("Kolomb baru berhasil ditambahkan.")
except:
    print("Kolom sudah ada atau error")

cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
print("\nStruktur tabel users:")
for col in columns:
    print(f"- {col[1]} ({col[2]})")

connection.commit()
connection.close()