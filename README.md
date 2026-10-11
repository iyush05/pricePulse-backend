# PricePulse Backend

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-TimescaleDB-336791?logo=postgresql&logoColor=white)](https://www.timescale.com/)
[![LightGBM](https://img.shields.io/badge/LightGBM-GBDT-brightgreen)](https://lightgbm.readthedocs.io/)
[![Meilisearch](https://img.shields.io/badge/Meilisearch-Search-pink?logo=meilisearch&logoColor=white)](https://www.meilisearch.com/)
[![Celery](https://img.shields.io/badge/Celery-Task%20Queue-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev/)

PricePulse is a prospective multi-vendor e-commerce price tracking and buy-timing recommendation engine. Rather than retroactive tracking, a product's history begins the instant a user submits its URL, de-duplicated at the product level so subsequent subscribers inherit the complete price timeline. The system formulates purchase timing as a binary classification problem predicting whether a meaningfully better price will appear within a forward-looking horizon $H = 14$ days.

---

## Architecture Overview

```
                                      +------------------------+
                                      |   Client Application   |
                                      +-----------+------------+
                                                  |
                                          HTTP / REST (JWT)
                                                  v
                                      +------------------------+
                                      |  FastAPI Gateway (v1)  |
                                      +-----+------------+-----+
                                            |            |
                     +----------------------+            +-----------------------+
                     v                                                           v
+---------------------------------------+                     +------------------------------------+
|            Ingestion Engine           |                     |       Decision Engine & ML         |
| - URL Resolver (ASIN/PID, clean URL)  |                     | - Feature Engineering (20 feats)   |
| - Scraper Pool (httpx / Playwright)   |                     | - Heuristic Cold-Start (|S| < 30)  |
| - Normaliser (currency, quarantine)   |                     | - GBDT Classifier (LightGBM, 400t) |
+-------------------+-------------------+                     +------------------+-----------------+
                    |                                                            |
                    v                                                            v
+---------------------------------------+                     +------------------------------------+
|          Celery Task Broker           |                     |        Search & RAG Chat           |
| - Priority Queues (scraping, alerts)  |                     | - Meilisearch (typo-tolerant)      |
| - Adaptive Polling Cadence Calculator |                     | - Grounded RAG Chat over watchlist |
+-------------------+-------------------+                     +------------------------------------+
                    |
                    v
+--------------------------------------------------------------------------------------------------+
|                                    Storage Layer                                                 |
| - Relational: PostgreSQL (Users, Products, Subscriptions, Alerts, Chat)                          |
| - Time-Series: TimescaleDB hypertable (price_history) & continuous aggregates                    |
| - Cache & Broker: Redis (Token-bucket rate limits, response caching, Celery queues)              |
+--------------------------------------------------------------------------------------------------+
```

---

## Core Algorithms Implemented

### 1. Prospective Submission & Recommendation Workflow
When a user submits a URL or query:
1. **Resolve Canonical Key**: Extracts canonical ID (e.g., Amazon ASIN `amazon:IN:B09V3KXJPB`, Flipkart PID `flipkart:itm12345678`) and strips tracking parameters (`utm_*`, `ref`, `tag`).
2. **De-duplication Check**: If new to system, executes prospective synchronous scrape, records first price in `price_history`, and enqueues scheduled tracking.
3. **Subscription**: Subscribes user to product key (with optional `target_price`).
4. **Cold-Start Check**:
   - If $|S| < w_{min}$ (default 30 observations): Runs **Phase 1 Heuristic**:
     $$\text{BUY if } r_{90}(t) < 0 \text{ AND } p_t \le (1 + 0.05) \cdot lo(t)$$
     Assigns preliminary low confidence score ($0.35$).
   - If $|S| \ge w_{min}$: Computes 20 features strictly from closed past, feeds into **Phase 2 GBDT model** predicting probability $c$ of label $y_t = 1$ (BUY if $c \ge 0.5$ else WAIT).

### 2. Adaptive Polling Cadence
Dynamic fetch cadence recalculation after every scrape:
1. Calculates trailing coefficient of variation: $v = \sigma_{30} / MA_{30}$.
2. Calculates gap to nearest subscriber target: $g = |p_t - \text{target}| / p_t$.
3. **Halve interval** down to 1 hour if volatile ($v > 0.10$) or near target ($g < 0.05$).
4. **Double interval** up to 48 hours if stable ($v < 0.02$) and unchanged for 14 days.
5. If zero active subscribers for 30 days, marks product `is_dormant = True`.
6. Adds randomized $\pm 10\%$ jitter to eliminate synchronized polling spikes.

### 3. Feature Engineering Pipeline
All features are computed strictly from the closed past:
- **Statistical Baselines**: Centered moving averages $MA_7, MA_{30}, MA_{90}$, ratios $r_7, r_{30}, r_{90}$, rolling std $\sigma_{90}$, $z_{90}$.
- **Running Extrema**: Gap to all-time low, gap to all-time high, normalized range position.
- **Promotional Cadence**: Discount episode detection ($>7\%$ below trailing 14-period max), days since discount, mean interval $\bar{g}(t)$, cadence phase $\phi(t)$.
- **Temporal**: $\sin$/$\cos$ cyclical transformations for Day of Year and Day of Week.
- **Trend Forecast & Context**: Holt's linear trend forecast ratio, 30-day stock availability fraction.

---

## Complete API Route Reference

All endpoints are mounted under `/api/v1` (with interactive Swagger UI at `/docs`).

### Authentication (`/api/v1/auth`)
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register new user, returns JWT pair |
| `POST` | `/api/v1/auth/login` | Authenticate with email/password |
| `POST` | `/api/v1/auth/refresh` | Rotate access token using refresh token |
| `POST` | `/api/v1/auth/logout` | Revoke token via Redis blacklist |
| `POST` | `/api/v1/auth/forgot-password` | Password reset trigger |
| `POST` | `/api/v1/auth/reset-password` | Password reset execution |

### User Profile (`/api/v1/users`)
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/users/me` | Current user profile |
| `PATCH` | `/api/v1/users/me` | Update locale, email, notification preferences |
| `DELETE` | `/api/v1/users/me` | Account deletion with cascade |
| `GET` | `/api/v1/users/me/stats` | Dashboard stats (tracked items, alerts fired, estimated savings) |

### Products & Prospective Tracking (`/api/v1/products`)
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/products/track` | **Core Tracking**: Resolve URL -> Scrape -> Subscribe -> Recommend |
| `GET` | `/api/v1/products` | Paginated catalog of tracked products |
| `GET` | `/api/v1/products/{id}` | Single product detail |
| `GET` | `/api/v1/products/{id}/stats` | Baselines, all-time extrema, averages |
| `GET` | `/api/v1/products/{id}/prices` | Time-series data (`7d`, `30d`, `90d`, `1y`, `all`; `raw`, `hourly`, `daily`) |
| `GET` | `/api/v1/products/{id}/recommendation` | BUY/WAIT recommendation with confidence |

### Subscriptions (`/api/v1/subscriptions`)
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/subscriptions` | User's active watchlist with embedded product data |
| `GET` | `/api/v1/subscriptions/{id}` | Single subscription details |
| `PATCH` | `/api/v1/subscriptions/{id}` | Update target price or active status |
| `DELETE` | `/api/v1/subscriptions/{id}` | Unsubscribe (soft delete) |

### Alerts (`/api/v1/alerts`)
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/alerts` | List price drop alerts (supports `unread=true` filter) |
| `GET` | `/api/v1/alerts/{id}` | Single alert detail |
| `PATCH` | `/api/v1/alerts/{id}/read` | Mark alert as read |
| `POST` | `/api/v1/alerts/mark-all-read` | Bulk mark all alerts read |

### Search & Chat (`/api/v1/search`, `/api/v1/chat`)
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/search` | Typo-tolerant search across tracked products |
| `POST` | `/api/v1/chat` | RAG Chat grounded in user's price telemetry records |
| `GET` | `/api/v1/chat/history` | Retrieve conversation history with cited sources |

### Health & Metadata
| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | DB and Redis connection health check |
| `GET` | `/docs` | OpenAPI Swagger documentation |

---

## Quickstart & Local Development

### 1. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
```

### 3. Run with Docker Compose
To launch the full production-like stack (PostgreSQL + TimescaleDB, Redis, Meilisearch, Celery Workers, Beat, and API Gateway):
```bash
docker compose up --build
```

### 4. Running Locally
Run the FastAPI development server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Run Celery Workers:
```bash
celery -A app.workers.celery_app.celery_app worker --loglevel=info -Q default,scraping,alerts,notifications
```

Run Celery Beat Scheduler:
```bash
celery -A app.workers.celery_app.celery_app beat --loglevel=info
```

### 5. Running Test Suite
```bash
pytest -v
```
All 21 unit and integration tests execute against an isolated async in-memory database.
