"""
Command-line interface entry points for della_wonders
"""

import sys
import os
import argparse
from pathlib import Path

from .orchestrator import DellaWondersOrchestrator
from .processor import WonderDellaProcessor


def wonder_run():
    """Entry point for 'wonder_run' command"""
    parser = argparse.ArgumentParser(
        description="Run a Python script through the della_wonders store-and-forward proxy",
        prog="wonder_run"
    )
    parser.add_argument(
        "script", 
        help="Python script to run through the proxy"
    )
    parser.add_argument(
        "args", 
        nargs="*", 
        help="Arguments to pass to the target script"
    )
    parser.add_argument(
        "--shared-dir", 
        default=os.environ.get("DELLA_SHARED_DIR", "/tmp/shared"),
        help="Directory for request/response exchange (default: /tmp/shared)"
    )
    parser.add_argument(
        "--proxy-port", 
        type=int,
        default=int(os.environ.get("DELLA_PROXY_PORT", "9025")),
        help="Local proxy port (default: 9025)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Set logging level if verbose
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate script exists
    script_path = Path(args.script)
    if not script_path.exists():
        print(f"Error: Script not found: {args.script}", file=sys.stderr)
        sys.exit(1)
    
    # Create orchestrator and run
    orchestrator = DellaWondersOrchestrator(
        shared_dir=args.shared_dir,
        proxy_port=args.proxy_port
    )
    
    try:
        exit_code = orchestrator.run(args.script, args.args)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def start_wonders():
    """Entry point for 'start_wonders' command (internet-side processor)"""
    parser = argparse.ArgumentParser(
        description="Run the internet-side processor for della_wonders proxy",
        prog="start_wonders"
    )
    parser.add_argument(
        "--shared-dir", 
        default=os.environ.get("DELLA_SHARED_DIR", "/tmp/shared"),
        help="Directory for request/response exchange (default: /tmp/shared)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--block-domain",
        action="append",
        dest="blocked_domains",
        help="Add domains to blocklist (can be used multiple times)"
    )
    parser.add_argument(
        "--add-domain",
        action="append",
        dest="allowed_domains",
        help="[DEPRECATED] This option no longer has effect - use --block-domain to block specific domains"
    )
    
    args = parser.parse_args()
    
    # Set logging level if verbose
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create processor
    processor = WonderDellaProcessor(shared_dir=args.shared_dir)
    
    # Add any blocked domains
    if args.blocked_domains:
        for domain in args.blocked_domains:
            processor.add_blocked_domain(domain)
    
    # Handle deprecated allowed domains option
    if args.allowed_domains:
        print("Warning: --add-domain is deprecated and has no effect. Use --block-domain to block specific domains.", file=sys.stderr)
    
    try:
        processor.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def wonder_status():
    """Entry point for 'wonder_status' command"""
    parser = argparse.ArgumentParser(
        description="Check status of della_wonders system",
        prog="wonder_status"
    )
    parser.add_argument(
        "--shared-dir", 
        default=os.environ.get("DELLA_SHARED_DIR", "/tmp/shared"),
        help="Directory for request/response exchange (default: /tmp/shared)"
    )
    
    args = parser.parse_args()
    
    shared_dir = Path(args.shared_dir)
    request_dir = shared_dir / "requests"
    response_dir = shared_dir / "responses"
    
    print(f"Della Wonders Status")
    print(f"===================")
    print(f"Shared directory: {shared_dir}")
    print(f"Exists: {shared_dir.exists()}")
    
    if shared_dir.exists():
        print(f"Request directory: {request_dir}")
        print(f"  Exists: {request_dir.exists()}")
        if request_dir.exists():
            pending_requests = len(list(request_dir.glob("*.json")))
            print(f"  Pending requests: {pending_requests}")
            
        print(f"Response directory: {response_dir}")
        print(f"  Exists: {response_dir.exists()}")
        if response_dir.exists():
            responses = len(list(response_dir.glob("*.json")))
            print(f"  Responses: {responses}")
    else:
        print("Shared directory does not exist. Run wonder_run or wonder_process to create it.")


def main():
    """Legacy entry point for backwards compatibility"""
    print("Warning: Using deprecated entry point. Use 'wonder_run' instead.", file=sys.stderr)
    wonder_run()