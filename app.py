from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import joblib
import numpy as np
from tensorflow.keras.models import load_model
import os
# TAMBAHAN PENTING: Library keamanan password
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_sertifikasi'

# --- KONFIGURASI DATABASE ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'db_emas'
}

# --- LOAD MODEL & SCALER (PERBAIKAN PATH) ---
# Menggunakan Relative Path agar Dinamis (Bisa jalan di komputer mana saja)
# Logikanya: Cari folder dimana app.py berada -> masuk folder 'model' -> ambil file
base_dir = os.path.dirname(os.path.abspath(__file__))
model_dir = os.path.join(base_dir, 'model')

path_model = os.path.join(model_dir, 'model_gru.h5')
path_scaler_x = os.path.join(model_dir, 'scaler_X.save')
path_scaler_y = os.path.join(model_dir, 'scaler_y.save')

model = None
scaler_X = None
scaler_y = None

try:
    if os.path.exists(path_model):
        model = load_model(path_model, compile=False)
        print(f"✅ SUKSES: Model dimuat dari {path_model}")
    else:
        print(f"❌ ERROR: File model tidak ditemukan di {path_model}")
    
    if os.path.exists(path_scaler_x):
        scaler_X = joblib.load(path_scaler_x)
        print("✅ SUKSES: Scaler X dimuat.")

    if os.path.exists(path_scaler_y):
        scaler_y = joblib.load(path_scaler_y)
        print("✅ SUKSES: Scaler Y dimuat.")
        
except Exception as e:
    print(f"⚠️ SISTEM ERROR: {e}")

# --- HELPER FUNCTIONS (ALGORITMA MANUAL) ---
def bubble_sort_manual(data_list):
    n = len(data_list)
    for i in range(n):
        for j in range(0, n-i-1):
            if data_list[j]['price'] > data_list[j+1]['price']:
                data_list[j], data_list[j+1] = data_list[j+1], data_list[j]
    return data_list

def linear_search_manual(data_list, target_price):
    for item in data_list:
        if item['price'] == target_price:
            return True
    return False

# --- ROUTES ---

@app.route('/')
def index():
    if 'loggedin' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# FITUR LOGIN (DENGAN KEAMANAN)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Ambil data user berdasarkan username saja
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        account = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # Cek apakah user ada DAN password cocok (hash)
        if account and check_password_hash(account['password'], password):
            session['loggedin'] = True
            session['username'] = account['username']
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau Password salah!', 'danger')
            
    return render_template('login.html')

# FITUR REGISTER (DENGAN KEAMANAN)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        try:
            # Enkripsi Password sebelum disimpan
            hashed_password = generate_password_hash(password)
            
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
            conn.commit()
            flash('Registrasi berhasil! Silakan login.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Username sudah digunakan, coba yang lain.', 'danger')
        except Exception as e:
            flash(f'Terjadi kesalahan: {e}', 'danger')
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
                
    return render_template('register.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'loggedin' not in session: return redirect(url_for('login'))
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # Ambil data dengan nama kolom yang baru (date, price, dll)
    cursor.execute("SELECT * FROM gold_prices ORDER BY date DESC LIMIT 50")
    data_emas = cursor.fetchall()
    
    msg = ""
    
    if request.method == 'POST':
        # Fitur Sorting Manual
        if 'btn_sort' in request.form:
            data_emas = bubble_sort_manual(data_emas)
            msg = "Data berhasil diurutkan berdasarkan Harga (Price)!"
        
        # Fitur Searching Manual
        elif 'btn_search' in request.form:
            try:
                cari = float(request.form['keyword'])
                found = linear_search_manual(data_emas, cari)
                msg = f"Harga ${cari}: {'DITEMUKAN' if found else 'TIDAK ADA'} dalam 50 data terakhir."
            except ValueError:
                msg = "Input pencarian harus berupa angka."

    cursor.close()
    conn.close()
    
    return render_template('dashboard.html', data=data_emas, msg=msg)

@app.route('/tambah_data', methods=['POST'])
def tambah_data():
    if 'loggedin' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        tgl = request.form['tanggal']
        harga = request.form['harga']
        
        # Logic sederhana: Jika user hanya input harga, kita samakan nilai OHLC
        # Ini mencegah error database karena kolom Open/High/Low tidak boleh kosong
        open_p = harga
        high_p = harga
        low_p = harga
        vol = 0
        change_p = 0.0
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        query = "INSERT INTO gold_prices (date, price, open, high, low, vol, change_percent) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        cursor.execute(query, (tgl, harga, open_p, high_p, low_p, vol, change_p))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Data berhasil ditambahkan ke database!', 'success')
        return redirect(url_for('dashboard'))

@app.route('/prediksi_form', methods=['GET', 'POST'])
def prediksi_form():
    if 'loggedin' not in session: return redirect(url_for('login'))
    
    hasil_prediksi = None
    error_msg = None
    
    if request.method == 'POST':
        try:
            # Validasi input agar tidak error jika kosong
            if not request.form['open'] or not request.form['high'] or not request.form['low']:
                raise ValueError("Semua kolom harus diisi!")

            open_p = float(request.form['open'])
            high_p = float(request.form['high'])
            low_p = float(request.form['low'])
            
            if model is None:
                raise Exception("Model AI belum dimuat. Cek path file .h5")

            # Preprocessing AI
            input_data = np.array([[open_p, high_p, low_p]])
            input_scaled = scaler_X.transform(input_data)
            
            # Reshaping dinamis sesuai input shape model
            time_steps = model.input_shape[1] 
            features = model.input_shape[2] 
            
            dummy_history = np.zeros((time_steps - 1, features))
            X_sequence = np.vstack([dummy_history, input_scaled])
            X_sequence = X_sequence.reshape(1, time_steps, features)
            
            # Prediksi
            y_pred_scaled = model.predict(X_sequence)
            
            # Inverse Transform
            placeholder = np.zeros((1, 1))
            placeholder[0, 0] = y_pred_scaled.flatten()[0]
            predicted_price = scaler_y.inverse_transform(placeholder)[0, 0]
            
            hasil_prediksi = f"${predicted_price:,.2f}"
            
        except Exception as e:
            error_msg = f"Gagal Memprediksi: {str(e)}"
            print(error_msg)

    return render_template('prediksi.html', hasil=hasil_prediksi, error=error_msg)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)