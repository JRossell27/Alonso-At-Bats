#!/bin/bash

# Mets Home Run Tracker Startup Script
echo "🏠⚾ Starting Mets Home Run Tracker System..."

# Get the port from environment variable or default to 5000
export PORT=${PORT:-5000}

echo "📋 Environment Configuration:"
echo "   Port: $PORT"
echo "   Python Version: $(python --version 2>&1)"
echo "   Working Directory: $(pwd)"

# Check if required files exist
echo "🔍 Checking required files..."
required_files=("mets_homerun_tracker.py" "mets_dashboard.py" "discord_integration.py" "baseball_savant_gif_integration.py")

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ $file found"
    else
        echo "   ❌ $file missing - system may not work properly"
    fi
done

# Start the Mets dashboard (which includes the tracker)
echo "🚀 Launching Mets Home Run Tracker Dashboard on port $PORT..."
python mets_dashboard.py 