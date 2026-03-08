#!/bin/bash
# deploy.sh — Build and deploy the SAM stack
# Usage: ./deploy.sh

set -euo pipefail

# Prompt for secrets if not already in samconfig.toml
echo "=== Voice-to-Notion Deploy ==="
echo ""
echo "Make sure you have filled in samconfig.toml with your real API keys."
echo "Press ENTER to continue or Ctrl-C to cancel."
read -r

sam build

sam deploy
