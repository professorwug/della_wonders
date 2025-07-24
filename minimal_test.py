#!/usr/bin/env python3
"""
Minimal test script that makes a simple HTTP request
"""

import requests
import sys

def main():
    print("Making HTTP request...")
    try:
        # This should be intercepted by the proxy
        response = requests.get("http://httpbin.org/get", timeout=10)
        print(f"Status: {response.status_code}")
        print("✓ Request completed successfully!")
        return 0
    except Exception as e:
        print(f"✗ Request failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())