from datetime import datetime, timedelta

import requests
from flask import Flask, render_template, request, redirect, flash, url_for, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'Tudor'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'chall48h'
app.secret_key = os.urandom(24)
mysql = MySQL(app)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'challenge4859170@gmail.com'  # Use your actual Gmail address
app.config['MAIL_PASSWORD'] = 'osky clct qodx uokz'  # Use your generated App Password
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
mail = Mail(app)

# URLs des sources API
url_passages = 'https://data.lillemetropole.fr/data/ogcapi/collections/ilevia:prochains_passages/items?f=json&limit=-1'
url_perturbations = 'https://data.lillemetropole.fr/data/ogcapi/collections/ilevia:perturbations/items?f=json&limit=-1'
url_lignes = 'https://data.lillemetropole.fr/geoserver/ows?SERVICE=WFS&REQUEST=GetFeature&VERSION=2.0.0&TYPENAMES=dsp_ilevia%3Ailevia_traceslignes&OUTPUTFORMAT=application%2Fjson'
url_vlille = "https://data.lillemetropole.fr/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&VERSION=2.0.0&TYPENAMES=dsp_ilevia%3Avlille_temps_reel&OUTPUTFORMAT=application%2Fjson"


def extract_line(line_ref):
    """
    Nettoie et standardise les codes de ligne à partir de différentes notations
    Exemple: 'LineRef::ME63:' devient 'M63'
    """
    patterns = [
        r'LineRef::([A-Z0-9]+):',
        r'LineRef:(\d+):',
        r'LineRef::([A-Z]+\d+)',
        r'([A-Z]+\d+)$'
    ]

    for pattern in patterns:
        match = re.search(pattern, line_ref or '')
        if match:
            code = match.group(1).strip()
            if code.startswith('ME'):
                return code.replace('ME', 'M')  # Conversion spécifique pour les métros
            return code
    return line_ref


app.jinja_env.filters['extract_line'] = extract_line


def check_perturbations():
    with app.app_context():
        try:
            # Récupérer toutes les lignes favorites avec les utilisateurs
            cursor = mysql.connection.cursor()
            cursor.execute('''
                SELECT u.email, f.bus_line_name, f.last_notified 
                FROM user_favorite_bus_lines f
                JOIN users u ON f.user_id = u.id 
                WHERE u.notifications = TRUE
            ''')
            favorites = cursor.fetchall()
            cursor.close()

            # Récupérer les perturbations actuelles
            perturbations_data = get_json_data(url_perturbations)
            current_perturbations = {}
            if perturbations_data and 'records' in perturbations_data:
                for pert in perturbations_data['records']:
                    ligne = extract_line(pert.get('cible', ''))
                    if ligne:
                        current_perturbations[ligne] = pert

            # Vérifier chaque ligne favorite
            for fav in favorites:
                email, ligne, last_notified = fav
                pert = current_perturbations.get(ligne)

                if pert:
                    # Vérifier si la perturbation est nouvelle
                    pert_date = datetime.fromisoformat(pert['date_modification'])
                    if not last_notified or pert_date > last_notified:
                        send_perturbation_alert(email, ligne, pert)

                        # Mettre à jour last_notified
                        cursor = mysql.connection.cursor()
                        cursor.execute('''
                            UPDATE user_favorite_bus_lines 
                            SET last_notified = NOW() 
                            WHERE bus_line_name = %s
                        ''', (ligne,))
                        mysql.connection.commit()
                        cursor.close()

        except Exception as e:
            print(f"Erreur dans la vérification des perturbations: {e}")


def send_perturbation_alert(email, ligne, perturbation):
    try:
        msg = Message(
            subject=f"Perturbation sur la ligne {ligne}",
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )
        msg.body = f'''
        Alerte perturbation : {perturbation.get('type_perturbation')}

        Message : {perturbation.get('message')}

        Début : {perturbation.get('date_modification')}
        Fin prévue : {perturbation.get('heure_fin_prevue')}
        '''
        mail.send(msg)
        print(f"Email envoyé à {email}")
    except Exception as e:
        print(f"Erreur d'envoi d'email: {e}")


# Planificateur pour vérifier toutes les 5 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_perturbations, trigger="interval", minutes=5)
scheduler.start()

favorites = [
    {"id": 1, "name": "Ligne 1", "status": "Normal"},
    {"id": 2, "name": "Ligne 2", "status": "Retard"},
]

perturbations = [
    {"id": 1, "line": "Ligne 2", "message": "Incident technique - retard de 15 min"},
    {"id": 2, "line": "Ligne 3", "message": "Travaux en cours - ligne perturbée"},
]


def get_json_data(url):
    """Récupère les données JSON depuis une API avec gestion des erreurs"""
    try:
        response = requests.get(url, timeout=10)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"Erreur lors de la récupération des données: {e}")
        return None


@app.route('/velo')
def velo():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    search_query = request.args.get('search', '').lower()

    try:
        response = requests.get(url_vlille)
        data = response.json()
        all_stations = data.get('features', [])
    except Exception as e:
        print(f"Erreur de récupération des données : {e}")
        all_stations = []

    # Récupération des paramètres de filtre
    request_args = request.args.to_dict()
    request_args.pop('page', None)
    # Filtrage par recherche
    filtered_stations = [
        s for s in all_stations
        if search_query in s['properties']['nom'].lower()
    ]

    # Pagination
    total = len(filtered_stations)

    # Calcul de la pagination
    total = len(filtered_stations)
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page

    return render_template('vlille.html',
                           stations=filtered_stations[start:end],
                           all_stations=all_stations,
                           current_page=page,
                           total_pages=total_pages,
                           total=total,
                           per_page=per_page,
                           request_args=request_args
                           )


@app.route('/')
def index():
    if 'username' not in session:
        return redirect("/signup")
    return redirect("/home")


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

    cursor.execute("INSERT INTO users (username, email, hashed_password, notifications) VALUES (%s, %s, %s, false)",
                   (username, email, hashed_password))
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


def get_user_favorites(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute(
        "SELECT bus_line_name FROM user_favorite_bus_lines WHERE user_id = %s",
        (user_id,)
    )
    favorites = cursor.fetchall()
    cursor.close()
    return [favorite[0] for favorite in favorites]


@app.route('/home')
def home():
    """Route pour la page d'accueil avec les lignes pref"""
    if 'username' not in session:
        flash('You must be logged in to view this page.', 'danger')
        return redirect('/login')

    username = session['username']
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()

    if not user:
        flash('User not found.', 'danger')
        return redirect('/login')

    user_id = user[0]

    cursor = mysql.connection.cursor()
    velo = mysql.connection.cursor()
    cursor.execute(
        "SELECT bus_line_name FROM user_favorite_bus_lines WHERE user_id = %s",
        (user_id,)
    )
    velo.execute("SELECT station_name FROM user_favorite_velos_stations WHERE user_id = %s", (user_id,))
    favorite_stations = velo.fetchall()
    favorite_bus_lines = cursor.fetchall()
    cursor.close()
    velo.close()

    print(f"Favorite Bus Lines: {favorite_bus_lines}")

    favorites = [line[0] for line in favorite_bus_lines]
    velos = [line[0] for line in favorite_stations]
    print(f"Favorites List: {favorites}")

    return render_template("index.html", favorites=favorites, velos=velos)


@app.route('/bus')
def passages():
    """Route principale pour les passages de bus"""
    # Gestion de la pagination
    page = request.args.get('page', 1, type=int)
    per_page = 5

    # Récupération des paramètres de filtre
    request_args = request.args.to_dict()
    request_args.pop('page', None)  # Suppression du paramètre de pagination

    # Récupération des données externes
    passages_data = get_json_data(url_passages)  # Prochains passages
    perturbations_data = get_json_data(url_perturbations)  # Perturbations
    lignes_data = get_json_data(url_lignes)  # Géolocalisation des lignes

    # Traitement des perturbations par ligne
    perturbations_par_ligne = {}
    if perturbations_data and 'records' in perturbations_data:
        for pert in perturbations_data['records']:
            ligne_code = extract_line(pert.get('cible', ''))
            if ligne_code:
                perturbations_par_ligne.setdefault(ligne_code, []).append(pert)

    # Extraction des coordonnées géographiques des lignes
    lignes_coordinates = {}
    if lignes_data and 'features' in lignes_data:
        for feature in lignes_data['features']:
            props = feature.get('properties', {})
            geometry = feature.get('geometry', {})

            if geometry.get('type') == 'LineString':
                coords = geometry.get('coordinates', [])
                if coords:
                    # Récupération du premier point valide de la ligne
                    first_valid_point = next(
                        (point for point in coords if len(point) >= 2),
                        None
                    )
                    if first_valid_point:
                        ligne_code = props.get('ligne', '')
                        if ligne_code and ligne_code not in lignes_coordinates:
                            # Stockage des coordonnées inversées (lat, lon)
                            lignes_coordinates[ligne_code] = [
                                first_valid_point[1],  # Latitude
                                first_valid_point[0]  # Longitude
                            ]

    # Filtrage des passages selon les critères utilisateur
    filtered_passages = []
    if passages_data and 'records' in passages_data:
        ligne_filter = request.args.get('ligne')
        perturbation_filter = request.args.get('perturbation')
        heure_filter = request.args.get('heure')

        for passage in passages_data['records']:
            ligne_code = passage.get('code_ligne', '')

            # Filtre par ligne
            if ligne_filter and ligne_code != ligne_filter:
                continue

            # Filtre par perturbation
            has_perturbation = ligne_code in perturbations_par_ligne
            if perturbation_filter == 'oui' and not has_perturbation:
                continue
            if perturbation_filter == 'non' and has_perturbation:
                continue

            # Filtre temporel
            if heure_filter:
                try:
                    heure_passage = datetime.fromisoformat(passage.get('heure_estimee_depart', ''))
                    now = datetime.now()
                    delta = heure_passage - now

                    if heure_filter == '1h' and delta > timedelta(hours=1):
                        continue
                    elif heure_filter == '3h' and delta > timedelta(hours=3):
                        continue
                    elif heure_filter == 'today' and heure_passage.date() != now.date():
                        continue
                except:
                    continue

            filtered_passages.append(passage)

    # Calcul de la pagination
    total = len(filtered_passages)
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page

    # Rendu du template avec toutes les données
    return render_template('bus.html',
                           passages={'records': filtered_passages[start:end]},  # Passages paginés
                           perturbations_par_ligne=perturbations_par_ligne,  # Perturbations organisées
                           lignes_coordinates=lignes_coordinates,  # Coordonnées géographiques
                           current_page=page,  # Pagination actuelle
                           total_pages=total_pages,  # Nombre total de pages
                           total=total,  # Total de résultats
                           lignes_uniques=sorted({  # Liste unique des lignes
                               p['code_ligne']
                               for p in passages_data.get('records', [])
                               if p.get('code_ligne')
                           }),
                           request_args=request_args  # Paramètres de filtre
                           )


@app.route('/ajouter-aux-favoris', methods=["POST"])
def ajouter_aux_favoris():
    data = request.form
    ligne = data['ligne']
    username = session["username"]

    cursor = mysql.connection.cursor()
    try:
        # Récupérer l'utilisateur
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user:
            return "Utilisateur non trouvé"

        user_id = user[0]

        # Vérifier si la ligne existe déjà
        cursor.execute('''
            SELECT * FROM user_favorite_bus_lines 
            WHERE user_id = %s AND bus_line_name = %s
        ''', (user_id, ligne))
        if cursor.fetchone():
            flash('Cette ligne est déjà dans vos favoris', 'warning')
            return redirect("/bus")

        # Ajouter la nouvelle ligne
        cursor.execute('''
            INSERT INTO user_favorite_bus_lines (user_id, bus_line_name, last_notified) 
            VALUES (%s, %s, NULL)
        ''', (user_id, ligne))
        mysql.connection.commit()

        flash('Ligne ajoutée aux favoris avec notifications', 'success')

    except Exception as e:
        mysql.connection.rollback()
        print(f"Erreur: {e}")
        flash("Une erreur s'est produite", 'danger')
    finally:
        cursor.close()

    return redirect("/bus")


@app.route('/ajouter-velos-aux-favoris', methods=["POST"])
def ajouter_velos_aux_favoris():
    data = request.form
    station = data['station']
    username = session["username"]

    cursor = mysql.connection.cursor()
    try:
        # Récupérer l'utilisateur
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user:
            return "Utilisateur non trouvé"

        user_id = user[0]

        cursor.execute("INSERT INTO user_favorite_velos_stations (user_id, station_name)", (user_id, station))

    except Exception as e:
        mysql.connection.rollback()
        print(f"Erreur: {e}")
        flash("Une erreur s'est produite", 'danger')
    finally:
        cursor.close()

    return redirect("/velo")


@app.route("/api/favorites")
def get_favorites():
    return jsonify(favorites)


@app.route("/api/perturbations")
def get_perturbations():
    return jsonify(perturbations)


if __name__ == '__main__':
    app.run(debug=True)