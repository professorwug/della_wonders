#!/bin/bash
#SBATCH --job-name=della-wonders          # Job name
#SBATCH --output=logs/start_wonders_%j.out # Standard output log (%j = job ID)
#SBATCH --error=logs/start_wonders_%j.err  # Standard error log (%j = job ID)
#SBATCH --time=24:00:00                    # Time limit (24 hours - adjust as needed)
#SBATCH --ntasks=1                         # Number of tasks (1 for single process)
#SBATCH --cpus-per-task=1                  # Number of CPU cores per task
#SBATCH --mem=2G                           # Memory per node (2GB should be sufficient)
#SBATCH --partition=cpu                    # Partition to submit to (adjust for your cluster)

# Optional: Email notifications (uncomment and set your email)
# #SBATCH --mail-type=BEGIN,END,FAIL        # Email on job start, end, and failure
# #SBATCH --mail-user=your.email@princeton.edu

# Optional: Account/QOS settings (uncomment if needed)
# #SBATCH --account=your_account_name
# #SBATCH --qos=your_qos_name

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
cd /scratch/gpfs/$USER/della_wonders/
# Load any required modules (uncomment if needed)
# module load anaconda3/2023.9
# module load python/3.11

# Set environment variables for della_wonders
export DELLA_SHARED_DIR="${DELLA_SHARED_DIR:-/tmp/shared}"
export DELLA_PROXY_PORT="${DELLA_PROXY_PORT:-9025}"

# Optional: Set custom shared directory based on job ID for isolation
# export DELLA_SHARED_DIR="/tmp/shared_${SLURM_JOB_ID}"

echo "Della Wonders Configuration:"
echo "  DELLA_SHARED_DIR: $DELLA_SHARED_DIR"
echo "  DELLA_PROXY_PORT: $DELLA_PROXY_PORT"
echo "=================================================================="

# Create logs directory if it doesn't exist
mkdir -p logs

# Create shared directory if it doesn't exist
mkdir -p "$DELLA_SHARED_DIR"

# Navigate to the project directory (adjust path as needed)
# Assuming the script is run from the project root
PROJECT_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"
cd "$PROJECT_DIR"

echo "Project Directory: $(pwd)"
echo "=================================================================="
ls

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

# Run start_wonders via pixi with proper error handling
set -e  # Exit on any error

echo "Running: pixi run start_wonders"
echo "Press Ctrl+C to stop gracefully"
echo ""

# Run the command with output buffering disabled for real-time logs
stdbuf -oL -eL pixi run start_wonders \
    --shared-dir "$DELLA_SHARED_DIR" \
    --verbose 2>&1 | while IFS= read -r line; do
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"
    done

# This should not be reached unless start_wonders exits normally
echo "=================================================================="
echo "start_wonders exited normally at: $(date)"
echo "=================================================================="