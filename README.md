# Della Wonders - Store-and-Forward HTTP Proxy

A secure store-and-forward HTTP proxy system for airgapped environments. This system allows scripts on airgapped machines to make controllable network requests via a file-based proxy mechanism.

## Architecture

The system consists of three main components:

1. **`DellaWondersOrchestrator`** - Main orchestrator running on the airgapped machine
2. **`StoreForwardAddon`** - mitmproxy addon that serializes HTTP requests/responses to JSON files
3. **`WonderDellaProcessor`** - Internet-side processor that handles requests with security filtering

## Installation

### Prerequisites

- Python 3.11+
- pip or pixi package manager

### Install from Source

```bash
# Clone the repository
git clone https://github.com/professorwug/della_wonders
cd della_wonders

# Install with pip
pip install -e .

# Or install with pixi (for development)
pixi install
```

### Install from PyPI (when published)

```bash
pip install della-wonders
```

## Usage

After installation, you have access to three main commands:

### 1. Start the Internet-side Processor

On a machine with internet access (with access to the shared filesystem):

```bash
# Start the processor that handles requests
start_wonders

# With custom shared directory
start_wonders --shared-dir /path/to/shared

# Block specific domains
start_wonders --block-domain malicious-site.com --block-domain spam-domain.org

# Enable verbose logging
start_wonders --verbose
```

### 2. Run Scripts on the Airgapped Machine

On the airgapped machine (with access to the same shared filesystem):

```bash
# Run your script through the proxy
wonder_run your_script.py [script_args...]

# Example with the included test script
wonder_run test_script.py

# With custom shared directory
wonder_run --shared-dir /path/to/shared your_script.py

# With custom proxy port and verbose logging
wonder_run --proxy-port 9000 --verbose your_script.py
```

### 3. Check System Status

```bash
# Check the status of the shared filesystem
wonder_status

# With custom shared directory
wonder_status --shared-dir /path/to/shared
```

## How It Works

1. **Request Flow**:
   - Your script makes HTTP requests (using `requests`, `urllib`, etc.)
   - `della_wonders.py` starts a local proxy using mitmproxy
   - All HTTP requests are intercepted and serialized to JSON files in `/shared/requests/`
   - The proxy waits for corresponding response files

2. **Processing Flow**:
   - `wonder_della.py` monitors `/shared/requests/` for new request files
   - Each request is validated against security policies (domain whitelist, content filtering)
   - Approved requests are executed and responses are written to `/shared/responses/`

3. **Response Flow**:
   - The proxy detects the response file and reconstructs the HTTP response
   - Your script receives the response as if it came directly from the internet

## Security Features

- **Domain Blocklisting**: Block access to malicious or unwanted domains
- **Content Filtering**: Request/response content is scanned for sensitive patterns  
- **Size Limits**: Configurable limits on request/response sizes
- **Integrity Checking**: SHA256 hashes ensure response integrity
- **Audit Trail**: All transactions are logged and can be audited

## Configuration

### Environment Variables

- `DELLA_SHARED_DIR`: Directory for request/response exchange (default: `/tmp/shared`)
- `DELLA_PROXY_PORT`: Local proxy port (default: `8888`)

### Security Configuration

Edit the `SecurityFilter` class in `della_wonders/security.py` to customize:
- `blocked_domains`: Blocklist of prohibited domains
- `blocked_patterns`: Regex patterns for content filtering
- `max_request_size` / `max_response_size`: Size limits

## Example Usage

```python
# your_script.py
import requests

# This request will be intercepted and processed through the proxy
response = requests.get("http://httpbin.org/get")
print(response.json())
```

```bash
# Run through the proxy system
pixi run python della_wonders.py your_script.py
```

## File Format

### Request Format (`/shared/requests/{uuid}.json`)
```json
{
  "metadata": {
    "request_id": "uuid-string",
    "timestamp": "2025-01-24T10:30:00Z",
    "source_process": "script_name.py",
    "proxy_version": "1.0.0"
  },
  "request": {
    "method": "GET",
    "url": "https://api.example.com/data",
    "headers": {"User-Agent": "..."},
    "content": "base64-encoded-body",
    "http_version": "HTTP/1.1"
  },
  "security": {
    "content_hash": "sha256-hash",
    "allowed_domains": ["api.example.com"],
    "max_response_size": 10485760
  }
}
```

### Response Format (`/shared/responses/{uuid}.json`)
```json
{
  "metadata": {
    "request_id": "uuid-string", 
    "processed_at": "2025-01-24T10:30:05Z",
    "security_status": "approved"
  },
  "response": {
    "status_code": 200,
    "reason": "OK",
    "headers": {"Content-Type": "application/json"},
    "content": "base64-encoded-response",
    "http_version": "HTTP/1.1"
  },
  "security": {
    "content_filtered": false,
    "response_hash": "sha256-hash",
    "scan_results": {"malware": false, "suspicious_content": false}
  }
}
```

## Testing

Run the included test script to verify the system:

```bash
# Start the processor in one terminal
start_wonders

# In another terminal, run the test
wonder_run test_script.py
```

## Command Reference

### `wonder_run`
Main command for running Python scripts through the proxy on airgapped machines.

**Usage:** `wonder_run script.py [script_args...]`

**Options:**
- `--shared-dir PATH`: Directory for request/response exchange (default: `/tmp/shared`)
- `--proxy-port PORT`: Local proxy port (default: `8888`)
- `--verbose, -v`: Enable verbose logging

### `start_wonders`
Internet-side processor that handles requests with security filtering.

**Usage:** `start_wonders [options]`

**Options:**
- `--shared-dir PATH`: Directory for request/response exchange (default: `/tmp/shared`)
- `--block-domain DOMAIN`: Add domains to blocklist (can be used multiple times)
- `--verbose, -v`: Enable verbose logging

### `wonder_status`
Check the status of the della_wonders system.

**Usage:** `wonder_status [options]`

**Options:**
- `--shared-dir PATH`: Directory for request/response exchange (default: `/tmp/shared`)

## Limitations

- Only HTTP/HTTPS protocols are supported
- Requires a shared filesystem between airgapped and internet-connected machines
- Response times depend on file system polling intervals
- WebSocket connections are not supported (HTTP requests only)

## Security Considerations

- Ensure shared filesystem has appropriate access controls
- Review and customize the domain whitelist for your use case
- Monitor logs for security events
- Consider additional content filtering rules for sensitive environments