# SLURM Integration for della_wonders

This directory contains SLURM job scripts and configuration files for running `start_wonders` as a long-running batch job on HPC clusters, specifically designed for Princeton Research Computing systems.

## Quick Start

1. **Basic submission** (uses default 24-hour limit):
   ```bash
   ./slurm/submit_wonders.sh
   ```

2. **Custom configuration**:
   ```bash
   cp slurm/config.env my_config.env
   # Edit my_config.env with your settings
   ./slurm/submit_wonders.sh my_config.env
   ```

3. **Monitor the job**:
   ```bash
   squeue -u $USER
   tail -f logs/start_wonders_<job_id>.out
   ```

## Files Overview

### Core Files
- **`submit_wonders.sh`** - Main submission script with configuration support
- **`config.env`** - Default configuration template
- **`start_wonders.slurm`** - Basic SLURM script template

### Example Configurations
- **`examples/short_test.env`** - 2-hour test job configuration
- **`examples/long_production.env`** - 7-day production job configuration

## Configuration Options

### SLURM Settings
```bash
JOB_NAME="della-wonders"        # Job name shown in queue
TIME_LIMIT="24:00:00"           # Time limit (HH:MM:SS or D-HH:MM:SS)
MEMORY="2G"                     # Memory per node
CPUS_PER_TASK="1"              # Number of CPU cores
PARTITION="cpu"                 # Partition to submit to
```

### Email Notifications (Optional)
```bash
EMAIL_NOTIFICATIONS="BEGIN,END,FAIL"
EMAIL_ADDRESS="your.email@princeton.edu"
```

### Account/QOS Settings (Optional)
```bash
ACCOUNT_NAME="your_account"     # SLURM account
QOS_NAME="your_qos"            # Quality of Service
```

### della_wonders Settings
```bash
DELLA_SHARED_DIR="/scratch/gpfs/$USER/.wonders"  # Directory for request/response exchange
DELLA_PROXY_PORT="9025"         # Proxy port
BLOCKED_DOMAINS="bad1.com bad2.com"  # Space-separated blocked domains
```

## Usage Examples

### Test Job (2 hours)
```bash
./slurm/submit_wonders.sh slurm/examples/short_test.env
```

### Production Job (7 days)
```bash
# Edit email address in the config first
cp slurm/examples/long_production.env my_prod.env
vim my_prod.env  # Set your email address
./slurm/submit_wonders.sh my_prod.env
```

### Custom Shared Directory
Create a config with job-specific isolation:
```bash
cat > my_isolated.env << EOF
JOB_NAME="della-wonders-isolated"
TIME_LIMIT="12:00:00"
DELLA_SHARED_DIR="/scratch/gpfs/\$USER/.wonders_\${SLURM_JOB_ID}"
EOF

./slurm/submit_wonders.sh my_isolated.env
```

## Monitoring Jobs

### Check job status
```bash
squeue -u $USER                    # All your jobs
squeue -j <job_id>                 # Specific job
sacct -j <job_id>                  # Job accounting info
```

### View job output
```bash
# Real-time output
tail -f logs/start_wonders_<job_id>.out

# Error log
tail -f logs/start_wonders_<job_id>.err

# Full logs
cat logs/start_wonders_<job_id>.out
```

### Cancel job
```bash
scancel <job_id>
```

## Job Features

### Graceful Shutdown
- Jobs handle SIGINT and SIGTERM signals gracefully
- Cleans up child processes on shutdown
- Logs cleanup actions

### Real-time Logging
- Timestamps added to all log output
- Unbuffered output for real-time monitoring
- Separate stdout and stderr logs

### Error Handling
- Checks for pixi availability
- Validates environment setup
- Exits cleanly on errors

### Resource Management
- Minimal resource requirements (1 CPU, 2GB RAM by default)
- Configurable based on workload
- Efficient for long-running proxy processes

## Princeton-Specific Notes

### Partitions
Common partitions on Princeton clusters:
- `cpu` - General CPU jobs
- `gpu` - GPU jobs (not needed for della_wonders)
- `datascience` - Data science partition

### Time Limits
- Default: 24 hours
- Maximum varies by partition (check with `sinfo`)
- Use `D-HH:MM:SS` format for multi-day jobs

### Storage
Recommended shared directory locations:
- `/scratch/gpfs/$USER/.wonders` - Default user scratch space (recommended)
- `/scratch/gpfs/$USER/.wonders_custom` - Custom user scratch space
- `/projects/$PROJECT/.wonders` - Project storage (if you have project space)

### Modules
If needed, add to your config or modify the script:
```bash
module load anaconda3/2023.9
module load python/3.11
```

## Troubleshooting

### Job Won't Start
- Check partition availability: `sinfo`
- Verify account/QOS: `sacctmgr show user $USER`
- Check resource limits: `sshare -u $USER`

### Job Fails Immediately
- Check error log: `cat logs/start_wonders_<job_id>.err`
- Verify pixi installation and PATH
- Check shared directory permissions

### Can't Connect to Proxy
- Verify shared directory path is accessible from compute nodes
- Check firewall rules for proxy port
- Ensure `start_wonders` is actually running

### Long Jobs Get Killed
- Increase time limit in configuration
- Check cluster policies for maximum job duration
- Consider using job arrays for very long runs

## Advanced Usage

### Job Arrays
For multiple parallel instances:
```bash
#SBATCH --array=1-5              # Run 5 instances
export DELLA_SHARED_DIR="/tmp/shared_${SLURM_ARRAY_TASK_ID}"
export DELLA_PROXY_PORT="$((9025 + SLURM_ARRAY_TASK_ID))"
```

### Dependency Chains
Submit jobs that depend on others:
```bash
JOB1=$(sbatch --parsable my_script.slurm)
JOB2=$(sbatch --dependency=afterok:$JOB1 next_script.slurm)
```

### Resource Scaling
For high-throughput scenarios:
```bash
MEMORY="8G"                      # More memory
CPUS_PER_TASK="4"               # More CPUs
PARTITION="datascience"          # Specialized partition
```