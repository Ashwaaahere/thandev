#!/usr/bin/env python3
"""
Real-time CVE data ingestion from NVD and other sources
"""
import os
import sys
import time
import json
import logging
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from models import Exploit

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/thandev")
engine = create_engine(DATABASE_URL, future=True)
Session = sessionmaker(bind=engine)

class NVDAPIClient:
    """Client for fetching CVE data from NVD API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"apiKey": api_key})
        
        # Rate limiting: NVD allows 50 requests per 30 seconds without API key
        # With API key: 5000 requests per 30 seconds
        self.rate_limit = 0.6 if not api_key else 0.006  # seconds between requests
        self.last_request = 0
    
    def _rate_limit_wait(self):
        """Implement rate limiting"""
        elapsed = time.time() - self.last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request = time.time()
    
    def fetch_cves(self, start_index: int = 0, results_per_page: int = 2000, 
                   pub_start_date: Optional[str] = None, 
                   pub_end_date: Optional[str] = None) -> Dict[str, Any]:
        """Fetch CVE data from NVD API"""
        self._rate_limit_wait()
        
        params = {
            "startIndex": start_index,
            "resultsPerPage": results_per_page
        }
        
        if pub_start_date:
            params["pubStartDate"] = pub_start_date
        if pub_end_date:
            params["pubEndDate"] = pub_end_date
        
        try:
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            LOG.error(f"Error fetching CVE data: {e}")
            return {}
    
    def fetch_recent_cves(self, days: int = 7) -> List[Dict[str, Any]]:
        """Fetch CVE data from the last N days"""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%S.000")
        end_date_str = end_date.strftime("%Y-%m-%dT%H:%M:%S.000")
        
        all_cves = []
        start_index = 0
        results_per_page = 2000
        
        while True:
            LOG.info(f"Fetching CVEs from NVD (start_index={start_index})")
            data = self.fetch_cves(
                start_index=start_index,
                results_per_page=results_per_page,
                pub_start_date=start_date_str,
                pub_end_date=end_date_str
            )
            
            if not data or "vulnerabilities" not in data:
                break
                
            cves = data.get("vulnerabilities", [])
            if not cves:
                break
                
            all_cves.extend(cves)
            LOG.info(f"Fetched {len(cves)} CVEs (total: {len(all_cves)})")
            
            # Check if we have more data
            total_results = data.get("totalResults", 0)
            if start_index + len(cves) >= total_results:
                break
                
            start_index += len(cves)
            
            # Be respectful to the API
            time.sleep(1)
        
        return all_cves

class CVEProcessor:
    """Process and normalize CVE data"""
    
    def __init__(self):
        self.session = Session()
    
    def _extract_cvss_score(self, cve_item: Dict[str, Any]) -> Optional[float]:
        """Extract CVSS score from CVE data"""
        try:
            metrics = cve_item.get("cve", {}).get("metrics", {})
            
            # Try CVSS v3.1 first
            cvss_v31 = metrics.get("cvssMetricV31", [])
            if cvss_v31 and len(cvss_v31) > 0:
                return float(cvss_v31[0].get("cvssData", {}).get("baseScore", 0))
            
            # Try CVSS v3.0
            cvss_v30 = metrics.get("cvssMetricV30", [])
            if cvss_v30 and len(cvss_v30) > 0:
                return float(cvss_v30[0].get("cvssData", {}).get("baseScore", 0))
            
            # Try CVSS v2
            cvss_v2 = metrics.get("cvssMetricV2", [])
            if cvss_v2 and len(cvss_v2) > 0:
                return float(cvss_v2[0].get("cvssData", {}).get("baseScore", 0))
                
        except (ValueError, KeyError, TypeError):
            pass
        
        return None
    
    def _determine_severity(self, cvss_score: Optional[float]) -> str:
        """Determine severity based on CVSS score"""
        if cvss_score is None:
            return "none"
        
        if cvss_score >= 9.0:
            return "critical"
        elif cvss_score >= 7.0:
            return "high"
        elif cvss_score >= 4.0:
            return "medium"
        elif cvss_score > 0:
            return "low"
        else:
            return "none"
    
    def _extract_published_date(self, cve_item: Dict[str, Any]) -> Optional[datetime]:
        """Extract published date from CVE data"""
        try:
            cve = cve_item.get("cve", {})
            published = cve.get("published")
            if published:
                # Parse ISO format with timezone
                return datetime.fromisoformat(published.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
        return None
    
    def _extract_references(self, cve_item: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract references from CVE data"""
        references = []
        try:
            cve = cve_item.get("cve", {})
            refs = cve.get("references", [])
            
            for ref in refs:
                url = ref.get("url", "")
                if url:
                    references.append({
                        "url": url,
                        "source": ref.get("source", "reference")
                    })
        except (KeyError, TypeError):
            pass
        
        return references
    
    def process_cve(self, cve_item: Dict[str, Any]) -> Optional[Exploit]:
        """Process a single CVE item and return an Exploit object"""
        try:
            cve = cve_item.get("cve", {})
            cve_id = cve.get("id")
            
            if not cve_id:
                return None
            
            # Extract basic info
            descriptions = cve.get("descriptions", [])
            title = None
            description = None
            
            for desc in descriptions:
                if desc.get("lang", "").lower().startswith("en"):
                    if not title:
                        title = desc.get("value", "")[:512]
                    if not description:
                        description = desc.get("value", "")[:2000]
            
            if not title:
                title = cve_id
            
            # Extract CVSS and severity
            cvss_score = self._extract_cvss_score(cve_item)
            severity = self._determine_severity(cvss_score)
            
            # Extract published date
            published_at = self._extract_published_date(cve_item)
            
            # Extract references
            references = self._extract_references(cve_item)
            
            # Create Exploit object
            exploit = Exploit(
                cve_id=cve_id,
                title=title,
                description=description or "",
                cvss_v3=cvss_score,
                severity=severity,
                published_at=published_at,
                references=references,
                source_tags=["nvd"],
                provenance={
                    "source": "nvd",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "raw_id": cve_id
                }
            )
            
            return exploit
            
        except Exception as e:
            LOG.error(f"Error processing CVE {cve_item.get('cve', {}).get('id', 'unknown')}: {e}")
            return None
    
    def upsert_exploit(self, exploit: Exploit) -> bool:
        """Upsert an exploit into the database"""
        try:
            # Check if exploit already exists
            existing = self.session.query(Exploit).filter(
                Exploit.cve_id == exploit.cve_id
            ).first()
            
            if existing:
                # Update existing
                existing.title = exploit.title
                existing.description = exploit.description
                existing.cvss_v3 = exploit.cvss_v3
                existing.severity = exploit.severity
                existing.published_at = exploit.published_at
                existing.references = exploit.references
                existing.source_tags = list(set((existing.source_tags or []) + ["nvd"]))
                existing.provenance = {**(existing.provenance or {}), **exploit.provenance}
                existing.updated_at = datetime.now(timezone.utc)
                LOG.info(f"Updated CVE {exploit.cve_id}")
            else:
                # Insert new
                self.session.add(exploit)
                LOG.info(f"Inserted CVE {exploit.cve_id}")
            
            self.session.commit()
            return True
            
        except Exception as e:
            LOG.error(f"Error upserting CVE {exploit.cve_id}: {e}")
            self.session.rollback()
            return False
    
    def process_cves(self, cve_items: List[Dict[str, Any]]) -> Dict[str, int]:
        """Process multiple CVE items and return statistics"""
        stats = {"processed": 0, "inserted": 0, "updated": 0, "errors": 0}
        
        for cve_item in cve_items:
            try:
                exploit = self.process_cve(cve_item)
                if exploit:
                    # Check if it's new or update
                    existing = self.session.query(Exploit).filter(
                        Exploit.cve_id == exploit.cve_id
                    ).first()
                    
                    if self.upsert_exploit(exploit):
                        stats["processed"] += 1
                        if existing:
                            stats["updated"] += 1
                        else:
                            stats["inserted"] += 1
                    else:
                        stats["errors"] += 1
                else:
                    stats["errors"] += 1
                    
            except Exception as e:
                LOG.error(f"Error processing CVE item: {e}")
                stats["errors"] += 1
        
        return stats

def main():
    """Main ingestion function"""
    LOG.info("Starting real-time CVE data ingestion")
    
    # Initialize clients
    nvd_client = NVDAPIClient(api_key=os.getenv("NVD_API_KEY"))
    processor = CVEProcessor()
    
    try:
        # Fetch recent CVEs (last 7 days)
        LOG.info("Fetching recent CVEs from NVD...")
        cve_items = nvd_client.fetch_recent_cves(days=7)
        
        if not cve_items:
            LOG.warning("No CVE data fetched")
            return
        
        LOG.info(f"Processing {len(cve_items)} CVE items...")
        stats = processor.process_cves(cve_items)
        
        LOG.info(f"Ingestion complete: {stats}")
        
    except Exception as e:
        LOG.error(f"Error during ingestion: {e}")
    finally:
        processor.session.close()

if __name__ == "__main__":
    main()
