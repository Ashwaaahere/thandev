# 🚀 ZAP Deployment to Fly.io

## **Deployment Summary**

ZAP (OWASP ZAP Proxy) has been deployed to Fly.io as a private service accessible via `.flycast` DNS.

---

## **Configuration**

### **Service Details**
- **App Name:** `thandev-zap`
- **Image:** `ghcr.io/zaproxy/zaproxy:stable`
- **Region:** `iad` (same as other services)
- **Port:** `8090` (API), `8080` (Proxy)
- **Access:** Private via `.flycast` DNS

### **Fly.toml**
**File:** `services/zap-fly/fly.toml`

```toml
app = "thandev-zap"
primary_region = "iad"

[build]
  image = "ghcr.io/zaproxy/zaproxy:stable"

[[services]]
  protocol = "tcp"
  internal_port = 8090
  processes = ["app"]
  
  [[services.ports]]
    handlers = ["http"]
    port = 8090

[processes]
  app = "zap.sh -daemon -host 0.0.0.0 -port 8090 -config api.disablekey=true ..."

[[vm]]
  cpu_kind = "shared"
  cpus = 2
  memory_mb = 2048
```

---

## **Runner Configuration**

### **Secret Updated**
```bash
fly secrets set ZAP_API_URL="http://thandev-zap.flycast:8090" -a thandev-runner
```

**Why `.flycast`:**
- More reliable than `.internal` DNS
- Works even when service is idle
- Routes through Fly Proxy

---

## **Verification**

After deployment, verify ZAP is accessible:

```bash
# Check ZAP service status
fly status -a thandev-zap

# Check ZAP logs
fly logs -a thandev-zap

# Test from runner (after restart)
fly logs -a thandev-runner | grep -i "zap.*accessible"
```

---

## **Expected Behavior**

1. ✅ ZAP service runs on Fly.io
2. ✅ Runner connects to ZAP via `http://thandev-zap.flycast:8090`
3. ✅ ZAP scans execute successfully
4. ✅ No more "ZAP API not accessible" errors

---

**Status:** ✅ **ZAP DEPLOYED TO FLY.IO**
