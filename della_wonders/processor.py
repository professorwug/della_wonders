"""
Internet-side processor that handles requests from airgapped proxy
"""

import json
import time
import hashlib
import base64
import requests
import os
from pathlib import Path
from datetime import datetime, timezone
import logging
from typing import Dict
import signal
import sys

from .security import SecurityFilter


class WonderDellaProcessor:
    """Internet-side processor for handling requests with security filtering"""
    
    def __init__(self, shared_dir="/tmp/shared"):
        self.shared_dir = Path(shared_dir)
        self.request_dir = self.shared_dir / "requests"
        self.response_dir = self.shared_dir / "responses"
        self.security_filter = SecurityFilter()
        self.session = requests.Session()
        self.running = True
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Ensure directories exist
        for dir_path in [self.request_dir, self.response_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
    def add_blocked_domain(self, domain: str):
        """Add a domain to the security filter blocklist"""
        self.security_filter.add_blocked_domain(domain)
        
    def add_allowed_domain(self, domain: str):
        """Legacy method - add_allowed_domain is deprecated"""
        self.logger.warning("add_allowed_domain is deprecated - use add_blocked_domain to block specific domains")
        # Do nothing since we're now using blocklist approach
        
    def process_requests(self):
        """Main processing loop"""
        self.logger.info("Started wonder_della processor")
        self.logger.info(f"Monitoring: {self.request_dir}")
        self.logger.info(f"Writing to: {self.response_dir}")
        
        while self.running:
            try:
                # Process all pending request files
                request_files = list(self.request_dir.glob("*.json"))
                if request_files:
                    self.logger.info(f"Found {len(request_files)} request files")
                    
                for request_file in request_files:
                    if not self.running:
                        break
                    self.process_single_request(request_file)
                    
                time.sleep(0.5)  # Polling interval
            except KeyboardInterrupt:
                self.logger.info("Received interrupt signal")
                self.running = False
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(1)
                
    def process_single_request(self, request_file: Path):
        """Process a single request file"""
        request_id = request_file.stem
        response_file = self.response_dir / f"{request_id}.json"
        
        # Skip if response already exists
        if response_file.exists():
            return
            
        try:
            # Load request
            with request_file.open() as f:
                request_data = json.load(f)
                
            self.logger.info(f"Processing request {request_id}")
                
            # Validate request
            is_valid, reason = self.security_filter.validate_request(request_data)
            if not is_valid:
                self.logger.warning(f"Request {request_id} blocked: {reason}")
                self.create_error_response(request_id, 403, f"Blocked: {reason}")
                return
                
            # Make HTTP request
            request_info = request_data['request']
            self.logger.info(f"Making request: {request_info['method']} {request_info['url']}")
            response = self.make_http_request(request_data)
            
            # Filter response
            filtered_content, was_filtered = self.security_filter.filter_response(response.content)
            
            if was_filtered:
                self.logger.warning(f"Response content was filtered for {request_id}")
            
            # Create response JSON
            response_data = {
                "metadata": {
                    "request_id": request_id,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "processor_version": "1.0.0",
                    "security_status": "approved"
                },
                "response": {
                    "status_code": response.status_code,
                    "reason": response.reason,
                    "headers": dict(response.headers),
                    "content": base64.b64encode(filtered_content).decode('utf-8'),
                    "http_version": "HTTP/1.1"
                },
                "security": {
                    "content_filtered": was_filtered,
                    "response_hash": hashlib.sha256(filtered_content).hexdigest(),
                    "scan_results": {"malware": False, "suspicious_content": False}
                }
            }
            
            # Atomic write
            temp_path = response_file.with_suffix(".json.tmp")
            with temp_path.open("w") as f:
                json.dump(response_data, f, indent=2)
            os.rename(temp_path, response_file)
            
            self.logger.info(f"Response written for {request_id}")
            
        except Exception as e:
            self.logger.error(f"Error processing {request_id}: {e}")
            self.create_error_response(request_id, 502, f"Processing error: {str(e)}")
            
    def make_http_request(self, request_data: Dict) -> requests.Response:
        """Make the actual HTTP request"""
        request = request_data["request"]
        content = base64.b64decode(request["content"]) if request["content"] else None
        
        # Remove proxy-related headers that might interfere
        headers = dict(request["headers"])
        headers.pop("Proxy-Connection", None)
        headers.pop("Proxy-Authorization", None)
        
        try:
            response = self.session.request(
                method=request["method"],
                url=request["url"],
                headers=headers,
                data=content,
                timeout=30,
                verify=True,
                allow_redirects=True
            )
            return response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"HTTP request failed: {e}")
            # Create a mock response for the error
            mock_response = requests.Response()
            mock_response.status_code = 502
            mock_response.reason = "Bad Gateway"
            mock_response._content = f"Request failed: {str(e)}".encode()
            mock_response.headers = {"Content-Type": "text/plain"}
            return mock_response
        
    def create_error_response(self, request_id: str, status_code: int, message: str):
        """Create an error response"""
        error_content = message.encode('utf-8')
        response_data = {
            "metadata": {
                "request_id": request_id,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "processor_version": "1.0.0",
                "security_status": "error"
            },
            "response": {
                "status_code": status_code,
                "reason": "Error",
                "headers": {"Content-Type": "text/plain"},
                "content": base64.b64encode(error_content).decode('utf-8'),
                "http_version": "HTTP/1.1"
            },
            "security": {
                "content_filtered": False,
                "response_hash": hashlib.sha256(error_content).hexdigest(),
                "scan_results": {"malware": False, "suspicious_content": False}
            }
        }
        
        response_file = self.response_dir / f"{request_id}.json"
        temp_path = response_file.with_suffix(".json.tmp")
        with temp_path.open("w") as f:
            json.dump(response_data, f, indent=2)
        os.rename(temp_path, response_file)
        
    def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down wonder_della processor")
        self.running = False
        
    def run(self):
        """Main entry point with signal handling"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down...")
            self.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            self.process_requests()
        except Exception as e:
            self.logger.error(f"Fatal error: {e}")
            raise