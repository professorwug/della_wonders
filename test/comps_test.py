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
import os
from pathlib import Path
from datetime import datetime


def analyze_processor_logs(shared_dir: str, test_start_time: datetime, test_end_time: datetime):
    """Analyze processor logs to count requests processed during test"""
    logs_dir = Path(shared_dir) / "logs"
    processor_log = logs_dir / "processor.log"
    
    if not processor_log.exists():
        return {
            'log_found': False,
            'requests_detected': 0,
            'requests_started': 0,
            'requests_succeeded': 0,
            'requests_failed': 0,
            'requests_skipped': 0,
            'error': 'No processor log found'
        }
    
    # Parse log entries within test timeframe
    requests_detected = 0
    requests_started = 0
    requests_succeeded = 0
    requests_failed = 0
    requests_skipped = 0
    
    try:
        with processor_log.open('r') as f:
            for line in f:
                if not line.strip():
                    continue
                    
                # Parse timestamp from log line (format: 2025-01-XX HH:MM:SS,mmm)
                try:
                    timestamp_str = line.split(' - ')[0]
                    log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                    
                    # Only count logs within test timeframe
                    if test_start_time <= log_time <= test_end_time:
                        if 'SCAN: Found' in line and 'request files' in line:
                            # Extract number of files found
                            parts = line.split('Found ')
                            if len(parts) > 1:
                                num_str = parts[1].split(' ')[0]
                                requests_detected += int(num_str)
                        elif 'REQUEST_START:' in line:
                            requests_started += 1
                        elif 'REQUEST_SUCCESS:' in line:
                            requests_succeeded += 1
                        elif 'REQUEST_FAILED:' in line:
                            requests_failed += 1
                        elif 'REQUEST_SKIP:' in line:
                            requests_skipped += 1
                            
                except (ValueError, IndexError):
                    # Skip malformed log lines
                    continue
                    
    except Exception as e:
        return {
            'log_found': True,
            'requests_detected': 0,
            'requests_started': 0,
            'requests_succeeded': 0,
            'requests_failed': 0,
            'requests_skipped': 0,
            'error': f'Error reading log: {e}'
        }
    
    return {
        'log_found': True,
        'requests_detected': requests_detected,
        'requests_started': requests_started,
        'requests_succeeded': requests_succeeded,
        'requests_failed': requests_failed,
        'requests_skipped': requests_skipped,
        'error': None
    }


def main():
    """Run comprehensive DNS resolution tests"""
    print("🧪 Comprehensive della_wonders DNS Resolution Test")
    print("=" * 60)
    
    # Test configuration
    num_tests = 60  # Many dozen tests
    base_url = "http://httpbun.org"
    endpoints = ["/get", "/headers", "/ip", "/status/200", "/delay/1"]
    
    # Get shared directory (same logic as processor)
    shared_dir = os.environ.get('DELLA_SHARED_DIR')
    if not shared_dir:
        user = os.environ.get('USER', 'unknown')
        if os.path.exists("/scratch/gpfs") and os.access("/scratch/gpfs", os.W_OK):
            shared_dir = f"/scratch/gpfs/{user}/.wonders"
        else:
            shared_dir = f"/tmp/shared_{user}"
    
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
    
    # Analyze processor logs
    print("\n🔍 Analyzing processor logs...")
    processor_stats = analyze_processor_logs(shared_dir, start_time, end_time)
    
    # Print detailed results
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    print(f"Total Tests: {len(results)}")
    print(f"Successes: {len(successes)} ({success_rate:.1f}%)")
    print(f"Failures: {len(failures)} ({100-success_rate:.1f}%)")
    print(f"Total Duration: {total_duration:.2f} seconds")
    print(f"End Time: {end_time.strftime('%H:%M:%S')}")
    print(f"Shared Directory: {shared_dir}")
    
    # Processor statistics
    if processor_stats['log_found']:
        print(f"\n🔧 PROCESSOR STATISTICS:")
        print(f"Requests Detected: {processor_stats['requests_detected']}")
        print(f"Requests Started: {processor_stats['requests_started']}")
        print(f"Requests Succeeded: {processor_stats['requests_succeeded']}")
        print(f"Requests Failed: {processor_stats['requests_failed']}")
        print(f"Requests Skipped: {processor_stats['requests_skipped']}")
        
        # Calculate processor success rate
        total_processed = processor_stats['requests_started']
        if total_processed > 0:
            processor_success_rate = processor_stats['requests_succeeded'] / total_processed * 100
            print(f"Processor Success Rate: {processor_success_rate:.1f}%")
            
            # Compare proxy vs processor
            detection_rate = processor_stats['requests_detected'] / len(results) * 100
            processing_rate = processor_stats['requests_started'] / len(results) * 100
            print(f"Detection Rate: {detection_rate:.1f}% ({processor_stats['requests_detected']}/{len(results)})")
            print(f"Processing Rate: {processing_rate:.1f}% ({processor_stats['requests_started']}/{len(results)})")
    else:
        print(f"\n⚠️  PROCESSOR LOG ANALYSIS FAILED:")
        print(f"Error: {processor_stats['error']}")
    
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
    
    # Processor vs Proxy diagnostic insights
    if processor_stats['log_found'] and processor_stats['requests_started'] > 0:
        detection_rate = processor_stats['requests_detected'] / len(results) * 100
        processing_rate = processor_stats['requests_started'] / len(results) * 100
        
        if detection_rate < 50:
            print(f"  🚨 Low detection rate ({detection_rate:.1f}%) - Processor missing many requests")
        elif processing_rate < detection_rate * 0.8:
            print(f"  ⚠️  Detection vs processing gap - Some requests not being processed")
        
        # Compare success rates
        processor_success_rate = processor_stats['requests_succeeded'] / processor_stats['requests_started'] * 100
        if processor_success_rate > success_rate + 20:
            print(f"  🔍 Processor succeeding ({processor_success_rate:.1f}%) but proxy failing ({success_rate:.1f}%) - Response delivery issue")
        elif processor_success_rate < 50:
            print(f"  💥 Processor itself failing ({processor_success_rate:.1f}%) - HTTP request issues")
    
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