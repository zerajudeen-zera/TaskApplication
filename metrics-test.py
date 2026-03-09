from flask import Flask
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
metrics = PrometheusMetrics(app, path="/metrics")

@app.route("/")
def index():
    return "Hello World"

if __name__ == "__main__":
    app.run(port=5000)
