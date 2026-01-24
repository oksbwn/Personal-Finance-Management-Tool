#!/bin/bash

# Configuration
REMOTE_USER="oksbwn"
REMOTE_HOST="192.168.0.9"
REMOTE_DIR="~/wealthfam"
ARCHIVE_NAME="wealthfam_deploy.tar.gz"

# Read version from version.json
MAJOR=$(grep -oP '"major": \K\d+' version.json)
MINOR=$(grep -oP '"minor": \K\d+' version.json)
PATCH=$(grep -oP '"patch": \K\d+' version.json)
VERSION="$MAJOR.$MINOR.$PATCH"

# Generate build string: master hash-date (e.g., c196-20260124)
GIT_HASH=$(git rev-parse master 2>/dev/null | cut -c1-4 || echo "0000")
BUILD_DATE=$(date +%Y%m%d)
BUILD_NUM="$GIT_HASH-$BUILD_DATE"

echo "📦 Packaging WealthFam v$VERSION (Build: $BUILD_NUM)..."

# Create a temporary archive excluding unnecessary files
# Using tar to preserve permissions and keep the transfer light
tar --exclude='frontend/node_modules' \
    --exclude='backend/__pycache__' \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='data' \
    --exclude="$ARCHIVE_NAME" \
    -czf "$ARCHIVE_NAME" .

if [ $? -eq 0 ]; then
    echo "✅ Archive created: $ARCHIVE_NAME"
    
    echo "🚀 Uploading to $REMOTE_USER@$REMOTE_HOST..."
    # Ensure remote directory exists and upload
    ssh $REMOTE_USER@$REMOTE_HOST "mkdir -p $REMOTE_DIR"
    scp $ARCHIVE_NAME $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/
    
    if [ $? -eq 0 ]; then
        echo "📂 Extracting on Raspberry Pi..."
        ssh $REMOTE_USER@$REMOTE_HOST "cd $REMOTE_DIR && tar -xzf $ARCHIVE_NAME && rm $ARCHIVE_NAME"
        
        echo "✨ Deployment successful!"
        echo "To run the app on your Pi, SSH into it and run:"
        echo "cd $REMOTE_DIR && VITE_APP_BUILD=$BUILD_NUM docker-compose down && VITE_APP_BUILD=$BUILD_NUM TAG=latest docker-compose up -d --build --force-recreate"
    else
        echo "❌ Upload failed!"
    fi
    
    # Cleanup local archive
    rm $ARCHIVE_NAME
else
    echo "❌ Packaging failed!"
    exit 1
fi
