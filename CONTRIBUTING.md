# Contributing to Money Maker

Thank you for your interest in contributing! This guide will help you get started with the development environment.

## Development Setup

### Using Docker Compose (Recommended)

The easiest way to get started is using Docker Compose, which sets up all services automatically.

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd money_maker
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

3. **Start the development environment**
   ```bash
   docker-compose up --build
   ```

4. **Verify everything is running**
   - Frontend: http://localhost
   - API Docs: http://localhost/docs
   - Health check: http://localhost/health

### Local Development (Advanced)

If you prefer to run services locally without Docker:

#### Backend (Local)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend (Local)

```bash
cd frontend

# Install dependencies
npm install

# Run tests
npm test

# Start development server
npm run dev
```

#### Database (Docker)

Even with local backend/frontend, you can use Docker for PostgreSQL:

```bash
docker run -d \
  --name money_maker_db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=money_maker \
  -p 5432:5432 \
  postgres:16-alpine
```

## Running Tests

### Backend Tests

```bash
# Run all backend tests
docker-compose exec backend pytest

# Run with verbose output
docker-compose exec backend pytest -v

# Run with coverage report
docker-compose exec backend pytest --cov=app --cov-report=term-missing

# Run specific test file
docker-compose exec backend pytest tests/test_main.py

# Run tests matching pattern
docker-compose exec backend pytest -k "health"
```

### Frontend Tests

```bash
# Run all frontend tests
docker-compose exec frontend npm test

# Run in CI mode (non-interactive)
docker-compose exec frontend npm test -- --ci --coverage

# Run specific test file
docker-compose exec frontend npm test -- page.test.tsx

# Run tests matching pattern
docker-compose exec frontend npm test -- --testNamePattern="health"
```

### Docker Compose Health Checks

All services include health checks. Verify status with:

```bash
# Check service status
docker-compose ps

# View health check logs
docker-compose logs backend | grep health

# Manual health check
curl http://localhost/health
curl http://localhost/api/health
curl http://localhost:8000/health
```

## Project Structure

### Backend (`/backend`)

```
backend/
├── app/                    # Application code
│   ├── __init__.py
│   ├── main.py            # FastAPI entry point
│   └── config.py          # Configuration
├── tests/                 # Test suite
│   ├── __init__.py
│   └── test_main.py       # API endpoint tests
├── Dockerfile             # Container definition
├── requirements.txt       # Python dependencies
└── pytest.ini            # pytest configuration
```

### Frontend (`/frontend`)

```
frontend/
├── app/                   # Next.js app router
│   ├── layout.tsx        # Root layout
│   ├── page.tsx          # Home page
│   └── health/           # Health check page
├── __tests__/            # Jest test suite
│   ├── page.test.tsx
│   └── health.test.tsx
├── Dockerfile            # Container definition
├── package.json          # Node dependencies
├── jest.config.js        # Jest configuration
├── jest.setup.js         # Test setup
├── next.config.js        # Next.js configuration
└── tsconfig.json         # TypeScript configuration
```

### Infrastructure

```
nginx/
├── Dockerfile            # Nginx container
└── nginx.conf           # Reverse proxy config

docker-compose.yml        # Development stack
docker-compose.prod.yml   # Production stack
.env.example             # Environment template
```

## Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow existing code style
   - Add tests for new functionality
   - Update documentation if needed

3. **Run tests locally**
   ```bash
   # Backend
   docker-compose exec backend pytest

   # Frontend
   docker-compose exec frontend npm test
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

5. **Push and create a pull request**

## Code Style

### Python (Backend)

- Follow PEP 8
- Use type hints where appropriate
- Document functions with docstrings
- Keep functions focused and small

### TypeScript/JavaScript (Frontend)

- Use TypeScript for all new code
- Follow the existing component structure
- Use functional components with hooks
- Write tests for components

## Troubleshooting

### Services not starting

```bash
# Check logs
docker-compose logs <service-name>

# Restart a service
docker-compose restart <service-name>

# Rebuild and restart
docker-compose up --build -d <service-name>
```

### Database connection issues

```bash
# Check database is running
docker-compose ps db

# Check logs
docker-compose logs db

# Reset database (WARNING: deletes data)
docker-compose down -v
docker-compose up -d db
```

### Port conflicts

If ports are already in use, modify the port mappings in `docker-compose.yml`:

```yaml
ports:
  - "8080:80"      # Change 80 to 8080
  - "8001:8000"    # Change 8000 to 8001
  - "3001:3000"    # Change 3000 to 3001
```

## Questions?

If you have questions or need help, please open an issue or contact the maintainers.
