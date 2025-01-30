from flask import Flask, render_template, jsonify
import requests

app = Flask(__name__)

DATA_URL = "https://data.lillemetropole.fr/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&VERSION=2.0.0&TYPENAMES=dsp_ilevia%3Avlille_temps_reel&OUTPUTFORMAT=application%2Fjson"

@app.route('/')
def index():
    return render_template("vlille.html")

@app.route("/data")
def get_data():
    try:
        response = requests.get(DATA_URL)
        data = response.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(debug=True)

if __name__ == '__main__':
    app.run(debug=True)

