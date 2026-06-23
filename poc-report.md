# PoC Report: MuckScraper

## 1. Executive Summary

**MuckScraper**, a self-hosted AI-powered news aggregator by grregis, was successfully containerized with a UBI-based image and deployed on OpenShift with PostgreSQL. All 3 test scenarios passed: the Flask web application serves the login page, handles routing correctly, and delivers static assets. The PoC validates that the core web application runs in a containerized OpenShift environment, with the AI features (Ollama-based summarization, bias scoring, story clustering) available as future enhancements.

## 2. Project Analysis

- **Repository:** [https://github.com/grregis/MuckScraper](https://github.com/grregis/MuckScraper)
- **Fork:** [https://github.com/aicatalyst-team/MuckScraper](https://github.com/aicatalyst-team/MuckScraper)
- **Description:** Self-hosted news aggregator that pulls articles from multiple sources, groups them into stories using pgvector embeddings, scores outlet bias, and generates AI summaries using Ollama.
- **Classification:** Web Application with AI features

| Component | Language | Build System | ML Workload | Port |
|-----------|----------|-------------|-------------|------|
| web | Python 3.12 | pip | No | 8080 |
| scheduler | Python 3.12 | pip | No | None |

## 3. Pipeline Execution

- **Intake:** Identified 2 components (web + scheduler). Docker Compose setup with PostgreSQL, Meilisearch, Ollama dependencies.
- **Evaluate:** RHOAI fitness score with strong demo potential (16/20). Heavy dependency profile is the main risk.
- **Fork:** Forked to [aicatalyst-team/MuckScraper](https://github.com/aicatalyst-team/MuckScraper).
- **PoC Plan:** Focus on web component only. Skip scheduler, Meilisearch, and Ollama for initial validation.
- **Containerize:** Created Dockerfile.ubi with UBI9 Python 3.12, excluding Playwright (not needed for web serving).
- **Build:** Built successfully on OpenShift internal registry. One retry needed (COPY with shell redirect syntax).
- **Deploy:** PostgreSQL deployed with Red Hat RHEL9 PostgreSQL 16 image. MuckScraper web as Deployment with Service.
- **Apply:** All resources deployed in autopoc-test-builds namespace.
- **PoC Execute:** 3/3 test scenarios passed.

## 4. Test Results

| Scenario | Status | HTTP Code | Details |
|----------|--------|-----------|---------|
| Health Check (/) | PASS | 302 | Correctly redirects to login page |
| Login Page (/auth/login) | PASS | 200 | Renders HTML with login form, dark mode support |
| Static CSS (/static/css/style.css) | PASS | 200 | Static assets served correctly |

**Pass Rate: 100% (3/3)**

## 5. Infrastructure Deployed

- **Namespace:** autopoc-test-builds
- **Container Image:** image-registry.openshift-image-registry.svc:5000/autopoc-test-builds/muckscraper:latest
- **Base Image:** registry.access.redhat.com/ubi9/python-312
- **PostgreSQL:** registry.redhat.io/rhel9/postgresql-16:latest
- **Resource Profile:** Medium (512Mi/250m request, 1Gi/500m limit for web app)

## 6. Recommendations

1. **Add pgvector extension** to PostgreSQL for story clustering via embeddings
2. **Deploy Meilisearch** as a sidecar for full-text search functionality
3. **Connect to Ollama** or OpenShift AI model serving for AI summaries and bias scoring
4. **Deploy the scheduler component** for automated news fetching
5. **Add PVC** for PostgreSQL data persistence

## 7. Appendix

### Artifacts
- **Dockerfile:** [Dockerfile.ubi](https://github.com/aicatalyst-team/MuckScraper/blob/main/Dockerfile.ubi)
- **PoC Plan:** [poc-plan.md](https://github.com/aicatalyst-team/MuckScraper/blob/main/poc-plan.md)

### Build Notes
- Playwright dependencies excluded (not needed for web UI serving)
- PostgreSQL pgvector/pgvector:pg14 image failed on OpenShift (permission issues)
- Switched to registry.redhat.io/rhel9/postgresql-16 (OpenShift-compatible)
- Database migrations log "No migrations to run" (expected without pgvector extension)
