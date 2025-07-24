#!/usr/bin/env python3
"""
Example script to test the store-and-forward proxy system
This script makes various HTTP requests that will be intercepted by the proxy
"""

import requests
import json
import time
import sys

def test_basic_get():
    """Test basic GET request"""
    print("=== Testing basic GET request ===")
    try:
        response = requests.get("http://httpbin.org/get")
        print(f"Status: {response.status_code}")
        print(f"Content length: {len(response.content)} bytes")
        data = response.json()
        print(f"Origin IP reported by httpbin: {data.get('origin', 'N/A')}")
        print("✓ GET request successful")
    except Exception as e:
        print(f"✗ GET request failed: {e}")
    print()

def test_post_request():
    """Test POST request with JSON data"""
    print("=== Testing POST request ===")
    try:
        payload = {"message": "Hello from airgapped machine!", "timestamp": time.time()}
        response = requests.post(
            "http://httpbin.org/post", 
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Echo data: {data.get('json', 'N/A')}")
        print("✓ POST request successful")
    except Exception as e:
        print(f"✗ POST request failed: {e}")
    print()

def test_multiple_requests():
    """Test multiple concurrent-ish requests"""
    print("=== Testing multiple requests ===")
    urls = [
        "http://httpbin.org/uuid",
        "http://httpbin.org/user-agent", 
        "http://httpbin.org/headers"
    ]
    
    for i, url in enumerate(urls, 1):
        try:
            print(f"Request {i}/{len(urls)}: {url}")
            response = requests.get(url)
            print(f"  Status: {response.status_code}, Size: {len(response.content)} bytes")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
        time.sleep(1)  # Small delay between requests
    print("✓ Multiple requests completed")
    print()

def test_json_api():
    """Test a JSON API endpoint"""
    print("=== Testing JSON API ===")
    try:
        response = requests.get("http://jsonplaceholder.typicode.com/posts/1")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Post title: {data.get('title', 'N/A')}")
        print(f"Post body: {data.get('body', 'N/A')[:50]}...")
        print("✓ JSON API request successful")
    except Exception as e:
        print(f"✗ JSON API request failed: {e}")
    print()

def test_blocked_domain():
    """Test request to a domain that should be blocked"""
    print("=== Testing blocked domain (should fail) ===")
    try:
        response = requests.get("http://malicious-site.com/data", timeout=10)
        print(f"✗ Unexpected success: {response.status_code}")
    except Exception as e:
        print(f"✓ Request properly blocked: {e}")
    print()

def main():
    print("🚀 Starting della_wonders test script")
    print("This script will make HTTP requests through the store-and-forward proxy")
    print("Make sure wonder_della.py is running on the internet-connected machine!")
    print()
    
    # Check if we're using a proxy
    proxy_env = requests.Session().proxies
    if proxy_env:
        print(f"Using proxy environment: {proxy_env}")
    else:
        print("No proxy detected in environment")
    print()
    
    # Run tests
    test_basic_get()
    test_post_request()
    test_multiple_requests()
    test_json_api()
    test_blocked_domain()
    
    print("🎉 Test script completed!")

if __name__ == "__main__":
    main()