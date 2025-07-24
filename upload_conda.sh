#!/bin/bash
# Helper script to upload conda package to anaconda.org

set -e

# Check if token is provided
if [[ -z "$ANACONDA_API_TOKEN" ]]; then
    echo "Please set ANACONDA_API_TOKEN environment variable"
    echo "Get your token from: https://anaconda.org/settings/access"
    echo ""
    echo "Usage:"
    echo "  export ANACONDA_API_TOKEN=your_token_here"
    echo "  ./upload_conda.sh"
    echo ""
    echo "Or provide token directly:"
    echo "  ./upload_conda.sh YOUR_TOKEN"
    exit 1
fi

# Use provided token or environment variable
TOKEN="${1:-$ANACONDA_API_TOKEN}"
USERNAME="wug"

# Find the conda package
PACKAGE=$(ls della-wonders-*.conda | head -1)

if [[ ! -f "$PACKAGE" ]]; then
    echo "No conda package found. Run 'pixi build' first."
    exit 1
fi

echo "Uploading $PACKAGE to anaconda.org as user '$USERNAME'..."

# Upload the package
pixi run anaconda -t "$TOKEN" upload "$PACKAGE" --user "$USERNAME" --force

echo "✅ Upload completed!"
echo ""
echo "Your package is now available at:"
echo "  https://anaconda.org/$USERNAME/della-wonders"
echo ""
echo "Users can install it with:"
echo "  conda install -c $USERNAME della-wonders"
echo "  # or"
echo "  pixi add -c $USERNAME della-wonders"