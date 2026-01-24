#!/bin/bash

# WealthFam Docker Publishing Script

IMAGE_NAME="wealthfam"
USERNAME="wglabz"

# Read version from version.json
MAJOR=$(grep -oP '"major": \K\d+' version.json)
MINOR=$(grep -oP '"minor": \K\d+' version.json)
PATCH=$(grep -oP '"patch": \K\d+' version.json)
VERSION="$MAJOR.$MINOR.$PATCH"

# Generate build string: master hash-date (e.g., c196-20260125)
GIT_HASH=$(git rev-parse --short=4 HEAD 2>/dev/null || echo "0000")
BUILD_DATE=$(date +%Y%m%d)
BUILD_NUM="$GIT_HASH-$BUILD_DATE"
TAG="v$VERSION-b$BUILD_NUM"
FULL_TAG="$USERNAME/$IMAGE_NAME:$TAG"
LATEST_TAG="$USERNAME/$IMAGE_NAME:latest"

echo "🚀 Starting Docker build for $FULL_TAG..."

# Check if buildx is available and use it for multi-arch build
if docker buildx version > /dev/null 2>&1; then
    echo "✨ Docker Buildx detected! Attempting multi-arch build (amd64, arm64)..."
    
    # Ensure a builder instance exists
    if ! docker buildx inspect wealthfam-builder > /dev/null 2>&1; then
        echo "🔧 Creating new buildx instance 'wealthfam-builder'..."
        docker buildx create --name wealthfam-builder --use --driver docker-container
        docker buildx bootstrap
    fi
    docker buildx use wealthfam-builder

    # Multi-arch build and push (Action requires --push to export to registry)
    echo "📦 Building and Pushing for linux/amd64 and linux/arm64..."
    
    echo "🔑 Ensuring you are logged in for push..."
    docker login
    
    if docker buildx build --platform linux/amd64,linux/arm64 \
        --build-arg VITE_APP_BUILD=$BUILD_NUM \
        -t "$FULL_TAG" \
        -t "$LATEST_TAG" \
        --push .; then
        
        echo "✅ Multi-arch build and push successful!"
        echo "🎉 published to https://hub.docker.com/r/$USERNAME/$IMAGE_NAME"
    else
        echo "❌ Multi-arch build failed. Falling back to standard local build..."
        # Fallback to standard build logic below
        docker buildx stop wealthfam-builder
        STANDARD_BUILD=true
    fi
    
else
    echo "⚠️ Docker Buildx not found. Proceeding with standard single-arch build..."
    STANDARD_BUILD=true
fi

if [ "$STANDARD_BUILD" = true ]; then
    # Build the monolithic image from the root directory (Single Arch)
    if docker build --build-arg VITE_APP_BUILD=$BUILD_NUM -t "$FULL_TAG" -t "$LATEST_TAG" .; then
        echo "✅ Local Build successful!"
        echo "📦 Image tagged as $FULL_TAG"
        
        # Push to Docker Hub (Standard)
        echo ""
        read -p "❓ Do you want to push this image to docker.io? (y/N): " confirm
        if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
            echo "🔑 Ensuring you are logged in..."
            docker login
            
            echo "📤 Pushing $FULL_TAG to Docker Hub..."
            if docker push "$FULL_TAG" && docker push "$LATEST_TAG"; then
                echo "🎉 Successfully published to https://hub.docker.com/r/$USERNAME/$IMAGE_NAME"
            else
                echo "❌ Push failed. Are you logged in to Docker Hub?"
                exit 1
            fi
        else
            echo "⏭️ Push skipped. You can push manually."
        fi
    else
        echo "❌ Build failed. Please check the logs above."
        exit 1
    fi
fi

echo ""
read -p "🚀 Do you want to deploy locally now? (docker-compose up -d) (y/N): " deploy
if [[ $deploy == [yY] || $deploy == [yY][eE][sS] ]]; then
    echo "🚀 Launching with Docker Compose..."
    docker compose up -d --build
fi
