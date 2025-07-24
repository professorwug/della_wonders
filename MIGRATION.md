# Migration Guide

## From Legacy Scripts to Installable Package

If you were previously using the standalone scripts, here's how to migrate to the new installable package:

### Old Usage (Deprecated)
```bash
# Old way - using standalone scripts
python della_wonders.py your_script.py --args
python wonder_della.py
```

### New Usage (Current)
```bash
# Install the package first
pip install -e .  # or from PyPI when available

# New way - using installed commands
wonder_run your_script.py --args
start_wonders
```

## Command Mapping

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `python della_wonders.py script.py` | `wonder_run script.py` | Main orchestrator command |
| `python wonder_della.py` | `start_wonders` | Internet-side processor |
| N/A | `wonder_status` | New: Check system status |

## Environment Variables

Environment variables work the same way:

```bash
# Both old and new support these variables
export DELLA_SHARED_DIR=/scratch/gpfs/$USER/.wonders
export DELLA_PROXY_PORT=9025

# Old
python della_wonders.py script.py

# New  
wonder_run script.py
```

## Configuration

The new version includes additional command-line options:

```bash
# Block specific domains
start_wonders --block-domain malicious-site.com --block-domain spam-domain.org

# Verbose logging
wonder_run --verbose your_script.py
start_wonders --verbose

# Custom proxy port
wonder_run --proxy-port 9000 your_script.py
```

## Programmatic Usage

You can still use the classes directly in your Python code:

```python
# Old way still works
from della_wonders import DellaWondersOrchestrator, WonderDellaProcessor

orchestrator = DellaWondersOrchestrator(shared_dir="/tmp/shared")
processor = WonderDellaProcessor(shared_dir="/tmp/shared")
```

## Benefits of the New Package

1. **Cleaner interface**: Simple commands instead of long Python invocations
2. **Better help**: Built-in `--help` for all commands
3. **Enhanced options**: More configuration options available
4. **Status checking**: New `wonder_status` command to check system state
5. **Easier deployment**: Install once, use anywhere
6. **Better error handling**: Improved error messages and logging