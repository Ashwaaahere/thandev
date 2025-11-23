"""
Locust test file for backend performance testing
"""
import os
import json
import time
from locust import HttpUser, task, between
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging

class WebsiteUser(HttpUser):
    """Locust user class for testing website performance"""
    
    # Wait between requests (1-2 seconds)
    wait_time = between(1, 2)
    
    def on_start(self):
        """Called when a user starts"""
        self.domain = os.getenv('DOMAIN', 'example.com')
        self.base_url = f"https://{self.domain}"
        
    @task(1)
    def get_homepage(self):
        """Test the homepage"""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_robots_txt(self):
        """Test robots.txt"""
        with self.client.get("/robots.txt", catch_response=True) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_sitemap(self):
        """Test sitemap.xml"""
        with self.client.get("/sitemap.xml", catch_response=True) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

def generate_summary():
    """Generate a summary of the test results"""
    stats = Environment.instance.stats
    
    # Calculate metrics
    total_requests = stats.total.num_requests
    total_failures = stats.total.num_failures
    error_rate = (total_failures / total_requests * 100) if total_requests > 0 else 0
    
    # Get response times
    response_times = stats.total.response_times
    avg_response_time = stats.total.avg_response_time
    p95_response_time = response_times.get_percentile(0.95) if response_times else 0
    
    # Calculate RPS
    duration = time.time() - stats.start_time if hasattr(stats, 'start_time') else 0
    avg_rps = total_requests / duration if duration > 0 else 0
    
    return {
        "p95LatencyMs": round(p95_response_time, 2),
        "avgRps": round(avg_rps, 2),
        "errorRatePct": round(error_rate, 2),
        "totalRequests": total_requests,
        "durationSec": round(duration, 2),
        "avgResponseTimeMs": round(avg_response_time, 2),
        "totalFailures": total_failures
    }


