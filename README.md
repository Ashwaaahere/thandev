# Thandev - Real-Time Security Intelligence Platform

A modern, futuristic security intelligence platform that provides real-time CVE (Common Vulnerabilities and Exposures) data, exploit feeds, and security news.

## 🚀 Features

### Real-Time Data
- **Live CVE Feed**: Real-time vulnerability data from NVD (National Vulnerability Database)
- **Automatic Updates**: Data refreshes every 6 hours automatically
- **Rich Metadata**: CVSS scores, severity levels, and detailed descriptions
- **Deduplication**: Prevents duplicate entries and ensures data integrity

### Modern UI/UX
- **Futuristic Design**: Glassmorphism, neon effects, and animated gradients
- **Dark/Light Mode**: Seamless theme switching
- **Responsive**: Works perfectly on desktop, tablet, and mobile
- **Interactive**: Hover effects, parallax scrolling, and smooth animations

### Security Intelligence
- **Exploit Feed**: Live stream of newly published exploits and PoCs
- **News Integration**: Security news and threat intelligence
- **Statistics Dashboard**: Real-time stats on vulnerabilities and threats
- **Search & Filter**: Advanced filtering by severity, date, and source

## 🛠️ Tech Stack

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling
- **Framer Motion** - Smooth animations and transitions
- **Canvas API** - Dynamic background effects

### Backend
- **FastAPI** - High-performance Python API
- **PostgreSQL** - Robust database for CVE data
- **SQLAlchemy** - Python ORM
- **Redis** - Caching and task queue
- **Celery** - Background task processing

### Data Sources
- **NVD API** - National Vulnerability Database
- **Rate Limiting** - Respects API limits (50 req/30s, 5000 with key)
- **Error Handling** - Robust error handling and retry logic

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and npm
- Python 3.11+
- PostgreSQL 15+
- Redis (optional)

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
   # Start PostgreSQL and create database
   createdb thandev
   
   # Run migrations
   alembic upgrade head
   ```

4. **Frontend Setup**
   ```bash
   cd frontend
   npm install
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

3. **Start Data Ingestion** (Optional)
   ```bash
   cd backend
   source .venv/bin/activate
   python scheduler.py
   ```

4. **Access the Application**
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## 🐳 Docker Deployment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 📊 API Endpoints

### Core Endpoints
- `GET /api/stats` - Get real-time statistics
- `GET /api/exploits` - List exploits with pagination
- `GET /api/exploits/{id}` - Get specific exploit details
- `POST /api/ingest` - Trigger manual data ingestion

### Example Response
```json
{
  "total_exploits": 1347,
  "new_today": 420,
  "critical_count": 47
}
```

## 🔧 Configuration

### Environment Variables

#### Backend
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `NVD_API_KEY` - Optional NVD API key for higher rate limits

#### Frontend
- `NEXT_PUBLIC_API_BASE` - Backend API base URL

### Example .env
```bash
# Backend
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
REDIS_URL=redis://localhost:6379/0
NVD_API_KEY=your_nvd_api_key_here

# Frontend
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

## 📈 Data Ingestion

The system automatically fetches real CVE data from the National Vulnerability Database:

- **Schedule**: Every 6 hours
- **Sources**: NVD API v2.0
- **Rate Limiting**: 50 requests/30s (5000 with API key)
- **Data Enrichment**: CVSS scores, severity classification
- **Deduplication**: Automatic duplicate prevention

### Manual Ingestion
```bash
# Trigger immediate data fetch
curl -X POST http://localhost:8000/api/ingest
```

## 🎨 UI Features

### Futuristic Design Elements
- **Glassmorphism**: Frosted glass effects on cards
- **Neon Accents**: Subtle glowing hover effects
- **Gradient Backgrounds**: Animated gradient overlays
- **Parallax Scrolling**: Smooth depth effects
- **Typewriter Effects**: Animated text transitions
- **Cursor Glow**: Interactive cursor following effects

### Responsive Design
- **Mobile First**: Optimized for all screen sizes
- **Touch Friendly**: Gesture support for mobile
- **Performance**: Optimized loading and animations

## 🔒 Security Features

- **CORS Protection**: Proper cross-origin resource sharing
- **Input Validation**: Pydantic models for data validation
- **SQL Injection Prevention**: SQLAlchemy ORM protection
- **Rate Limiting**: API rate limiting and throttling
- **Error Handling**: Secure error responses

## 📝 Development

### Project Structure
```
thandev/
├── backend/           # FastAPI backend
│   ├── app/          # Application code
│   ├── migrations/   # Database migrations
│   └── requirements.txt
├── frontend/         # Next.js frontend
│   ├── app/         # App Router pages
│   ├── components/  # React components
│   └── package.json
├── docker-compose.yml
└── README.md
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Support

For support, email support@thandev.com or create an issue on GitHub.

## 🎯 Roadmap

- [ ] Additional data sources (CVE Details, ExploitDB)
- [ ] Machine learning threat scoring
- [ ] Real-time notifications
- [ ] API rate limiting dashboard
- [ ] Advanced search and filtering
- [ ] Export functionality (CSV, JSON)
- [ ] User authentication and profiles
- [ ] Custom watchlists and alerts

---

**Built with ❤️ for the security community**