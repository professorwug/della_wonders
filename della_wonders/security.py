"""
Security filtering and validation for the store-and-forward proxy
"""

import re
import base64
import hashlib
import logging
from typing import Dict, List, Set, Tuple
from urllib.parse import urlparse


class SecurityFilter:
    """Security filter for validating requests and filtering responses"""
    
    def __init__(self):
        # Configure blocked domains and suspicious patterns
        self.blocked_domains: Set[str] = {
            # Add explicitly blocked domains here
            "malicious-site.com",
            "phishing-site.net",
            "spam-domain.org",
            # Add more dangerous domains as needed
        }
        self.blocked_patterns: List[str] = [
            r"(?i)\b(password|token|secret|key)\b=",
            r"(?i)\b(admin|root|administrator)\b",
            # Remove IP address blocking to allow API calls
        ]
        self.max_request_size = 1024 * 1024  # 1MB
        self.max_response_size = 10 * 1024 * 1024  # 10MB
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Legacy support - keep for backward compatibility but not used in validation
        self.allowed_domains: Set[str] = set()  # Deprecated
        
    def add_blocked_domain(self, domain: str):
        """Add a domain to the blocklist"""
        self.blocked_domains.add(domain)
        self.logger.info(f"Added domain to blocklist: {domain}")
        
    def remove_blocked_domain(self, domain: str):
        """Remove a domain from the blocklist"""
        self.blocked_domains.discard(domain)
        self.logger.info(f"Removed domain from blocklist: {domain}")
        
    def add_blocked_pattern(self, pattern: str):
        """Add a regex pattern to the block list"""
        self.blocked_patterns.append(pattern)
        self.logger.info(f"Added blocked pattern: {pattern}")
        
    # Legacy methods for backward compatibility
    def add_allowed_domain(self, domain: str):
        """Legacy method - no longer used in validation"""
        self.allowed_domains.add(domain)
        self.logger.warning(f"add_allowed_domain is deprecated - domain allowlist no longer used: {domain}")
        
    def remove_allowed_domain(self, domain: str):
        """Legacy method - no longer used in validation"""
        self.allowed_domains.discard(domain)
        self.logger.warning(f"remove_allowed_domain is deprecated - domain allowlist no longer used: {domain}")
        
    def validate_request(self, request_data: Dict) -> Tuple[bool, str]:
        """Validate request against security policies"""
        request = request_data["request"]
        
        # Check domain blocklist - BLOCK if in blocklist
        parsed_url = urlparse(request["url"])
        if parsed_url.hostname in self.blocked_domains:
            return False, f"Domain {parsed_url.hostname} is blocked"
            
        # Check request size
        content = base64.b64decode(request["content"]) if request["content"] else b""
        if len(content) > self.max_request_size:
            return False, f"Request size {len(content)} exceeds limit"
            
        # Check for suspicious patterns in URL and headers
        for pattern in self.blocked_patterns:
            if re.search(pattern, request["url"]) or \
               any(re.search(pattern, str(v)) for v in request["headers"].values()):
                self.logger.warning(f"Blocked pattern: {pattern}")
                return False, f"Suspicious pattern detected"
                
        return True, "Request approved"
        
    def filter_response(self, response_content: bytes) -> Tuple[bytes, bool]:
        """Filter response content for sensitive data"""
        # Check size limit
        if len(response_content) > self.max_response_size:
            return b"Response too large", True
            
        # Basic content filtering - could be enhanced
        try:
            content_str = response_content.decode('utf-8', errors='ignore')
            
            # Look for sensitive patterns in response
            for pattern in self.blocked_patterns:
                if re.search(pattern, content_str):
                    self.logger.warning(f"Filtered sensitive content: {pattern}")
                    # For now, just log - could modify content
        except Exception as e:
            self.logger.warning(f"Error during content filtering: {e}")
            
        return response_content, False
        
    def validate_response_integrity(self, response_content: bytes, expected_hash: str) -> bool:
        """Validate response integrity using SHA256 hash"""
        actual_hash = hashlib.sha256(response_content).hexdigest()
        return actual_hash == expected_hash