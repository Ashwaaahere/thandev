"""
Nmap output parser
Parses Nmap XML output into normalized findings
"""
import xml.etree.ElementTree as ET
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def parse_nmap_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse Nmap XML output file into normalized findings.
    
    Each open port becomes a finding with service information.
    
    Returns a list of normalized finding dicts with fields:
    - tool_id: "nmap"
    - title: Finding title
    - severity: "info" (nmap is discovery, not direct vuln)
    - description: Finding description
    - evidence: Port and service information
    - host: Target host
    - url: Service URL if applicable
    - raw: Original XML data (optional)
    
    Args:
        path: Path to the Nmap XML output file
        
    Returns:
        List of normalized finding dicts (empty list if file is empty/missing)
    """
    if not path.exists():
        logger.info("Nmap output file is empty or missing for %s; treating as no findings", path)
        return []
    
    file_size = path.stat().st_size
    if file_size == 0:
        logger.info("Nmap output file is empty for %s; treating as no findings", path)
        return []
    
    findings: List[Dict[str, Any]] = []
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Extract host information
        for host in root.findall("host"):
            # Get host address
            address_elem = host.find("address")
            host_ip = address_elem.get("addr") if address_elem is not None else "unknown"
            
            # Get hostname
            hostname_elem = host.find("hostnames/hostname")
            hostname = hostname_elem.get("name") if hostname_elem is not None else host_ip
            
            # Get ports
            ports_elem = host.find("ports")
            if ports_elem is None:
                continue
            
            # Check for extraports (filtered/closed ports summary)
            extraports = ports_elem.find("extraports")
            extraports_state = None
            extraports_count = 0
            if extraports is not None:
                extraports_state = extraports.get("state", "")
                extraports_count = int(extraports.get("count", "0"))
            
            # Track if we found any open ports
            open_ports_found = False
            
            for port in ports_elem.findall("port"):
                port_id = port.get("portid")
                protocol = port.get("protocol", "tcp")
                
                state_elem = port.find("state")
                if state_elem is None:
                    continue
                
                state = state_elem.get("state", "unknown")
                
                # Track open ports
                if state == "open":
                    open_ports_found = True
                # Only report open ports (filtered/closed ports are not security findings)
                elif state != "open":
                    continue
                
                # Get service information
                service_elem = port.find("service")
                service_name = service_elem.get("name") if service_elem is not None else "unknown"
                service_product = service_elem.get("product") if service_elem is not None else None
                service_version = service_elem.get("version") if service_elem is not None else None
                service_extrainfo = service_elem.get("extrainfo") if service_elem is not None else None
                
                # Build service description
                service_desc_parts = [service_name]
                if service_product:
                    service_desc_parts.append(service_product)
                if service_version:
                    service_desc_parts.append(service_version)
                if service_extrainfo:
                    service_desc_parts.append(service_extrainfo)
                service_desc = " ".join(service_desc_parts)
                
                # Determine URL if HTTP/HTTPS
                url = None
                if service_name in ["http", "http-proxy", "ssl/http"]:
                    scheme = "https" if port_id == "443" or "ssl" in service_name.lower() else "http"
                    url = f"{scheme}://{hostname}:{port_id}" if port_id not in ["80", "443"] else f"{scheme}://{hostname}"
                
                # Build title
                title = f"Open port {port_id}/{protocol} ({service_name})"
                if service_product:
                    title += f" - {service_product}"
                
                # Build description
                description = f"Port {port_id}/{protocol} is open on {hostname} ({host_ip}). "
                if service_desc:
                    description += f"Service: {service_desc}. "
                description += "This port should be reviewed for security implications."
                
                # Build evidence
                evidence = f"Port {port_id}/{protocol} open on {hostname}"
                if service_desc:
                    evidence += f" - {service_desc}"
                
                finding = {
                    "tool_id": "nmap",
                    "title": title,
                    "severity": "info",  # Nmap is discovery, not direct vulnerability
                    "description": description,
                    "evidence": evidence,
                    "host": hostname,
                    "url": url,
                    "raw": {
                        "host": hostname,
                        "ip": host_ip,
                        "port": port_id,
                        "protocol": protocol,
                        "service": service_name,
                        "product": service_product,
                        "version": service_version,
                        "extrainfo": service_extrainfo,
                    },
                }
                
                findings.append(finding)
            
            # If no open ports were found but we have filtered ports, report them as informational findings
            # This ensures nmap scans always produce some results when ports are discovered (even if filtered)
            if not open_ports_found and extraports_state == "filtered" and extraports_count > 0:
                # Extract port ranges from extraports if available
                extraports_reasons = extraports.findall("extrareasons")
                port_ranges = []
                for reason in extraports_reasons:
                    ports_attr = reason.get("ports", "")
                    if ports_attr:
                        port_ranges.append(ports_attr)
                
                # Create informational finding about filtered ports
                filtered_ports_desc = f"{extraports_count} ports are filtered (no response)"
                if port_ranges:
                    filtered_ports_desc += f" on ports: {', '.join(port_ranges[:3])}"  # Show first 3 ranges
                    if len(port_ranges) > 3:
                        filtered_ports_desc += f" and {len(port_ranges) - 3} more"
                
                findings.append({
                    "tool_id": "nmap",
                    "title": f"Filtered ports detected on {hostname}",
                    "severity": "info",
                    "description": f"Nmap scan detected {extraports_count} filtered ports on {hostname} ({host_ip}). Filtered ports typically indicate firewall rules or network filtering. {filtered_ports_desc}.",
                    "evidence": f"{extraports_count} filtered ports detected on {hostname}",
                    "host": hostname,
                    "url": None,
                    "raw": {
                        "host": hostname,
                        "ip": host_ip,
                        "filtered_ports_count": extraports_count,
                        "port_ranges": port_ranges,
                    },
                })
        
        logger.info("Parsed %d nmap findings from file %s", len(findings), path)
        return findings
        
    except ET.ParseError as e:
        logger.error("Failed to parse Nmap XML output from %s: %s", path, e, exc_info=True)
        return []
    except Exception as e:
        logger.error("Error processing Nmap output from %s: %s", path, e, exc_info=True)
        return []





