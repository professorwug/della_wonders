#!/bin/bash
# Helper script to submit della_wonders SLURM job with custom configuration

set -e

# Default configuration file
CONFIG_FILE="${1:-slurm/config.env}"

# Check if configuration file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Error: Configuration file '$CONFIG_FILE' not found."
    echo "Usage: $0 [config_file]"
    echo "       $0                    # Uses slurm/config.env"
    echo "       $0 my_custom.env      # Uses custom config file"
    exit 1
fi

echo "Using configuration file: $CONFIG_FILE"

# Load configuration
source "$CONFIG_FILE"

# Set defaults if not specified
JOB_NAME="${JOB_NAME:-della-wonders}"
TIME_LIMIT="${TIME_LIMIT:-24:00:00}"
MEMORY="${MEMORY:-2G}"
CPUS_PER_TASK="${CPUS_PER_TASK:-1}"
PARTITION="${PARTITION:-cpu}"
DELLA_SHARED_DIR="${DELLA_SHARED_DIR:-/scratch/gpfs/\$USER/.wonders}"
DELLA_PROXY_PORT="${DELLA_PROXY_PORT:-9025}"

# Create logs directory
mkdir -p logs

# Create temporary SLURM script
TEMP_SCRIPT="logs/temp_start_wonders_$(date +%Y%m%d_%H%M%S).slurm"

echo "Generating SLURM script: $TEMP_SCRIPT"

# Generate SLURM script with configuration
cat > "$TEMP_SCRIPT" << EOF
#!/bin/bash
#SBATCH --job-name=$JOB_NAME
#SBATCH --output=logs/start_wonders_%j.out
#SBATCH --error=logs/start_wonders_%j.err
#SBATCH --time=$TIME_LIMIT
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=$CPUS_PER_TASK
#SBATCH --mem=$MEMORY
#SBATCH --partition=$PARTITION
EOF

# Add optional email settings
if [[ -n "$EMAIL_NOTIFICATIONS" && -n "$EMAIL_ADDRESS" ]]; then
    echo "#SBATCH --mail-type=$EMAIL_NOTIFICATIONS" >> "$TEMP_SCRIPT"
    echo "#SBATCH --mail-user=$EMAIL_ADDRESS" >> "$TEMP_SCRIPT"
fi

# Add optional account/QOS settings
if [[ -n "$ACCOUNT_NAME" ]]; then
    echo "#SBATCH --account=$ACCOUNT_NAME" >> "$TEMP_SCRIPT"
fi

if [[ -n "$QOS_NAME" ]]; then
    echo "#SBATCH --qos=$QOS_NAME" >> "$TEMP_SCRIPT"
fi

# Add the main script content
cat >> "$TEMP_SCRIPT" << 'EOF'

# Print job information
echo "=================================================================="
echo "SLURM Job Information"
echo "=================================================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Node: $SLURMD_NODENAME"
echo "Start Time: $(date)"
echo "Working Directory: $(pwd)"
echo "=================================================================="

# Environment setup
echo "Setting up environment..."

# Set environment variables for della_wonders
EOF

echo "export DELLA_SHARED_DIR=\"$DELLA_SHARED_DIR\"" >> "$TEMP_SCRIPT"
echo "export DELLA_PROXY_PORT=\"$DELLA_PROXY_PORT\"" >> "$TEMP_SCRIPT"

cat >> "$TEMP_SCRIPT" << 'EOF'

echo "Della Wonders Configuration:"
echo "  DELLA_SHARED_DIR: $DELLA_SHARED_DIR"
echo "  DELLA_PROXY_PORT: $DELLA_PROXY_PORT"
echo "=================================================================="

# Create logs directory if it doesn't exist
mkdir -p logs

# Create shared directory if it doesn't exist
mkdir -p "$DELLA_SHARED_DIR"

# Navigate to the project directory
PROJECT_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"
cd "$PROJECT_DIR"

echo "Project Directory: $(pwd)"
echo "=================================================================="

# Check if pixi is available
if ! command -v pixi &> /dev/null; then
    echo "ERROR: pixi command not found. Please ensure pixi is installed and in PATH."
    echo "Installation instructions: https://pixi.sh/latest/#installation"
    exit 1
fi

# Verify pixi environment
echo "Verifying pixi environment..."
pixi info

echo "=================================================================="
echo "Starting della_wonders processor..."
echo "=================================================================="

# Set up signal handling for graceful shutdown
cleanup() {
    echo ""
    echo "=================================================================="
    echo "Received shutdown signal. Cleaning up..."
    echo "=================================================================="
    
    # Kill any child processes
    jobs -p | xargs -r kill
    
    echo "Cleanup completed at: $(date)"
    exit 0
}

# Trap signals for graceful shutdown
trap cleanup SIGINT SIGTERM

# Build start_wonders command with options
CMD="pixi run start_wonders --shared-dir \$DELLA_SHARED_DIR --verbose"
EOF

# Add blocked domains if specified
if [[ -n "$BLOCKED_DOMAINS" ]]; then
    for domain in $BLOCKED_DOMAINS; do
        echo "CMD=\"\$CMD --block-domain $domain\"" >> "$TEMP_SCRIPT"
    done
fi

cat >> "$TEMP_SCRIPT" << 'EOF'

echo "Running: $CMD"
echo "Press Ctrl+C to stop gracefully"
echo ""

# Run the command with output buffering disabled for real-time logs
stdbuf -oL -eL $CMD 2>&1 | while IFS= read -r line; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"
done

# This should not be reached unless start_wonders exits normally
echo "=================================================================="
echo "start_wonders exited normally at: $(date)"
echo "=================================================================="
EOF

# Make the temporary script executable
chmod +x "$TEMP_SCRIPT"

# Display configuration summary
echo ""
echo "=================================================================="
echo "SLURM Job Configuration Summary"
echo "=================================================================="
echo "Job Name: $JOB_NAME"
echo "Time Limit: $TIME_LIMIT"
echo "Memory: $MEMORY"
echo "CPUs per Task: $CPUS_PER_TASK"
echo "Partition: $PARTITION"
echo "Shared Directory: $DELLA_SHARED_DIR"
echo "Proxy Port: $DELLA_PROXY_PORT"

if [[ -n "$BLOCKED_DOMAINS" ]]; then
    echo "Blocked Domains: $BLOCKED_DOMAINS"
fi

if [[ -n "$EMAIL_ADDRESS" ]]; then
    echo "Email Notifications: $EMAIL_NOTIFICATIONS -> $EMAIL_ADDRESS"
fi

if [[ -n "$ACCOUNT_NAME" ]]; then
    echo "Account: $ACCOUNT_NAME"
fi

if [[ -n "$QOS_NAME" ]]; then
    echo "QOS: $QOS_NAME"
fi

echo "=================================================================="

# Submit the job
echo "Submitting SLURM job..."
JOB_ID=$(sbatch "$TEMP_SCRIPT")

if [[ $? -eq 0 ]]; then
    echo "✅ Job submitted successfully!"
    echo "Job ID: $JOB_ID"
    echo ""
    echo "Monitor job status with:"
    echo "  squeue -u \$USER"
    echo "  squeue -j $(echo $JOB_ID | grep -o '[0-9]*')"
    echo ""
    echo "View job output with:"
    echo "  tail -f logs/start_wonders_$(echo $JOB_ID | grep -o '[0-9]*').out"
    echo ""
    echo "Cancel job with:"
    echo "  scancel $(echo $JOB_ID | grep -o '[0-9]*')"
else
    echo "❌ Job submission failed!"
    exit 1
fi

# Clean up temporary script after successful submission
rm "$TEMP_SCRIPT"