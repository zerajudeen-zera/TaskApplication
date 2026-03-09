<h1>Task Management Flask App</h1>
    A full-stack Flask application with MySQL backend, Dockerized environment, and integrated authentication, observability, and CI/CD pipelines. Designed for secure, scalable deployments on AWS EKS with Terraform-managed infrastructure.

![alt text](https://copilot.microsoft.com/th/id/BCO.04e97351-fcc4-4490-8e75-9b69f432542a.png)

<h1>To Run the application </h1>
    - git clone <repo-url>
    - cd flask-task-app
    - python3 -m venv venv
    - source venv/bin/activate
    - pip install -r requirements.txt
    - flask run

<h1>Features</h1>
    - User authentication (signup, login, session management)
    - CRUD operations for tasks
    - MySQL database integration with migrations
    - RESTful API endpoints
    - Bootstrap-styled UI for responsive design
    - Docker Compose for local development
    - Observability stack: Prometheus, Grafana, Loki, Jaeger, Datadog
    - OpenTelemetry tracing for all CRUD routes
    - Health endpoints (liveness, readiness, unified health checks)

<h1>🔒 Deployment (AWS EKS)</h1>
    - Infrastructure managed via Terraform
    - Database: Amazon RDS MySQL
    - Secrets: AWS Secrets Manager
    - CI/CD pipeline integrates pytest unit/integration tests
    - Security groups dynamically managed for best practices

<h1>📊 Observability</h1>
    - Prometheus: Metrics collection
    - Grafana: Dashboards
    - Loki + Promtail: Log aggregation
    - Jaeger: Distributed tracing
    - Datadog (ddtrace): Unified monitoring
