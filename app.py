from flask import Flask, render_template, request, redirect, flash, url_for, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import os


app = Flask(__name__)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'Tudor'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'chall48h'
app.secret_key = os.urandom(24)
mysql = MySQL(app)

favorites = [
    {"id": 1, "name": "Ligne 1", "status": "Normal"},
    {"id": 2, "name": "Ligne 2", "status": "Retard"},
]

perturbations = [
    {"id": 1, "line": "Ligne 2", "message": "Incident technique - retard de 15 min"},
    {"id": 2, "line": "Ligne 3", "message": "Travaux en cours - ligne perturbée"},
]


@app.route('/')
def index():
    if 'username' in session:
        return redirect("/home")
    return redirect("/signup")

@app.route('/signup', methods=["GET"])
def signup():
    return render_template("signup.html")


@app.route('/signup-check', methods=["POST"])
def check_signup():
    if request.method != "POST":
        return "Mauvaise methode"
    data = request.form

    username = data['username']
    email = data['email']
    password = data['password']
    hashed_password = generate_password_hash(password)
    cursor = mysql.connection.cursor()

    cursor.execute("INSERT INTO users (username, email, hashed_password, notifications) VALUES (%s, %s, %s, false)", (username, email, hashed_password))
    mysql.connection.commit()
    cursor.close()
    print(f"Username: {username}, Email: {email}, Password: {password}")

    return redirect("/login")


@app.route('/login')
def login():
    return render_template("login.html")

@app.route('/login-check', methods=["POST"])
def login_check():
    data = request.form

    username = data['username']
    password = data['password']

    cursor = mysql.connection.cursor()

    cursor.execute("SELECT hashed_password FROM users WHERE username = %s", (username,))
    stored_password = cursor.fetchone()

    if stored_password is None:
        flash('cet user n\'existe pas', 'danger')
        return redirect(url_for('login'))

    if check_password_hash(stored_password[0], password):
        session['username'] = username
        flash('Login successful!', 'success')
        return redirect("/home")
    else:
        flash('Incorrect password!', 'danger')
        return redirect("/login")


@app.route('/home')
def home():
    return render_template("index.html")

@app.route("/api/favorites")
def get_favorites():
    return jsonify(favorites)

@app.route("/api/perturbations")
def get_perturbations():
    return jsonify(perturbations)

if __name__ == '__main__':
    app.run(debug=True)
