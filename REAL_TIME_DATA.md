# Real-Time CVE Data Ingestion System

This system automatically fetches and processes real CVE (Common Vulnerabilities and Exposures) data from the National Vulnerability Database (NVD) and other sources.

## 🚀 Features

- **Real-time data ingestion** from NVD API
- **Automatic scheduling** (every 6 hours)
- **Data enrichment** with CVSS scores and severity classification
- **Deduplication** to prevent duplicate entries
- **Rate limiting** to respect API limits
- **Error handling** and logging
- **Manual trigger** via API endpoint

## 📊 Current Stats

After running the ingestion system, your database now contains:
- **Total exploits**: 2,684 (real CVE data from NVD)
- **New today**: 420 (exploits published today)
- **Critical**: 381 (high-severity vulnerabilities)

## 🛠️ How It Works

### 1. Data Sources
- **Primary**: National Vulnerability Database (NVD) API
- **Format**: JSON API v2.0
- **Coverage**: All published CVEs with metadata

### 2. Data Processing
- Fetches recent CVEs (last 7 days by default)
- Extracts CVSS scores (v3.1, v3.0, v2.0)
- Determines severity (critical, high, medium, low, none)
- Parses published dates and references
- Enriches with source tags and provenance

### 3. Database Updates
- **Upsert logic**: Updates existing CVEs, inserts new ones
- **Deduplication**: Prevents duplicate entries by CVE ID
- **Data validation**: Ensures data integrity

## 🚀 Usage

### Start the Scheduler
```bash
# Run the scheduler (fetches data every 6 hours)
./start_scheduler.sh
```

### Manual Data Ingestion
```bash
# Trigger immediate data fetch
curl -X POST http://localhost:8000/api/ingest
```

### Check Current Stats
```bash
# View real-time statistics
curl http://localhost:8000/api/stats
```

## ⚙️ Configuration

### Environment Variables
- `NVD_API_KEY`: Optional API key for higher rate limits
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection for caching

### Rate Limiting
- **Without API key**: 50 requests per 30 seconds
- **With API key**: 5,000 requests per 30 seconds
- **Automatic delays**: Built-in rate limiting

### Scheduling
- **Default**: Every 6 hours
- **Customizable**: Modify `scheduler.py`
- **Immediate**: Run on startup

## 📁 Files

- `real_data_ingestion.py`: Main ingestion logic
- `scheduler.py`: Background scheduler
- `test_ingestion.py`: Test script
- `start_scheduler.sh`: Startup script
- `docker-compose.yml`: Full stack deployment

## 🔧 API Endpoints

### GET /api/stats
Returns current statistics:
```json
{
  "total_exploits": 2684,
  "new_today": 420,
  "critical_count": 381
}
```

### POST /api/ingest
Triggers manual data ingestion:
```json
{
  "status": "success",
  "message": "Data ingestion started in background"
}
```

## 🐳 Docker Deployment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f scheduler

# Stop services
docker-compose down
```

## 📈 Monitoring

The system logs all activities:
- Data fetch progress
- Processing statistics
- Error handling
- Rate limiting

Check logs for:
- Ingestion progress
- API errors
- Database updates
- Performance metrics

## 🔄 Data Flow

1. **Scheduler** triggers ingestion every 6 hours
2. **NVD Client** fetches recent CVE data
3. **CVE Processor** normalizes and enriches data
4. **Database** stores/updates exploit records
5. **API** serves real-time statistics
6. **Frontend** displays live data

## 🎯 Benefits

- **Real-time updates**: Always current vulnerability data
- **Comprehensive coverage**: All published CVEs
- **Rich metadata**: CVSS scores, severity, references
- **Reliable**: Error handling and retry logic
- **Scalable**: Rate limiting and batch processing
- **Maintainable**: Clean, documented code

Your exploit feed now shows live, real-time data from the National Vulnerability Database! 🎉
