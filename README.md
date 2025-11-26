# Thandev - Real-Time Security Intelligence Platform

A comprehensive, modern security intelligence platform that provides real-time CVE data, security scanning, performance analysis, exploit feeds, and cybersecurity news aggregation.

## 🎯 Overview

Thandev is a full-stack security intelligence platform designed for security professionals, developers, and organizations. It combines multiple security tools and data sources into a unified, modern interface with real-time updates and comprehensive analysis capabilities.

## ✨ Key Features

### 🔒 Security Scanning
- **Multi-Tier Security Scans**: Level 0 (Surface), Level 1 (Discovery), Level 2 (Active) scanning
- **Cloud Run Integration**: Scalable security scanning using Google Cloud Run Jobs
- **Security Tools**: Integration with Nuclei, Nmap, SSLScan, and custom security checks
- **Vulnerability Detection**: Comprehensive vulnerability scanning with severity classification
- **Real-time Progress**: Live scan status updates and progress tracking
- **Detailed Reports**: Security score breakdown, vulnerability categorization, and actionable recommendations
- **Scan History**: Complete history of all security scans with trend analysis

### ⚡ Performance Scanning
- **Lighthouse Integration**: Google Lighthouse-powered performance analysis
- **Core Web Vitals**: FCP, LCP, CLS, FID metrics
- **Device-Specific Analysis**: Desktop and mobile performance testing
- **Optimization Opportunities**: Actionable recommendations for performance improvements
- **Diagnostics**: Detailed technical diagnostics and best practices
- **Cloud Run Deployment**: Scalable performance scanning service
- **Performance Reports**: Comprehensive reports similar to PageSpeed Insights

### 📰 Security News Aggregation
- **RSS Feed Integration**: Aggregates news from certified security sources
- **Real-time Updates**: Automatic feed updates and content refresh
- **Source Filtering**: Filter by source, category (cyber, tech, AI)
- **Article Reading**: Full article content extraction and readability
- **News Statistics**: Top sources, categories, and trending topics
- **Certified Sources**: The Hacker News, BleepingComputer, Krebs on Security, SANS ISC, ZDI, Dark Reading, Ars Technica

### 💥 Exploit Feed
- **CVE Database**: Real-time Common Vulnerabilities and Exposures data
- **NVD Integration**: National Vulnerability Database API integration
- **Exploit Tracking**: Track exploits with PoCs and detailed information
- **Severity Classification**: CVSS v2/v3 scoring and severity levels
- **EPSS Scores**: Exploit Prediction Scoring System integration
- **KEV Tracking**: Known Exploited Vulnerabilities identification
- **Advanced Filtering**: Filter by severity, CVE ID, date, and source

### 🌐 Domain Verification
- **DNS TXT Record Verification**: Verify domain ownership via DNS records
- **Secure Token System**: Cryptographically secure verification tokens
- **Real-time Status**: Check verification status in real-time
- **Rate Limiting**: Built-in rate limiting for verification requests
- **Expiration Management**: Automatic expiration handling (48-hour validity)

### 🔐 Authentication
- **GitHub OAuth**: Secure authentication via GitHub OAuth 2.0
- **NextAuth.js Integration**: Industry-standard authentication solution
- **Session Management**: Secure JWT-based session handling
- **User Profiles**: User profile management and customization

### 📊 Dashboard
- **Real-time Statistics**: Live stats on vulnerabilities, exploits, and threats
- **Security Insights**: Visual security metrics and trends
- **Quick Actions**: Quick access to common tasks
- **Recent Scans**: Recent scan history and quick access
- **Performance Metrics**: Performance scan history and trends

## 🛠️ Tech Stack

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS 4** - Modern utility-first styling
- **Framer Motion** - Smooth animations and transitions
- **NextAuth.js** - Authentication and session management
- **Prisma** - Database ORM and type safety
- **Anime.js** - Advanced animations
- **Lucide React** - Icon library
- **RSS Parser** - RSS feed parsing
- **Mozilla Readability** - Article content extraction

### Backend
- **FastAPI** - High-performance Python API framework
- **SQLAlchemy 2.0** - Modern Python ORM
- **PostgreSQL** - Primary database (SQLite for development)
- **Redis** - Caching and task queue
- **Celery** - Distributed task processing
- **Alembic** - Database migrations
- **Pydantic** - Data validation and settings management
- **SlowAPI** - Rate limiting middleware
- **Sentry** - Error tracking and monitoring
- **Gunicorn** - Production WSGI server

### Cloud Services
- **Google Cloud Run** - Serverless container platform for scanning services
- **Vercel** - Frontend deployment and hosting
- **Fly.io** - Backend deployment and hosting
- **Google Cloud Storage** - Artifact storage for scan results

### Security Tools
- **Nuclei** - Vulnerability scanner with 1000+ templates
- **Nmap** - Network port scanner and service detection
- **SSLScan** - SSL/TLS configuration analysis
- **Lighthouse** - Performance auditing tool
- **Puppeteer** - Headless Chrome automation

### Data Sources
- **NVD API v2.0** - National Vulnerability Database
- **RSS Feeds** - Security news feeds from certified sources
- **EPSS** - Exploit Prediction Scoring System

## 📁 Project Structure

```
thandev/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py            # FastAPI application entry point
│   │   ├── db.py              # Database configuration and session management
│   │   ├── models.py           # SQLAlchemy database models
│   │   ├── schemas.py          # Pydantic schemas for API validation
│   │   ├── routers/           # API route handlers
│   │   │   ├── exploits.py    # Exploit feed endpoints
│   │   │   ├── news.py        # News aggregation endpoints
│   │   │   ├── performance.py # Performance scan endpoints
│   │   │   └── security.py   # Security scan endpoints
│   │   ├── tasks/             # Celery background tasks
│   │   │   └── celery_app.py  # Celery configuration
│   │   └── utils/             # Utility functions
│   │       ├── cache.py       # Redis caching utilities
│   │       └── dedupe.py      # Data deduplication logic
│   ├── migrations/            # Alembic database migrations
│   ├── presets/               # Security scan presets (YAML)
│   ├── requirements.txt       # Python dependencies
│   ├── Dockerfile             # Backend container image
│   ├── scheduler.py           # Data ingestion scheduler
│   └── init_db.py             # Database initialization script
│
├── frontend/                  # Next.js frontend
│   ├── app/                   # Next.js App Router
│   │   ├── api/               # API routes (Next.js API routes)
│   │   │   ├── auth/          # Authentication endpoints
│   │   │   ├── domains/       # Domain verification endpoints
│   │   │   ├── exploits/      # Exploit feed endpoints
│   │   │   ├── news/          # News aggregation endpoints
│   │   │   ├── performance-scan/ # Performance scan endpoints
│   │   │   └── security-scan/ # Security scan endpoints
│   │   ├── dashboard/         # Dashboard pages
│   │   │   ├── scan/          # Security scan interface
│   │   │   ├── performance/   # Performance scan interface
│   │   │   ├── history/       # Scan history
│   │   │   └── profile/       # User profile
│   │   ├── exploits/          # Exploit feed page
│   │   ├── news/              # News aggregation page
│   │   └── security/          # Security information page
│   ├── components/            # React components
│   │   ├── Dashboard/         # Dashboard components
│   │   ├── Exploits/          # Exploit feed components
│   │   ├── News/              # News components
│   │   └── utils/             # Utility components
│   ├── lib/                   # Library code
│   │   ├── auth.ts            # Authentication configuration
│   │   └── cloud-run.ts       # Cloud Run integration
│   ├── prisma/                # Prisma schema
│   ├── public/                # Static assets
│   ├── package.json           # Node.js dependencies
│   └── Dockerfile             # Frontend container image
│
├── cloud-run/                 # Google Cloud Run services
│   ├── security-scanner/      # Security scanning service
│   │   ├── scanner.py         # Main scanner logic
│   │   ├── server.py          # HTTP server
│   │   └── Dockerfile         # Container image
│   ├── lighthouse-scanner/    # Performance scanning service
│   │   ├── server.js          # Node.js server
│   │   └── Dockerfile         # Container image
│   └── deploy-*.sh            # Deployment scripts
│
├── docker-compose.yml         # Docker Compose configuration
├── vercel.json                # Vercel deployment configuration
├── fly.toml                   # Fly.io deployment configuration
└── README.md                  # This file
```

## 🚀 Quick Start

### Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.11+
- **PostgreSQL** 15+ (or SQLite for development)
- **Redis** (optional, for caching and task queue)
- **Docker** (optional, for containerized deployment)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/thandev.git
   cd thandev
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Database Setup**
   ```bash
   # For PostgreSQL
   createdb thandev
   
   # Or use SQLite (default for development)
   # No setup needed, database will be created automatically
   
   # Run migrations
   alembic upgrade head
   ```

4. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   ```

5. **Environment Variables**

   Create `.env` files in both `backend/` and `frontend/` directories:

   **Backend `.env`:**
   ```env
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
   # Or for SQLite:
   # DATABASE_URL=sqlite:///./thandev.db
   
   REDIS_URL=redis://localhost:6379/0
   NVD_API_KEY=your_nvd_api_key_here  # Optional, for higher rate limits
   
   # Cloud Run Configuration (optional)
   CLOUD_RUN_ENABLED=true
   GCP_PROJECT_ID=your-gcp-project-id
   GCP_REGION=us-central1
   BACKEND_URL=http://localhost:8000
   GCS_BUCKET=your-gcs-bucket-name
   
   # Sentry (optional)
   SENTRY_DSN=your_sentry_dsn
   ENVIRONMENT=development
   
   # CORS
   CORS_ORIGINS=http://localhost:3000,https://thandev.com
   ```

   **Frontend `.env.local`:**
   ```env
   NEXT_PUBLIC_API_BASE=http://localhost:8000
   
   # Authentication
   GITHUB_CLIENT_ID=your_github_client_id
   GITHUB_CLIENT_SECRET=your_github_client_secret
   NEXTAUTH_SECRET=your_nextauth_secret
   NEXTAUTH_URL=http://localhost:3000
   
   # Cloud Run (optional)
   CLOUD_RUN_JOB_URL=https://your-cloud-run-service.run.app
   ```

### Running the Application

1. **Start the Backend**
   ```bash
   cd backend
   source .venv/bin/activate
   uvicorn app.main:app --reload --port 8000
   ```

2. **Start the Frontend**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Start Data Ingestion** (Optional, in separate terminal)
   ```bash
   cd backend
   source .venv/bin/activate
   python scheduler.py
   ```

4. **Start Redis** (Optional, for caching)
   ```bash
   redis-server
   ```

5. **Access the Application**
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## 🐳 Docker Deployment

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

### Services Included

- **PostgreSQL**: Database server
- **Redis**: Caching and task queue
- **API**: FastAPI backend
- **Scheduler**: Data ingestion service
- **Frontend**: Next.js frontend

## 📊 API Endpoints

### Core Endpoints

#### Health & Status
- `GET /health` - Health check with database status
- `GET /debug/env` - Debug environment variables (non-sensitive)

#### Exploits
- `GET /api/exploits` - List exploits with pagination
  - Query params: `limit`, `cursor`, `severity`, `cve`
- `GET /api/exploits/stats` - Get exploit statistics
- `GET /api/exploits/{id}` - Get specific exploit details

#### News
- `GET /news` - List security news articles
  - Query params: `q` (search), `kev`, `exploit`, `limit`, `offset`

#### Security Scanning
- `POST /api/security-scan/` - Start a security scan
  ```json
  {
    "url": "https://example.com",
    "tier": "level0" | "level1" | "level2",
    "user_id": "optional-user-id"
  }
  ```
- `GET /api/security-scan/{job_id}` - Get scan status
- `POST /api/security-scan/callback/{job_id}` - Webhook for scan results (internal)

#### Performance Scanning
- `POST /api/performance-scan/` - Start a performance scan
  ```json
  {
    "url": "https://example.com",
    "device": "desktop" | "mobile",
    "user_id": "optional-user-id"
  }
  ```
- `GET /api/performance-scan/{job_id}` - Get scan status

### Rate Limiting

- Exploits: 100 requests/minute
- Exploit Stats: 30 requests/minute
- Security Scans: 10 requests/minute
- Performance Scans: 10 requests/minute

## 🔧 Configuration

### Environment Variables

#### Backend
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | Database connection string | Yes | `sqlite:///./thandev.db` |
| `REDIS_URL` | Redis connection string | No | - |
| `NVD_API_KEY` | NVD API key for higher rate limits | No | - |
| `CLOUD_RUN_ENABLED` | Enable Cloud Run scanning | No | `true` |
| `GCP_PROJECT_ID` | Google Cloud project ID | No | - |
| `GCP_REGION` | Google Cloud region | No | `us-central1` |
| `BACKEND_URL` | Backend URL for callbacks | No | - |
| `GCS_BUCKET` | Google Cloud Storage bucket | No | - |
| `SENTRY_DSN` | Sentry error tracking DSN | No | - |
| `ENVIRONMENT` | Environment name | No | `development` |
| `CORS_ORIGINS` | Allowed CORS origins | No | `http://localhost:3000` |

#### Frontend
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `NEXT_PUBLIC_API_BASE` | Backend API base URL | Yes | - |
| `GITHUB_CLIENT_ID` | GitHub OAuth client ID | Yes | - |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth client secret | Yes | - |
| `NEXTAUTH_SECRET` | NextAuth.js secret | Yes | - |
| `NEXTAUTH_URL` | NextAuth.js URL | No | `http://localhost:3000` |
| `CLOUD_RUN_JOB_URL` | Cloud Run service URL | No | - |

## 📈 Data Ingestion

### Automatic Ingestion

The system automatically fetches data from multiple sources:

- **CVE Data**: Every 6 hours from NVD API
- **News Feeds**: Real-time RSS feed updates
- **Exploit Data**: Continuous monitoring and updates

### Manual Ingestion

```bash
# Trigger immediate CVE data fetch
curl -X POST http://localhost:8000/api/ingest

# Or use the scheduler
cd backend
python scheduler.py
```

### Data Sources

- **NVD API v2.0**: National Vulnerability Database
  - Rate Limits: 50 requests/30s (5000 with API key)
  - Data: CVSS scores, severity, descriptions, references
- **RSS Feeds**: Certified security news sources
- **EPSS**: Exploit Prediction Scoring System

## 🎨 UI Features

### Design Elements

- **Glassmorphism**: Frosted glass effects on cards
- **Neon Accents**: Subtle glowing hover effects
- **Gradient Backgrounds**: Animated gradient overlays
- **Parallax Scrolling**: Smooth depth effects
- **Typewriter Effects**: Animated text transitions
- **Cursor Glow**: Interactive cursor following effects
- **Dark/Light Mode**: Seamless theme switching

### Responsive Design

- **Mobile First**: Optimized for all screen sizes
- **Touch Friendly**: Gesture support for mobile devices
- **Performance**: Optimized loading and animations
- **Accessibility**: WCAG compliance considerations

## 🔒 Security Features

### Backend Security

- **CORS Protection**: Configurable cross-origin resource sharing
- **Input Validation**: Pydantic models for all API inputs
- **SQL Injection Prevention**: SQLAlchemy ORM protection
- **Rate Limiting**: API rate limiting and throttling
- **Security Headers**: X-Content-Type-Options, X-Frame-Options, CSP
- **Error Handling**: Secure error responses without sensitive data
- **Sentry Integration**: Error tracking and monitoring

### Frontend Security

- **NextAuth.js**: Secure authentication and session management
- **CSRF Protection**: Built-in CSRF protection
- **XSS Prevention**: React's built-in XSS protection
- **Content Security Policy**: CSP headers for additional security

## 🚀 Deployment

### Frontend Deployment (Vercel)

1. **Connect Repository**
   - Go to [Vercel Dashboard](https://vercel.com/dashboard)
   - Import GitHub repository
   - Set root directory to `frontend`

2. **Configure Build**
   - Framework: Next.js
   - Build Command: `npm run build`
   - Output Directory: `.next`

3. **Set Environment Variables**
   - Add all required environment variables in Vercel dashboard

4. **Deploy**
   - Push to main branch for automatic deployment

### Backend Deployment (Fly.io)

1. **Install Fly CLI**
   ```bash
   curl -L https://fly.io/install.sh | sh
   fly auth login
   ```

2. **Create PostgreSQL Database**
   ```bash
   fly postgres create --name thandev-db --region iad
   ```

3. **Deploy Backend**
   ```bash
   cd backend
   fly launch
   fly secrets set DATABASE_URL="postgresql://..."
   fly secrets set NVD_API_KEY="your_key"
   fly deploy
   ```

4. **Deploy Scheduler**
   ```bash
   fly deploy --config ../fly-scheduler.toml
   ```

### Cloud Run Deployment

See detailed guides:
- `cloud-run/README.md` - Lighthouse scanner deployment
- `SECURITY_SCAN_README.md` - Security scanner deployment
- `DEPLOYMENT.md` - Complete deployment guide

## 🧪 Development

### Running Tests

```bash
# Backend tests (when available)
cd backend
pytest

# Frontend tests (when available)
cd frontend
npm test
```

### Code Quality

```bash
# Backend linting
cd backend
black .  # Code formatting
flake8 . # Linting

# Frontend linting
cd frontend
npm run lint
```

### Database Migrations

```bash
# Create new migration
cd backend
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## 📝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Ensure code quality (linting, formatting)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Development Guidelines

- Follow existing code style and patterns
- Write clear commit messages
- Add documentation for new features
- Update tests for new functionality
- Ensure backward compatibility when possible

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Support

- **GitHub Issues**: [Create an issue](https://github.com/yourusername/thandev/issues)
- **Documentation**: See individual README files in subdirectories
- **Email**: support@thandev.com (if applicable)

## 🎯 Roadmap

### Planned Features

- [ ] Additional data sources (CVE Details, ExploitDB)
- [ ] Machine learning threat scoring
- [ ] Real-time notifications (WebSocket)
- [ ] API rate limiting dashboard
- [ ] Advanced search and filtering
- [ ] Export functionality (CSV, JSON, PDF)
- [ ] User authentication and profiles (enhanced)
- [ ] Custom watchlists and alerts
- [ ] API key management
- [ ] Webhook integrations
- [ ] Scheduled scans
- [ ] Compliance reporting
- [ ] Multi-tenant support

### In Progress

- [x] Security scanning with Cloud Run
- [x] Performance scanning with Lighthouse
- [x] News aggregation
- [x] Exploit feed
- [x] Domain verification
- [x] Authentication system

## 🙏 Acknowledgments

- **NVD**: National Vulnerability Database
- **Google Lighthouse**: Performance auditing
- **Nuclei**: Vulnerability scanning templates
- **Next.js**: React framework
- **FastAPI**: Python web framework
- **All contributors**: Thank you for your contributions!

---

**Built with ❤️ for the security community**
