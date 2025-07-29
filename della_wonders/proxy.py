"""
mitmproxy addon for store-and-forward proxy functionality
Compatible with mitmproxy 10.x API
"""

from mitmproxy import ctx, http
from pathlib import Path
import json
import uuid
import time
import hashlib
import base64
import os
from typing import Optional
from datetime import datetime, timezone
import logging


class StoreForwardAddon:
    """mitmproxy addon for serializing HTTP requests/responses to JSON files"""
    
    def __init__(self):
        self.shared_dir: Optional[Path] = None
        self.request_dir: Optional[Path] = None
        self.response_dir: Optional[Path] = None
        self.response_timeout = 300  # 5 minutes
        self.logger = logging.getLogger(__name__)
        
    def load(self, loader):
        loader.add_option(
            "shared_dir", str, "/tmp/shared",
            "Directory for request/response exchange"
        )
        
    def configure(self, updates):
        if "shared_dir" in updates:
            self.shared_dir = Path(ctx.options.shared_dir)
            self.request_dir = self.shared_dir / "requests"
            self.response_dir = self.shared_dir / "responses"
            
            # Ensure directories exist
            for dir_path in [self.request_dir, self.response_dir]:
                dir_path.mkdir(parents=True, exist_ok=True)
                
            ctx.log.info(f"Store-forward addon configured with shared_dir: {self.shared_dir}")
                
    def request(self, flow: http.HTTPFlow) -> None:
        """Handle outgoing HTTP requests"""
        request_id = str(uuid.uuid4())
        
        try:
            # Get request content
            content = flow.request.content if flow.request.content else b""
            
            # Serialize request to JSON
            request_data = {
                "metadata": {
                    "request_id": request_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source_process": "target_script",
                    "proxy_version": "1.0.0"
                },
                "request": {
                    "method": flow.request.method,
                    "url": flow.request.pretty_url,
                    "headers": dict(flow.request.headers),
                    "content": base64.b64encode(content).decode('utf-8'),
                    "http_version": flow.request.http_version
                },
                "security": {
                    "content_hash": hashlib.sha256(content).hexdigest(),
                    "allowed_domains": [flow.request.pretty_host],
                    "max_response_size": 10 * 1024 * 1024  # 10MB limit
                }
            }
            
            # Atomic write to requests directory
            temp_path = self.request_dir / f"{request_id}.json.tmp"
            final_path = self.request_dir / f"{request_id}.json"
            
            with temp_path.open("w") as f:
                json.dump(request_data, f, indent=2)
            os.rename(temp_path, final_path)
            
            ctx.log.info(f"Serialized request {request_id} to {final_path}")
            
            # Wait for response
            response_path = self.response_dir / f"{request_id}.json"
            start_time = time.time()
            
            ctx.log.info(f"Waiting for response at {response_path}")
            
            while not response_path.exists():
                if time.time() - start_time > self.response_timeout:
                    flow.response = http.Response.make(
                        504,
                        b"Gateway Timeout: No response from relay",
                        {"Content-Type": "text/plain"}
                    )
                    ctx.log.error(f"Timeout waiting for response {request_id}")
                    return
                time.sleep(0.2)
                
            # Load and reconstruct response
            try:
                with response_path.open() as f:
                    response_data = json.load(f)
                    
                # Validate response integrity
                response_content = base64.b64decode(response_data["response"]["content"])
                expected_hash = response_data["security"]["response_hash"]
                actual_hash = hashlib.sha256(response_content).hexdigest()
                
                if expected_hash != actual_hash:
                    flow.response = http.Response.make(
                        502,
                        b"Response integrity check failed",
                        {"Content-Type": "text/plain"}
                    )
                    ctx.log.error(f"Integrity check failed for {request_id}")
                    
                    # Clean up files even on integrity failure
                    try:
                        response_path.unlink()
                        final_path.unlink()
                        ctx.log.info(f"Cleaned up files after integrity failure for {request_id}")
                    except OSError as cleanup_error:
                        ctx.log.warn(f"Failed to cleanup files after integrity failure for {request_id}: {cleanup_error}")
                    return
                    
                # Reconstruct HTTP response
                flow.response = http.Response.make(
                    response_data["response"]["status_code"],
                    response_content,
                    response_data["response"]["headers"]
                )
                flow.response.reason = response_data["response"]["reason"]
                
                ctx.log.info(f"Reconstructed response for {request_id}")
                
                # Clean up files after successful processing
                try:
                    # Delete the response file
                    response_path.unlink()
                    ctx.log.info(f"Deleted response file: {response_path}")
                    
                    # Delete the original request file  
                    final_path.unlink()
                    ctx.log.info(f"Deleted request file: {final_path}")
                    
                except OSError as cleanup_error:
                    ctx.log.warn(f"Failed to cleanup files for {request_id}: {cleanup_error}")
                    # Don't fail the request if cleanup fails
                
            except Exception as e:
                ctx.log.error(f"Error processing response {request_id}: {e}")
                flow.response = http.Response.make(
                    502,
                    f"Response processing error: {str(e)}".encode(),
                    {"Content-Type": "text/plain"}
                )
                
                # Clean up files even on processing error
                try:
                    if response_path.exists():
                        response_path.unlink()
                    if final_path.exists():
                        final_path.unlink()
                    ctx.log.info(f"Cleaned up files after processing error for {request_id}")
                except OSError as cleanup_error:
                    ctx.log.warn(f"Failed to cleanup files after processing error for {request_id}: {cleanup_error}")
                
        except Exception as e:
            ctx.log.error(f"Error in request handler: {e}")
            flow.response = http.Response.make(
                500,
                f"Proxy error: {str(e)}".encode(),
                {"Content-Type": "text/plain"}
            )


addons = [StoreForwardAddon()]