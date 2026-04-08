# Money Maker

A full-stack web application with FastAPI backend, Next.js frontend, PostgreSQL database, and nginx reverse proxy.

## Tech Stack

- **Backend**: FastAPI (Python 3.11) with SQLAlchemy ORM
- **Frontend**: Next.js 14 (React 18, TypeScript)
- **Database**: PostgreSQL 16
- **Reverse Proxy**: nginx
- **Containerization**: Docker & Docker Compose
- **Testing**: pytest (backend), Jest (frontend)

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- (Optional) Python 3.11+ for local backend development
- (Optional) Node.js 20+ for local frontend development

## Quick Start

1. Clone the repository and navigate to the project directory

2. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

3. Start the development stack:
   ```bash
   docker-compose up --build
   ```

4. Access the application:
   - Frontend: http://localhost
   - Backend API: http://localhost/api
   - API Documentation: http://localhost/docs
   - Backend Direct: http://localhost:8000
   - Frontend Direct: http://localhost:3000

## Development

### Running in Development Mode

```bash
# Start all services with hot reload
docker-compose up

# Run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### Running Tests

**Backend Tests (pytest):**
```bash
# Run backend tests in Docker
docker-compose exec backend pytest

# Run with coverage
docker-compose exec backend pytest --cov=app
```

**Frontend Tests (Jest):**
```bash
# Run frontend tests in Docker
docker-compose exec frontend npm test

# Run in watch mode
docker-compose exec frontend npm run test:watch

# Run with coverage
docker-compose exec frontend npm run test:coverage
```

### Health Checks

All services include Docker Compose health checks:

- **Database**: `pg_isready` command
- **Backend**: HTTP GET `/health` endpoint
- **Frontend**: HTTP GET `/health` page
- **Nginx**: HTTP GET `/health` endpoint

Check service health:
```bash
docker-compose ps
```

## Production Deployment

1. Set production environment variables in `.env`

2. Deploy using production compose file:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

## Project Structure

```
.
├── backend/              # FastAPI application
│   ├── app/             # Main application code
│   │   ├── __init__.py
│   │   ├── main.py      # FastAPI app entry point
│   │   └── config.py    # Pydantic settings
│   ├── tests/           # pytest test suite
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pytest.ini
├── frontend/            # Next.js application
│   ├── app/            # Next.js app router
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── health/
│   ├── __tests__/      # Jest test suite
│   ├── Dockerfile
│   ├── package.json
│   ├── jest.config.js
│   └── next.config.js
├── nginx/              # Nginx reverse proxy
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml           # Development configuration
├── docker-compose.prod.yml      # Production configuration
├── .env.example        # Environment template
├── README.md           # This file
└── CONTRIBUTING.md     # Development guidelines
```

## API Endpoints

### Health Check
- `GET /health` - Service health status

### Root
- `GET /` - API information

### API v1
- `GET /api/v1/status` - API status and environment info

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_USER` | PostgreSQL username | `postgres` |
| `DB_PASSWORD` | PostgreSQL password | `postgres` |
| `DB_NAME` | PostgreSQL database name | `money_maker` |
| `DATABASE_URL` | Full database connection URL | `postgresql://postgres:postgres@db:5432/money_maker` |
| `ENV` | Application environment | `development` |
| `SECRET_KEY` | Application secret key | `dev-secret-key` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000,http://localhost` |
| `NEXT_PUBLIC_API_URL` | Frontend API URL | `http://localhost:8000` |

## License

MIT
