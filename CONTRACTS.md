# FILE OWNERSHIP
T1: api/server.py, api/db.py, api/models.py, api/executor.py
T2: agents/
T3: frontend/ (not admin)
T4: frontend/admin.html, frontend/js/admin.js, api/admin.py
T5: deploy/, Dockerfile, api/deploy.py
T6: tests/
DATABASE: PostgreSQL only, psycopg2, no ORM
API: Flask port 8090, /api/ prefix, JSON responses
FRONTEND: Vanilla JS, no framework
