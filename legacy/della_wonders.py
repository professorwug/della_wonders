#!/usr/bin/env python3
"""
Main orchestrator that runs target scripts with store-and-forward proxy
Usage: python della_wonders.py target_script.py --script-args
"""

import sys
import subprocess
import signal
import os
import threading
import time
from pathlib import Path
import logging

class DellaWonders:
    def __init__(self, shared_dir="/tmp/shared", proxy_port=8888):
        self.shared_dir = Path(shared_dir)
        self.proxy_port = proxy_port
        self.proxy_process = None
        self.target_process = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_directories(self):
        """Create shared directories with proper permissions"""
        for subdir in ["requests", "responses", "logs"]:
            subdir_path = self.shared_dir / subdir
            subdir_path.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created directory: {subdir_path}")
            
    def start_proxy(self):
        """Start mitmproxy with our addon"""
        proxy_script = Path(__file__).parent / "proxy.py"
        if not proxy_script.exists():
            raise FileNotFoundError(f"Proxy script not found: {proxy_script}")
            
        cmd = [
            "mitmdump", 
            "-s", str(proxy_script),
            "-p", str(self.proxy_port),
            "--set", f"shared_dir={self.shared_dir}",
            "--set", "confdir=~/.mitmproxy"
        ]
        
        self.logger.info(f"Starting mitmproxy: {' '.join(cmd)}")
        self.proxy_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for proxy to start
        time.sleep(3)
        
        # Check if proxy started successfully
        if self.proxy_process.poll() is not None:
            stdout, stderr = self.proxy_process.communicate()
            self.logger.error(f"Proxy failed to start. STDOUT: {stdout.decode()}")
            self.logger.error(f"STDERR: {stderr.decode()}")
            raise RuntimeError("Failed to start mitmproxy")
            
        self.logger.info(f"Proxy started on port {self.proxy_port}")
        
    def run_target_script(self, script_path, script_args):
        """Run target script with proxy environment"""
        if not Path(script_path).exists():
            raise FileNotFoundError(f"Target script not found: {script_path}")
            
        env = os.environ.copy()
        env.update({
            "HTTP_PROXY": f"http://127.0.0.1:{self.proxy_port}",
            "HTTPS_PROXY": f"http://127.0.0.1:{self.proxy_port}",
            "REQUESTS_CA_BUNDLE": "",  # Disable SSL verification for proxy
            "CURL_CA_BUNDLE": "",
        })
        
        cmd = ["python", script_path] + script_args
        self.logger.info(f"Running target script: {' '.join(cmd)}")
        
        self.target_process = subprocess.Popen(cmd, env=env)
        return self.target_process.wait()
        
    def cleanup(self):
        """Clean shutdown of all processes"""
        self.logger.info("Cleaning up processes...")
        
        if self.target_process and self.target_process.poll() is None:
            self.logger.info("Terminating target process")
            self.target_process.terminate()
            try:
                self.target_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.target_process.kill()
                
        if self.proxy_process and self.proxy_process.poll() is None:
            self.logger.info("Terminating proxy process")
            self.proxy_process.terminate()
            try:
                self.proxy_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proxy_process.kill()

def main():
    if len(sys.argv) < 2:
        print("Usage: python della_wonders.py target_script.py [script_args...]")
        print("Example: python della_wonders.py test_script.py --verbose")
        sys.exit(1)
        
    script_path = sys.argv[1]
    script_args = sys.argv[2:]
    
    # Allow custom shared directory via environment variable
    shared_dir = os.environ.get("DELLA_SHARED_DIR", "/tmp/shared")
    proxy_port = int(os.environ.get("DELLA_PROXY_PORT", "8888"))
    
    orchestrator = DellaWonders(shared_dir=shared_dir, proxy_port=proxy_port)
    
    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        orchestrator.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        orchestrator.setup_directories()
        orchestrator.start_proxy()
        exit_code = orchestrator.run_target_script(script_path, script_args)
        sys.exit(exit_code)
    except Exception as e:
        orchestrator.logger.error(f"Error: {e}")
        sys.exit(1)
    finally:
        orchestrator.cleanup()

if __name__ == "__main__":
    main()