from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

url_vlille = "https://data.lillemetropole.fr/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&VERSION=2.0.0&TYPENAMES=dsp_ilevia%3Avlille_temps_reel&OUTPUTFORMAT=application%2Fjson"

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

    #Récupération des paramètres de filtre
    request_args = request.args.to_dict()
    request_args.pop('page', None)
    # Filtrage par recherche
    filtered_stations = [
        s for s in all_stations 
        if search_query in s['properties']['nom'].lower()
    ]

    # Pagination
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

if __name__ == '__main__':
    app.run(debug=True)