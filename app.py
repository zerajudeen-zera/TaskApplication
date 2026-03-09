import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import mysql.connector
import bcrypt
from prometheus_flask_exporter import PrometheusMetrics
import logging
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.mysql import MySQLInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from ddtrace import patch, tracer

load_dotenv()

logging.basicConfig(level=logging.INFO)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

logger.info("flask_app_started", port=5000)

patch(flask=True)

app = Flask(__name__)
app.secret_key = "supersecretkey"  # replace with env variable in production

metrics = PrometheusMetrics(app, path="/metrics")
metrics.info("flask_app", "Flask App with Prometheus", version="1.0.0")
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

metrics.register_default(
    metrics.counter(
        'skip_auth_requests', 'Requests that skip authentication',
        labels={'endpoint': lambda: request.endpoint}
    )
)

RequestsInstrumentor().instrument()

MySQLInstrumentor().instrument()

tracer = trace.get_tracer(__name__)

resource = Resource.create({"service.name": "flaskapp"})

trace.set_tracer_provider(TracerProvider(resource=resource))

#jaeger exporter config
otlp_exporter = OTLPSpanExporter(endpoint="http://jaeger.monitoring.svc.cluster.local:4318/v1/traces")  # adjust for EKS/ADOT
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

FlaskInstrumentor().instrument_app(app)



def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE")
    )

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

@app.route("/health", methods=["GET"])
def health():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")   # simple test query
        cursor.fetchone()            # consume the result
        cursor.close()
        conn.close()
        return {"status": "UP", "database": "UP"}, 200
    except Exception as e:
        return {"status": "DOWN", "database": f"ERROR: {str(e)}"}, 500

    

@app.route("/healthz", methods=["GET"])
def liveness():
    return {"status": "ALIVE"}, 200

@app.route("/readyz", methods=["GET"])
def readiness():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        _ = cursor.fetchone()   # consume the result
        cursor.close()
        conn.close()
        return {"status": "READY"}, 200
    except Exception as e:
        return {"status": "NOT READY", "error": str(e)}, 500



@app.route("/metrics")
def metrics_endpoint():
    return app.response_class(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return User(user["id"], user["username"], user["password"])
    return None

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "myappdb")
    )

@app.route("/")
@login_required
def index():
    with tracer.start_as_current_span("db.select_tasks"):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, completed FROM tasks WHERE user_id = %s", (current_user.id,))
        rows = cursor.fetchall()
        # Normalize completed column to int (0 or 1)
        tasks = [(row[0], row[1], int(row[2])) for row in rows]
        cursor.close()
        conn.close()
    return render_template("index.html", tasks=tasks)

@app.route("/add", methods=["POST"])
@login_required
def add_task():
    task_name = request.form["task"]
    with tracer.start_as_current_span("db.insert_task") as span:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (name, user_id, completed) VALUES (%s, %s, %s)",
            (task_name, current_user.id, 0)
        )
        conn.commit()
        cursor.close()
        conn.close()
        span.set_attribute("db.operation", "INSERT")
        span.set_attribute("db.table", "tasks")
        span.set_attribute("task.name", task_name)
        span.set_attribute("task.user_id", current_user.id)

    flash("Task added successfully!", "success")
    return redirect(url_for("index"))


@app.route("/toggle/<int:id>", methods=["POST"])
@login_required
def toggle_task(id):
    with tracer.start_as_current_span("db.toggle_task") as span:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET completed = NOT completed WHERE id = %s AND user_id = %s",
            (id, current_user.id)
        )
        conn.commit()
        cursor.close()
        conn.close()

        # Add attributes for richer context in Jaeger
        span.set_attribute("db.operation", "UPDATE")
        span.set_attribute("db.table", "tasks")
        span.set_attribute("task.id", id)
        span.set_attribute("task.user_id", current_user.id)

    flash("Task status updated!", "info")
    return redirect(url_for("index"))


@app.route("/delete/<int:id>")
@login_required
def delete_task(id):
    with tracer.start_as_current_span("db.delete_task") as span:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = %s", (id,))
        conn.commit()
        cursor.close()
        conn.close()
        span.set_attribute("db.operation", "DELETE")
        span.set_attribute("db.table", "tasks")
        span.set_attribute("task.id", id)
    flash("Deleted successfully!", "success")
    return redirect("/")

@app.route("/update/<int:id>", methods=["GET", "POST"])
@login_required
def update_task(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Span for SELECT
    with tracer.start_as_current_span("db.select_task") as span:
        cursor.execute("SELECT * FROM tasks WHERE id = %s AND user_id = %s", (id, current_user.id))
        task = cursor.fetchone()
        span.set_attribute("db.operation", "SELECT")
        span.set_attribute("db.table", "tasks")
        span.set_attribute("task.id", id)

    if not task:
        cursor.close()
        conn.close()
        flash("Task not found or unauthorized.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        new_name = request.form["task"]
        # Span for UPDATE
        with tracer.start_as_current_span("db.update_task") as span:
            cursor.execute("UPDATE tasks SET name = %s WHERE id = %s AND user_id = %s",
                           (new_name, id, current_user.id))
            conn.commit()
            span.set_attribute("db.operation", "UPDATE")
            span.set_attribute("db.table", "tasks")
            span.set_attribute("task.id", id)
            span.set_attribute("task.new_name", new_name)

        flash("Task updated successfully!", "success")
        cursor.close()
        conn.close()
        return redirect(url_for("index"))

    cursor.close()
    conn.close()
    return render_template("update.html", task=task)

    
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"].encode("utf-8")
        hashed = bcrypt.hashpw(password, bcrypt.gensalt()).decode("utf-8")

        try:
            with tracer.start_as_current_span("db.insert_user") as span:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, password) VALUES (%s, %s)",
                    (username, hashed)
                )
                conn.commit()
                cursor.close()
                conn.close()

                # Add attributes for richer context in Jaeger
                span.set_attribute("db.operation", "INSERT")
                span.set_attribute("db.table", "users")
                span.set_attribute("user.username", username)

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))

        except Exception as e:
            # Optional: record error in span
            with tracer.start_as_current_span("db.insert_user_error") as span:
                span.set_attribute("error", str(e))
                span.set_attribute("user.username", username)

            flash("Username already exists. Try another.", "error")
            return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"].encode("utf-8")

        # Span for SELECT query
        with tracer.start_as_current_span("db.select_user") as span:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            span.set_attribute("db.operation", "SELECT")
            span.set_attribute("db.table", "users")
            span.set_attribute("user.username", username)

        if user:
            # Span for password check
            with tracer.start_as_current_span("auth.password_check") as span:
                valid = bcrypt.checkpw(password, user["password"].encode("utf-8"))
                span.set_attribute("auth.username", username)
                span.set_attribute("auth.success", valid)

            if valid:
                login_user(User(user["id"], user["username"], user["password"]))
                flash("Login successful!", "success")
                return redirect(url_for("index"))

        flash("Login failed. User not found or wrong password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)