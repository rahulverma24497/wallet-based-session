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

## End-to-End Application Flow (How It Works)

Here is a brief step-by-step walkthrough of how the system operates from start to finish:

1. User Registration & Wallet Auto-Creation
   - A client (`role='user'`) and a provider (`role='provider'`) register via `POST /api/accounts/register/`.
   - A Django `post_save` signal triggers immediately upon registration to automatically create a dedicated, zero-balance `Wallet` for each new user.

2. Authentication & Token Authorization
   - Users authenticate via `POST /api/accounts/login/` and receive a DRF authentication token.
   - For all protected endpoints, the client passes the header `Authorization: Token <key>` (in Swagger UI, click 'Authorize' at the top right and enter `Token <your_token>`).

3. Prepaid Wallet Recharge
   - The user initiates a wallet recharge via `POST /api/wallet/recharge/` specifying the amount and a unique reference. The transaction starts in `pending` status.
   - The mock payment gateway callback `POST /api/wallet/recharge/callback/` marks the transaction `success` and atomically credits the user's wallet balance using database row locks (`select_for_update()`).
   - Duplicate callbacks are idempotent: re-submitting the same reference will safely acknowledge without double-crediting.

4. Booking & Provider Acceptance
   - The user creates a consultation request via `POST /api/sessions/` with a defined `per_minute_cost` (session state: `unassigned`).
   - The user assigns a provider via `PATCH /api/sessions/{id}/assign/` (session state: `assigned`).
   - The provider accepts the request via `PATCH /api/sessions/{id}/accept/` (session state: `accepted_by_provider`).

5. Starting the Session (Minimum Balance Barrier)
   - The user starts the session via `PATCH /api/sessions/{id}/start/`.
   - Enforcement Check: The system verifies the user has enough prepaid balance to cover at least 5 full minutes (`balance >= 5 * per_minute_cost`) and does not already have another session in progress.
   - If verified, the session enters `in_progress` and the start timestamp (`started_at`) is captured.

6. Per-Minute Billing & Idempotent Deductions
   - While the session runs, per-minute billing is processed via `POST /api/sessions/{id}/billing/`.
   - The system calculates elapsed minutes since `started_at` against the count of already billed minutes.
   - For each elapsed minute, the system deducts the `per_minute_cost` from the wallet and inserts a `BillingRecord`.
   - Duplicate Billing Protection: A database `unique_together` constraint on `(session, minute_number)` guarantees that the exact same minute can never be billed twice.

7. Session Completion (Manual or Auto-Termination)
   - Manual End: Either the user or provider calls `PATCH /api/sessions/{id}/end/` to conclude the consultation (`status='completed'`, `ended_by='user'` or `'provider'`).
   - Auto-End on Low Balance: If at any point during billing the wallet balance is insufficient to cover the upcoming minute, the system terminates the session automatically (`status='completed'`, `ended_by='system'`, `end_reason='Insufficient Balance'`), ensuring the wallet balance never drops below zero.
