# Wallet-Based Per-Minute Session Billing (Dockerized)

A containerized Django REST API for a paid consultation session system with prepaid wallet, per-minute billing, and session state management.

## Tech Stack & Architecture
- Django 4.2 & DRF
- PostgreSQL 15
- Docker & Docker Compose
- drf-yasg (For Swagger)


## Quickstart with Docker

1. Clone and enter the project-
git clone https://github.com/rahulverma24497/wallet-based-session.git 

cd wallet-based-session

2. Configure environment variables (optional defaults provided)

The project includes pre-configured defaults in `.env` and `docker-compose.yml`:

DATABASE_NAME=wallet_based_session
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_PORT=5432

3. Build and launch services

docker compose up --build -d

2 services run in docker container:
- `wallet_session_db`: PostgreSQL 15 on internal port 5432 (mapped to host port 5433).
- `wallet_session_web`: Django server on `http://localhost:8000/` with automated `makemigrations` + `migrate` on boot.

To stop the services:
docker compose down


4. Interactive Swagger API Docs

Open your browser at:
- **Swagger UI:** [http://localhost:8000/swagger/]
- **ReDoc UI:** [http://localhost:8000/redoc/]

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/accounts/register/` | Register new user or provider |
| POST | `/api/accounts/login/` | Authenticate and obtain auth token |

### Wallet Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/wallet/` | View current prepaid wallet balance |
| POST | `/api/wallet/recharge/` | Initiate mock wallet recharge (status: `pending`) |
| POST | `/api/wallet/recharge/callback/` | Webhook callback to credit balance (idempotent) |

### Consultation Sessions & Billing
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions/` | List current user sessions |
| POST | `/api/sessions/` | Book a consultation session (`unassigned`) |
| GET | `/api/sessions/{id}/` | Get detailed session status & billing info |
| PATCH | `/api/sessions/{id}/assign/` | Assign a provider to the session (`assigned`) |
| PATCH | `/api/sessions/{id}/accept/` | Provider accepts the session (`accepted_by_provider`) |
| PATCH | `/api/sessions/{id}/start/` | Start consultation (enforces 5x min prepaid balance) |
| POST | `/api/sessions/{id}/billing/` | Trigger per-minute billing for elapsed time |
| PATCH | `/api/sessions/{id}/end/` | Manually end consultation session |
| PATCH | `/api/sessions/{id}/cancel/` | Cancel session prior to start |

---

## Session State Machine

```
unassigned ──→ assigned ──→ accepted_by_provider ──→ in_progress ──→ completed
     │              │                  │
     └──────────────┴──────────────────┘
                    ↓
                cancelled
```

- **`unassigned` ➔ `assigned`**: Client assigns provider.
- **`assigned` ➔ `accepted_by_provider`**: Provider accepts assigned session.
- **`accepted_by_provider` ➔ `in_progress`**: Client starts session. Requires prepaid balance covering at least **5 minutes** of consultation.
- **`in_progress` ➔ `completed`**: Ended manually by client/provider or automatically by system upon balance exhaustion.
- **Single Active Session Rule**: A user cannot start a new session while another session is in progress.

---

## Database ER Diagram

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│     User     │     │      Wallet      │     │ RechargeTransaction │
├──────────────┤     ├──────────────────┤     ├─────────────────────┤
│ id           │1───1│ id               │     │ id                  │
│ username     │     │ user_id (FK)     │     │ user_id (FK)        │
│ email        │     │ balance          │     │ amount              │
│ password     │     │ created_at       │     │ reference (unique)  │
│ role         │     │ updated_at       │     │ status              │
└──────┬───────┘     └──────────────────┘     │ created_at          │
       │                                      │ updated_at          │
       │1                                     └─────────────────────┘
       │
       ├───────────────────────┐
       │                       │
       ▼ N                     ▼ N
┌─────────────────────┐  ┌──────────────┐
│ ConsultationSession │  │ BillingRecord│
├─────────────────────┤  ├──────────────┤
│ id                  │  │ id           │
│ user_id (FK)        │1─N session_id   │
│ provider_id (FK)    │  │ minute_number│
│ status              │  │ amount       │
│ per_minute_cost     │  │ billed_at    │
│ started_at          │  └──────────────┘
│ ended_at            │  (unique: session + minute_number)
│ ended_by            │
│ end_reason          │
│ billed_minutes      │
│ total_billed_amount │
│ created_at          │
│ updated_at          │
└─────────────────────┘
```
