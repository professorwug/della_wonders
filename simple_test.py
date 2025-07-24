#!/usr/bin/env python3
"""
Simple test script to verify basic HTTP functionality
"""

import requests
import time

def main():
    print("Simple HTTP test")
    try:
        response = requests.get("http://httpbin.org/get", timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Response size: {len(response.content)} bytes")
        if response.status_code == 200:
            print("✓ Test successful!")
        else:
            print("✗ Unexpected status code")
    except Exception as e:
        print(f"✗ Test failed: {e}")

if __name__ == "__main__":
    main()