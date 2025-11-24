# Thandev Request Handling Capacity

## Current Configuration

### Backend (Fly.io)

**VM Resources:**
- **CPU**: 1 shared CPU core
- **Memory**: 256 MB RAM
- **Auto-scaling**: Enabled (min: 0, auto-start/stop)
- **Region**: `iad` (Washington, D.C.)

**Database Connection Pool:**
- **Pool Size**: 10 connections (PostgreSQL only)
- **Max Overflow**: 20 connections
- **Current DB**: SQLite (no connection pooling)
- **Pool Recycle**: 1 hour

### Frontend (Vercel)
- **Platform**: Next.js on Vercel
- **Auto-scaling**: Automatic
- **Limits**: Based on Vercel plan (Hobby/Pro/Enterprise)

---

## Rate Limits (Per IP Address)

### API Endpoints

| Endpoint | Rate Limit | Notes |
|----------|------------|-------|
| **Security Scan** (POST `/api/security-scan/`) | **10/minute** | Per IP address |
| **Security Scan Status** (GET `/api/security-scan/status/{id}`) | No limit | - |
| **Security Scan List** (GET `/api/security-scan/list`) | **30/minute** | Per IP address |
| **Performance Scan** (POST `/api/performance-scan/`) | **10/minute** | Per IP address |
| **Performance Scan Status** (GET `/api/performance-scan/{id}`) | No limit | - |
| **Exploits List** (GET `/api/exploits/`) | **100/minute** | Per IP address |
| **Exploits Stats** (GET `/api/exploits/stats`) | **30/minute** | Per IP address |
| **News** (GET `/news/`) | No limit | - |
| **Health Check** (GET `/health`) | No limit | - |

### Concurrency Limits

| Feature | Limit | Notes |
|---------|-------|-------|
| **Security Scans** | **3 concurrent** | Per user (not per IP) |
| **Backend Load Tests** | **2 concurrent** | Global limit |
| **Database Connections** | **10-30** | Depends on DB type |

---

## Theoretical Maximum Throughput

### Per Minute (Single IP)
- **Security Scans**: 10 requests/minute
- **Performance Scans**: 10 requests/minute
- **Exploits API**: 100 requests/minute
- **Combined**: ~120 requests/minute per IP

### Per Hour (Single IP)
- **Security Scans**: 600 requests/hour
- **Performance Scans**: 600 requests/hour
- **Exploits API**: 6,000 requests/hour
- **Combined**: ~7,200 requests/hour per IP

### Global Capacity (Multiple IPs)
- **Backend VM**: 1 CPU, 256MB RAM
- **Estimated**: 50-100 concurrent requests (lightweight operations)
- **Heavy operations** (scans): Limited by:
  - CPU: 1 core
  - Memory: 256MB
  - Database: SQLite (single writer)
  - Background tasks: Limited by memory

---

## Bottlenecks & Limitations

### Current Bottlenecks

1. **Backend Resources**
   - **CPU**: 1 shared core (can handle ~50-100 lightweight requests/sec)
   - **Memory**: 256MB (limits concurrent operations)
   - **Auto-scaling**: Starts at 0, may have cold start delays

2. **Database**
   - **SQLite**: Single writer, limited concurrency
   - **No connection pooling** for SQLite
   - **File-based**: I/O bound operations

3. **Background Tasks**
   - **Security scans**: Run in background (memory intensive)
   - **Cloud Run Jobs**: External dependency (if enabled)
   - **Limited by**: Available memory (256MB)

4. **Rate Limiting**
   - **Per-IP limits**: Prevents abuse but limits legitimate users
   - **No user-based limits**: All users share same IP limits

### Performance Characteristics

**Lightweight Requests** (Health check, status, exploits list):
- **Throughput**: 50-100 requests/second
- **Latency**: < 100ms
- **Bottleneck**: CPU

**Medium Requests** (News, exploits stats):
- **Throughput**: 20-50 requests/second
- **Latency**: 100-500ms
- **Bottleneck**: Database queries

**Heavy Requests** (Security/Performance scans):
- **Throughput**: Limited by rate limits (10/minute)
- **Latency**: 1-30 seconds (background processing)
- **Bottleneck**: Memory, external services (Cloud Run)

---

## Scaling Recommendations

### Immediate Improvements

1. **Increase Backend Resources**
   ```toml
   # In backend/fly.toml
   [[vm]]
     cpu_kind = "shared"
     cpus = 2          # Increase from 1
     memory_mb = 512  # Increase from 256
   ```

2. **Upgrade Database**
   - Switch from SQLite to PostgreSQL
   - Enables connection pooling (10-30 connections)
   - Better concurrency handling

3. **Add Caching**
   - Redis for frequently accessed data
   - Reduces database load
   - Improves response times

### Medium-term Improvements

1. **Multiple Instances**
   - Scale to 2-3 backend instances
   - Load balancing via Fly.io
   - Better fault tolerance

2. **User-based Rate Limiting**
   - Replace IP-based with user-based limits
   - Better for authenticated users
   - More fair distribution

3. **Background Job Queue**
   - Use Celery + Redis for scan jobs
   - Better resource management
   - Priority queuing

### Long-term Improvements

1. **Horizontal Scaling**
   - Auto-scale based on load
   - Multiple regions
   - CDN for static assets

2. **Database Optimization**
   - Read replicas
   - Connection pooling
   - Query optimization

3. **Monitoring & Alerting**
   - Track request rates
   - Monitor resource usage
   - Auto-scale triggers

---

## Current Capacity Summary

### Request Handling
- **Lightweight requests**: ~50-100/sec
- **Medium requests**: ~20-50/sec
- **Heavy requests**: 10/minute (rate limited)

### Concurrent Operations
- **Security scans**: 3 per user
- **Background jobs**: Limited by 256MB memory
- **Database connections**: 10-30 (PostgreSQL) or 1 (SQLite)

### Estimated Daily Capacity
- **Lightweight**: ~4-8 million requests/day
- **Medium**: ~1.7-4.3 million requests/day
- **Heavy (scans)**: ~14,400 scans/day (10/min × 60 × 24)

### Real-World Capacity
- **Typical usage**: 100-1,000 requests/hour
- **Peak usage**: 5,000-10,000 requests/hour
- **Current setup**: Handles typical usage easily
- **Bottleneck**: Heavy operations (scans) due to memory limits

---

## Monitoring

To check current capacity:
```bash
# Backend logs
fly logs -a thandev-backend

# Check resource usage
fly status -a thandev-backend

# Monitor rate limits
# Check response headers: X-RateLimit-Limit, X-RateLimit-Remaining
```

---

## Recommendations

**For Current Setup:**
- ✅ Handles typical usage (100-1,000 req/hour) easily
- ⚠️ May struggle with sustained high load (>5,000 req/hour)
- ⚠️ Memory limits affect concurrent scan operations

**To Handle More Traffic:**
1. Increase backend memory to 512MB-1GB
2. Upgrade to PostgreSQL
3. Add Redis caching
4. Scale to 2-3 instances for redundancy

**For Production:**
- Monitor request rates and resource usage
- Set up alerts for high load
- Plan for auto-scaling
- Consider load testing

