#!/usr/bin/env python3
"""
Comprehensive test script for della_wonders DNS resolution reliability
Tests many requests to httpbun.org with random intervals to stress-test cache management
"""

import requests
import time
import random
from collections import defaultdict, Counter
import statistics
import sys
from datetime import datetime


def main():
    """Run comprehensive DNS resolution tests"""
    print("🧪 Comprehensive della_wonders DNS Resolution Test")
    print("=" * 60)
    
    # Test configuration
    num_tests = 60  # Many dozen tests
    base_url = "http://httpbun.org"
    endpoints = ["/get", "/json", "/user-agent", "/headers", "/ip"]
    
    # Results tracking
    results = []
    errors = Counter()
    response_times = []
    status_codes = Counter()
    start_time = datetime.now()
    
    print(f"Running {num_tests} tests to {base_url}")
    print(f"Random intervals: 0.01-1.0 seconds")
    print(f"Start time: {start_time.strftime('%H:%M:%S')}")
    print("-" * 60)
    
    for i in range(num_tests):
        # Random endpoint selection
        endpoint = random.choice(endpoints)
        url = f"{base_url}{endpoint}"
        
        # Random delay between requests
        delay = random.uniform(0.01, 1.0)
        time.sleep(delay)
        
        # Progress indicator
        if (i + 1) % 10 == 0 or i == 0:
            print(f"Progress: {i + 1}/{num_tests} tests completed...")
        
        # Make the request
        test_start = time.time()
        try:
            response = requests.get(url, timeout=15)
            test_duration = time.time() - test_start
            
            # Check if response is successful (2xx status codes)
            is_success = 200 <= response.status_code < 300
            
            if is_success:
                # Track successful request
                results.append({
                    'test_num': i + 1,
                    'url': url,
                    'status': 'SUCCESS',
                    'status_code': response.status_code,
                    'response_time': test_duration,
                    'delay_before': delay,
                    'error': None
                })
                response_times.append(test_duration)
            else:
                # Track HTTP error as failure
                results.append({
                    'test_num': i + 1,
                    'url': url,
                    'status': 'FAILURE',
                    'status_code': response.status_code,
                    'response_time': test_duration,
                    'delay_before': delay,
                    'error': f"HTTP {response.status_code}: {response.reason}"
                })
                errors[f"HTTP_{response.status_code}"] += 1
            
            status_codes[response.status_code] += 1
            
        except Exception as e:
            test_duration = time.time() - test_start
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Track failed request
            results.append({
                'test_num': i + 1,
                'url': url,
                'status': 'FAILURE',
                'status_code': None,
                'response_time': test_duration,
                'delay_before': delay,
                'error': f"{error_type}: {error_msg}"
            })
            
            errors[error_type] += 1
    
    # Calculate summary statistics
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    successes = [r for r in results if r['status'] == 'SUCCESS']
    failures = [r for r in results if r['status'] == 'FAILURE']
    success_rate = len(successes) / len(results) * 100
    
    # Print detailed results
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    print(f"Total Tests: {len(results)}")
    print(f"Successes: {len(successes)} ({success_rate:.1f}%)")
    print(f"Failures: {len(failures)} ({100-success_rate:.1f}%)")
    print(f"Total Duration: {total_duration:.2f} seconds")
    print(f"End Time: {end_time.strftime('%H:%M:%S')}")
    
    # Status code breakdown
    if status_codes:
        print(f"\n📈 HTTP Status Codes:")
        for status, count in sorted(status_codes.items()):
            percentage = count / len(results) * 100
            success_indicator = "✅" if 200 <= status < 300 else "❌"
            print(f"  {status}: {count} ({percentage:.1f}%) {success_indicator}")
    
    # Response time statistics
    if response_times:
        print(f"\n⏱️  Response Time Statistics:")
        print(f"  Average: {statistics.mean(response_times):.3f}s")
        print(f"  Median: {statistics.median(response_times):.3f}s")
        print(f"  Min: {min(response_times):.3f}s")
        print(f"  Max: {max(response_times):.3f}s")
        if len(response_times) > 1:
            print(f"  Std Dev: {statistics.stdev(response_times):.3f}s")
    
    # Error breakdown
    if errors:
        print(f"\n❌ Error Breakdown:")
        for error_type, count in errors.most_common():
            percentage = count / len(failures) * 100 if failures else 0
            print(f"  {error_type}: {count} ({percentage:.1f}%)")
        
        print(f"\n🔍 Sample Error Messages:")
        error_samples = defaultdict(list)
        for result in failures:
            if result['error']:
                error_type = result['error'].split(':')[0]
                error_samples[error_type].append(result['error'])
        
        for error_type, msgs in error_samples.items():
            print(f"  {error_type}:")
            # Show first unique error message for each type
            unique_msgs = list(set(msgs))
            for msg in unique_msgs[:2]:  # Show max 2 per type
                print(f"    → {msg}")
    
    # Performance insights
    print(f"\n📋 Test Insights:")
    if success_rate >= 95:
        print("  ✅ Excellent reliability - DNS cache management working well")
    elif success_rate >= 80:
        print("  ⚠️  Good reliability - Minor issues detected")
    elif success_rate >= 50:
        print("  ⚠️  Moderate reliability - Significant issues present")
    else:
        print("  ❌ Poor reliability - Major problems detected")
    
    # Specific proxy error analysis
    if 502 in status_codes:
        proxy_errors = status_codes[502]
        proxy_error_rate = proxy_errors / len(results) * 100
        print(f"  🔥 Proxy errors (502): {proxy_errors} ({proxy_error_rate:.1f}%) - DNS/cache issues likely")
    
    if 404 in status_codes:
        not_found = status_codes[404] 
        print(f"  📍 404 errors: {not_found} - Endpoint availability issues")
    
    if response_times and statistics.mean(response_times) > 5.0:
        print("  ⚠️  High average response times detected")
    
    # Failure pattern analysis
    if failures:
        failure_positions = [f['test_num'] for f in failures]
        if len(failure_positions) > 3:
            # Check if failures cluster at the beginning (cold start issues)
            early_failures = len([pos for pos in failure_positions if pos <= 10])
            if early_failures / len(failure_positions) > 0.5:
                print("  🔍 Many failures in first 10 tests - possible cold start issues")
    
    print(f"\n{'='*60}")
    
    # Exit with appropriate code
    if success_rate < 80:
        print("⚠️  Test completed with significant failures")
        sys.exit(1)
    else:
        print("✅ Test completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()