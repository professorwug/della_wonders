# Della Wonders

Princeton's DELLA cluster wisely airgaps its GPU cluster, which protects against abuse by crypto miners or lavish self-hosted chatbots -- but makes it hard to perform training runs that rely on external resources (e.g. LLM-as-a-Judge calls, or agentic open search).

`della_wonders` is a utility which allows scripts on DELLA's GPUs to make limited, controllable network requests to the outside world. This is accomplished by a "store-and-forward" proxy which uses Della's shared filesystem to convey HTTP requests from an air-gapped GPU node to a helper process on an internet-enabled node. 

Rather marvelously, because this is realized as an HTTP *proxy*, you need make no modifications to your training scripts: just use our helper script `wonder_run`, to start them, and their network requests will be seamlessly handled.

To use `della_wonders`, there are two steps:

1. Log into an internet-enabled Della node, clone this repo, and start the helper process by running 

	```
	bash slurm_wonders.sh
	```

	This will submit a slurm job to run the helper process for 24 hrs, by default. 
2. Meanwhile, in the repo where you intend to launch your training run, install the package with `conda install -c wug della_wonders`. **Wait until the job from (1) has started**, then launch your training run with some slurm script that include 
	```
	wonder_run your_python_file.py
	```
	`wonder_run` launches your Python script with a subprocess, but with network traffic proxied to the helper.

If your script fails to run, you may have to insert a few lines of code to loosen the network security of common packages like `requests`. See "Required Modifications", below.

## Architecture

The system consists of three main components:

1. **`DellaWondersOrchestrator`** - Main orchestrator running on the airgapped machine
2. **`StoreForwardAddon`** - mitmproxy addon that serializes HTTP requests/responses to JSON files
3. **`WonderDellaProcessor`** - Internet-side processor that handles requests with security filtering

## Installation

### Prerequisites

- Python 3.11+
- conda or pixi package manager

### Install from Conda (Recommended)

```bash
# Install from anaconda.org
conda install -c wug della-wonders

# Or with pixi
pixi project channel add wug  # Add the wug channel to your project
pixi add della-wonders
```

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

### Build and Install as Conda Package

```bash
# Clone the repository
git clone https://github.com/professorwug/della_wonders
cd della_wonders

# Build the conda package using pixi
pixi build

# This creates a conda package file: della-wonders-1.0.0-[hash].conda
# Install the built package in your conda environment:
conda install ./della-wonders-*.conda

# Or install in a pixi environment:
pixi add ./della-wonders-*.conda
```

**Note:** Built conda packages (`*.conda` files) are excluded from git to keep the repository clean. Users should build packages locally as needed.

## Usage

After installation, you have access to four main commands:

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

- `DELLA_SHARED_DIR`: Directory for request/response exchange (default: `/scratch/gpfs/$USER/.wonders`)
- `DELLA_PROXY_PORT`: Local proxy port (default: `9025`)

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

## Using Third-Party Libraries with Requests

Most third-party Python libraries that make HTTP requests use the `requests` library internally. To ensure these libraries work properly through the della_wonders proxy system, they need to be configured to:

1. **Respect proxy environment variables**
2. **Disable SSL certificate verification** (since mitmproxy generates its own certificates)
3. **Use a properly configured requests session**

### Required Modifications

When using libraries that make HTTP requests (like API clients), you'll need to modify them to use a proxy-compatible session:

```python
import requests
import os

# Create a session that works with della_wonders proxy
session = requests.Session()
session.verify = False  # Disable SSL verification for proxy compatibility
session.trust_env = True  # Use proxy settings from environment variables

# Set proxies explicitly from environment if available
http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
if http_proxy or https_proxy:
    session.proxies.update({
        'http': http_proxy,
        'https': https_proxy
    })

# Use the session for all requests
response = session.get("https://api.example.com/data")
```

### Example: Modifying a Third-Party API Client

If you have a third-party API client class like this:

```python
class APIClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.example.com"
    
    def make_request(self, endpoint):
        # Original code that won't work with proxy:
        response = requests.get(f"{self.base_url}{endpoint}", 
                              headers={"Authorization": f"Bearer {self.api_key}"})
        return response.json()
```

Modify it to use a proxy-compatible session:

```python
class APIClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.example.com"
        
        # Create proxy-compatible session
        self.session = requests.Session()
        self.session.verify = False
        self.session.trust_env = True
        
        # Set proxies explicitly
        http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        if http_proxy or https_proxy:
            self.session.proxies.update({
                'http': http_proxy,
                'https': https_proxy
            })
    
    def make_request(self, endpoint):
        # Modified code that works with proxy:
        response = self.session.get(f"{self.base_url}{endpoint}", 
                                  headers={"Authorization": f"Bearer {self.api_key}"})
        return response.json()
```

### Common SSL Issues

If you see errors like:
- `[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed`
- `HTTPSConnectionPool(host='...', port=443): Max retries exceeded`
- `unable to get local issuer certificate`

These indicate that SSL verification needs to be disabled for the proxy to work. The modifications above will resolve these issues.

### Environment Variables Set by della_wonders

When you run `wonder_run`, the following environment variables are automatically set for your script:

- `HTTP_PROXY=http://127.0.0.1:9025`
- `HTTPS_PROXY=http://127.0.0.1:9025`
- `REQUESTS_CA_BUNDLE=""` (disabled)
- `PYTHONHTTPSVERIFY=0` (disabled)
- `SSL_VERIFY=False` (disabled)

However, some libraries ignore these environment variables, which is why explicit session configuration is necessary.

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

## Development

### Building Packages

The project includes configuration for building conda packages:

```bash
# Build conda package
pixi build

# Run development tasks
pixi run test-commands  # Test all CLI commands
pixi run test-install   # Test pip installation
```

### Publishing to Anaconda.org

To publish the conda package to anaconda.org:

1. **Get an API token** from https://anaconda.org/settings/access
2. **Set the token** as an environment variable:
   ```bash
   export ANACONDA_API_TOKEN=your_token_here
   ```
3. **Upload the package**:
   ```bash
   pixi run upload-conda
   # or
   ./upload_conda.sh
   ```

The package will be available at: https://anaconda.org/wug/della-wonders

### Project Structure

- `della_wonders/` - Main package source code
- `pixi.toml` - Pixi build configuration for conda packages
- `pyproject.toml` - Python package configuration
- `recipe.yaml` - Conda recipe specification
- `slurm/` - SLURM job scripts and configuration

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

### `wonder_bread`
Display ASCII art of a loaf of bread for your viewing pleasure.

**Usage:** `wonder_bread`

A delightful command that brings a smile to your day while working with proxy systems!

## HPC/SLURM Integration

For long-running deployments on HPC clusters, della_wonders includes SLURM job scripts:

```bash
# Quick start - submit with default 24-hour limit
./slurm/submit_wonders.sh

# Custom configuration
cp slurm/config.env my_config.env
# Edit my_config.env with your cluster settings
./slurm/submit_wonders.sh my_config.env

# Monitor the job
squeue -u $USER
tail -f logs/start_wonders_<job_id>.out
```

The SLURM integration provides:
- **Configurable time limits** (2 hours to 7+ days)
- **Resource management** (CPU, memory, partition selection)
- **Email notifications** for job status
- **Graceful shutdown handling**
- **Real-time logging** with timestamps
- **Example configurations** for different scenarios

See `slurm/README.md` for complete documentation and Princeton Research Computing specific guidance.

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