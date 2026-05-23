# CyberVerse AI

CyberVerse AI is an Autonomous Multi-Agent Security Intelligence Platform designed to automate code scanning, vulnerability analysis, and threat intelligence mapping. Powered by a robust FastAPI/Celery backend and a modern Next.js/Three.js frontend, it delivers an "Elite Engineer" dashboard for visualizing zero-day risks and structural code flaws.

## Features

- **Multi-Agent Architecture**: Dedicated AI agents for Asset Intelligence, Security Analysis, Validation, and Reporting.
- **Asynchronous Task Pipeline**: Built on Celery and Redis to handle deep codebase clones and intensive LLM analysis asynchronously.
- **Elite Holographic Dashboard**: A Next.js frontend with Three.js rendering for real-time scan visualization.
- **Security-First Architecture**: Integrated rate limiting, secure pseudo-random generators, subprocess isolation, and CWE/OWASP vulnerability mapping.
- **Cloud-Ready**: Fully containerized and prepared for AWS and Vercel deployments.

---

## Local Development Setup

To run CyberVerse AI locally on a Linux/macOS machine:

### Prerequisites
- Python 3.10+
- Node.js 18+
- Redis (must be installed and running, or available via Docker)

### 1. Environment Configuration
Duplicate the `.env.example` files (or create new `.env` files) in both the `backend/` and `frontend/` directories.

**Backend (`backend/.env`):**
```env
APP_ENV=development
# The backend will automatically generate a secure local SQLite DB and secret key if left blank in development.
NVIDIA_API_KEY=your_nvidia_nim_api_key_here
```

**Frontend (`frontend/.env.local`):**
```env
NEXT_PUBLIC_BACKEND_REST_URL=http://localhost:8090/api/v1
NEXT_PUBLIC_BACKEND_WS_URL=ws://localhost:8090/ws/scan
```

### 2. Install Dependencies
**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

<<<<<<< HEAD
### 3. Launch the Stack
We provide a unified launcher script that cleanly starts Redis, the FastAPI backend, the Celery worker, and the Next.js frontend in the background.

Ensure your terminal file watcher limit is increased to prevent Next.js compilation issues:
```bash
sudo sysctl -w fs.inotify.max_user_watches=524288
```

Then start the platform:
```bash
./start.sh
```
- **Frontend Dashboard**: `http://localhost:3000`
- **Backend API Docs**: `http://localhost:8090/docs`

To gracefully shut down all services:
```bash
./start.sh stop
```

---

## Production Deployment

CyberVerse AI is containerized and ready for production deployment on AWS (EC2/ECS) and Vercel.

1. **Backend Stack (AWS)**: A `docker-compose.yml` and `Dockerfile` are provided in the root directory to spin up the FastAPI Backend, Celery, Redis, and a PostgreSQL database.
2. **Frontend (Vercel)**: The Next.js frontend can be deployed directly via Vercel by importing the GitHub repository.

*For detailed cloud deployment steps, please refer to the deployment documentation artifacts provided during setup.*
=======
### 3. Launch the Stack (Locally)

To run the full stack locally:

1. **Start Redis**:
   Ensure Redis is running locally on port `6379`.

2. **Start Backend API Server**:
   ```bash
   cd backend
   source .venv/bin/activate
   # Run migrations
   alembic upgrade head
   # Start Uvicorn
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8090
   ```

3. **Start Celery Worker**:
   In a separate terminal window:
   ```bash
   cd backend
   source .venv/bin/activate
   python -m celery -A app.core.celery:celery_app worker --loglevel=info --concurrency=2
   ```

4. **Start Frontend Dev Server**:
   In a separate terminal window:
   ```bash
   cd frontend
   npm run dev
   ```

- **Frontend Dashboard**: `http://localhost:3000`
- **Backend API Docs**: `http://localhost:8090/docs`

---

## Production Deployment (Railway & Vercel)

CyberVerse AI is configured for a robust, production-grade cloud deployment leveraging **Vercel** for the frontend and **Railway** for the backend architecture.

### Target Architecture

```
Frontend (Vercel)
        ↓ (HTTP / WebSocket)
FastAPI Backend (Railway API Service)
   ├── Railway PostgreSQL
   ├── Railway Redis
   └── Celery Worker (Railway Worker Service)
```

### 1. Railway Services Provisioning

1. **Create a New Project** in Railway.
2. **Add Databases**:
   - Add a **PostgreSQL** service database.
   - Add a **Redis** service database.
3. **Add the FastAPI API Backend Service**:
   - Link the service to your GitHub repository.
   - Set the **Root Directory** to `backend`.
   - Railway will automatically detect the `backend/Dockerfile` and `backend/railway.json` configurations.
   - Add the required environment variables (see below).
4. **Add the Celery Worker Service**:
   - In the same Railway project, add another service linking to the same GitHub repository.
   - Set the **Root Directory** to `backend`.
   - Set the **Start Command** to:
     ```bash
     python -m celery -A app.core.celery:celery_app worker --loglevel=info --concurrency=2
     ```
   - Add the required environment variables (see below).

### 2. Environment Variables Configuration

Configure the following environment variables in the Railway dashboard:

#### API Service (`backend`):
- `APP_ENV`: `production`
- `DATABASE_URL`: `${{Postgres.DATABASE_URL}}` (Injected automatically by linking services)
- `REDIS_URL`: `${{Redis.REDIS_URL}}` (Injected automatically by linking services)
- `SECRET_KEY`: A cryptographically secure random string (Generate via `openssl rand -hex 32`)
- `NVIDIA_API_KEY`: Your Nvidia NIM API key (Mandatory in production)
- `PREFERRED_LLM_PROVIDER`: `nvidia`
- `CORS_ORIGINS`: `https://cyber-verse-ai.vercel.app` (Your custom Vercel domain)

#### Celery Worker Service:
- `APP_ENV`: `production`
- `DATABASE_URL`: `${{Postgres.DATABASE_URL}}`
- `REDIS_URL`: `${{Redis.REDIS_URL}}`
- `SECRET_KEY`: A cryptographically secure random string (Matching the API service's key)
- `NVIDIA_API_KEY`: Your Nvidia NIM API key
- `PREFERRED_LLM_PROVIDER`: `nvidia`

### 3. Frontend Deployment (Vercel)

1. Import your GitHub repository to Vercel.
2. Link the `frontend` directory.
3. Configure the following build-time Environment Variables:
   - `NEXT_PUBLIC_BACKEND_REST_URL`: The production API URL generated by Railway (e.g. `https://cyberverse-api.up.railway.app/api/v1`)
   - `NEXT_PUBLIC_BACKEND_WS_URL`: The production WebSocket URL generated by Railway (e.g. `wss://cyberverse-api.up.railway.app/ws/scan`)
4. Deploy the frontend application.
>>>>>>> 2cb71a5 (deployment to railway)

---

## Architecture Overview

- **Backend Framework**: FastAPI (Python)
- **Task Queue**: Celery + Redis
- **Database**: SQLite (Local) / PostgreSQL (Production) via SQLAlchemy/Alembic
- **Frontend**: Next.js (React), Zustand, Three.js (React Three Fiber)
- **AI Integration**: Nvidia NIM API (`moonshotai/kimi-k2.6`), utilizing dynamic retry loops for rate-limit resilience.
<<<<<<< HEAD
=======

>>>>>>> 2cb71a5 (deployment to railway)
