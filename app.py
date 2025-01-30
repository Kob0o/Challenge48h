from flask import Flask, render_template, request
import requests
import re
from datetime import datetime, timedelta

# Initialisation de l'application Flask
app = Flask(__name__)

# URLs des sources API
url_passages = 'https://data.lillemetropole.fr/data/ogcapi/collections/ilevia:prochains_passages/items?f=json&limit=-1'
url_perturbations = 'https://data.lillemetropole.fr/data/ogcapi/collections/ilevia:perturbations/items?f=json&limit=-1'
url_lignes = 'https://data.lillemetropole.fr/geoserver/ows?SERVICE=WFS&REQUEST=GetFeature&VERSION=2.0.0&TYPENAMES=dsp_ilevia%3Ailevia_traceslignes&OUTPUTFORMAT=application%2Fjson'

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

def get_json_data(url):
    """Récupère les données JSON depuis une API avec gestion des erreurs"""
    try:
        response = requests.get(url, timeout=10)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"Erreur lors de la récupération des données: {e}")
        return None

@app.route('/')
def home():
    """Route principale - Page d'accueil"""
    return render_template('index.html')

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
                                first_valid_point[0]   # Longitude
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
        perturbations_par_ligne=perturbations_par_ligne,     # Perturbations organisées
        lignes_coordinates=lignes_coordinates,               # Coordonnées géographiques
        current_page=page,                                   # Pagination actuelle
        total_pages=total_pages,                             # Nombre total de pages
        total=total,                                         # Total de résultats
        lignes_uniques=sorted({                              # Liste unique des lignes
            p['code_ligne'] 
            for p in passages_data.get('records', []) 
            if p.get('code_ligne')
        }),
        request_args=request_args                            # Paramètres de filtre
    )

if __name__ == '__main__':
    app.run(debug=True)  # Lancement du serveur en mode debug