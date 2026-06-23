# PoC Plan: MuckScraper

## Project Classification
- **Type:** web-app (Flask web application with AI-powered news processing)
- **Key Technologies:** Python 3.10, Flask, PostgreSQL+pgvector, Meilisearch, Ollama LLM, Playwright, Gunicorn
- **ODH Relevance:** Demonstrates AI-powered content processing pipeline on OpenShift, relevant to agentic AI and LLM application deployment

## PoC Objectives
1. Containerize the MuckScraper Flask web application with a UBI-based image
2. Deploy with PostgreSQL+pgvector sidecar on OpenShift
3. Validate the web UI serves correctly in a containerized environment
4. Demonstrate database migrations run successfully

## Infrastructure Requirements
- **Resource Profile:** medium (1Gi RAM, 500m CPU for the web app)
- **GPU Required:** No
- **Persistent Storage:** 1Gi PVC for PostgreSQL data
- **Sidecar Containers:** PostgreSQL 14 with pgvector extension
- **Deployment Model:** Deployment (long-running web service)
- **LLM API Required:** No (skip Ollama for initial PoC; web UI works without it)

## PoC Components
For this PoC, we focus on the **web** component only (not the scheduler) to validate containerization and web UI serving. The scheduler requires News API keys and Ollama which add unnecessary complexity for initial validation.

## Test Scenarios

### Scenario 1: health-check
- **Description:** Verify the Flask web app responds on port 8080
- **Type:** http
- **Endpoint:** /
- **Expected:** HTTP 200 or 302 (redirect to login)
- **Timeout:** 60 seconds

### Scenario 2: login-page
- **Description:** Verify the login page renders correctly
- **Type:** http
- **Endpoint:** /auth/login
- **Expected:** HTTP 200 with HTML containing "login" form
- **Timeout:** 30 seconds

### Scenario 3: static-assets
- **Description:** Verify static assets are served
- **Type:** http
- **Endpoint:** /static/css/style.css
- **Expected:** HTTP 200 with CSS content
- **Timeout:** 30 seconds

## Dockerfile Considerations
- Convert from python:3.10-slim to UBI9 Python 3.12
- Skip Playwright installation (not needed for web serving, only for article scraping)
- Install PostgreSQL client libraries via dnf
- Port 5000 -> 8080 (OpenShift unprivileged port)
- Run database migrations in entrypoint before starting gunicorn

## Deployment Considerations
- Web app as Deployment with Service on port 8080
- PostgreSQL as StatefulSet with PVC, or use a simple Deployment for PoC
- ConfigMap for non-sensitive environment variables
- Secret for database credentials
- InitContainer or entrypoint script for database migration
