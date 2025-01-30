from flask import Flask, render_template, request
import requests
import re
from datetime import datetime, timedelta

app = Flask(__name__)

url_passages = 'https://data.lillemetropole.fr/data/ogcapi/collections/ilevia:prochains_passages/items?f=json&limit=-1'
url_perturbations = 'https://data.lillemetropole.fr/data/ogcapi/collections/ilevia:perturbations/items?f=json&limit=-1'

def extract_line(line_ref):
    """ Extrait uniquement le code de la ligne réelle depuis les formats variés """
    if line_ref:
        # On supprime tout ce qui est avant 'LineRef:'
        match = re.search(r'LineRef:(?::)?([A-Za-z0-9]+)', line_ref)
        if match:
            return match.group(1).strip()  # Retourne uniquement la ligne réelle
    return line_ref  # Retourne la valeur originale si non valide

# Enregistre le filtre Jinja2
app.jinja_env.filters['extract_line'] = extract_line

# Fonction pour récupérer les données JSON depuis l'URL
def get_json_data(url):
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/bus', methods=['GET', 'POST'])
def passages():
    
    # Paramètres de pagination
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Récupération des données
    passages_data = get_json_data(url_passages)
    perturbations_data = get_json_data(url_perturbations)
    
    # Traitement des perturbations
    perturbations_par_ligne = {}
    if perturbations_data and 'records' in perturbations_data:
        for pert in perturbations_data['records']:
            ligne_clean = extract_line(pert['cible'])
            if ligne_clean not in perturbations_par_ligne:
                perturbations_par_ligne[ligne_clean] = []
            perturbations_par_ligne[ligne_clean].append(pert)
    
    # Filtrage des données
    filtered_passages = []
    if passages_data and 'records' in passages_data:
        # Récupération des paramètres de filtre
        ligne_filter = request.args.get('ligne')
        perturbation_filter = request.args.get('perturbation')
        heure_filter = request.args.get('heure')
        
        # Application des filtres
        for passage in passages_data['records']:
            # Filtre par ligne
            if ligne_filter and passage['code_ligne'] != ligne_filter:
                continue
                
            # Filtre par perturbation
            has_perturbation = passage['code_ligne'] in perturbations_par_ligne
            if perturbation_filter == 'oui' and not has_perturbation:
                continue
            if perturbation_filter == 'non' and has_perturbation:
                continue
                
            # Filtre par heure
            if heure_filter:
                heure_passage = datetime.fromisoformat(passage['heure_estimee_depart'])
                now = datetime.now()
                if heure_filter == '1h' and (heure_passage - now) > timedelta(hours=1):
                    continue
                elif heure_filter == '3h' and (heure_passage - now) > timedelta(hours=3):
                    continue
                elif heure_filter == 'today' and heure_passage.date() != now.date():
                    continue
            
            filtered_passages.append(passage)
    
    # Pagination
    total = len(filtered_passages)
    start = (page - 1) * per_page
    end = start + per_page
    passages_pagines = filtered_passages[start:end]
    total_pages = (total + per_page - 1) // per_page
    
    # Liste des lignes uniques pour le filtre
    lignes_uniques = sorted({p['code_ligne'] for p in filtered_passages})
    
    return render_template('bus.html', 
                     passages={'records': passages_pagines},
                     perturbations_par_ligne=perturbations_par_ligne,
                     current_page=page,  # Changé ici
                     total_pages=total_pages,
                     total=total,
                     lignes_uniques=lignes_uniques)


if __name__ == '__main__':
    app.run(debug=True)