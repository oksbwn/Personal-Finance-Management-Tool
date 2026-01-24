#!/bin/bash

# Read version from version.json
MAJOR=$(grep -oP '"major": \K\d+' version.json)
MINOR=$(grep -oP '"minor": \K\d+' version.json)
PATCH=$(grep -oP '"patch": \K\d+' version.json)
VERSION="$MAJOR.$MINOR.$PATCH"

IMAGE_NAME="wealthfam"
# Generate build string: master hash-date (e.g., c196-20260125)
GIT_HASH=$(git rev-parse --short=4 HEAD 2>/dev/null || echo "0000")
BUILD_DATE=$(date +%Y%m%d)
BUILD_NUM="$GIT_HASH-$BUILD_DATE"
TAG="v$VERSION-b$BUILD_NUM"

NAMESPACE="wglabz"  # Default Docker Hub namespace

echo "Detected version: $VERSION"
echo "Build number: $BUILD_NUM"
echo "Full tag: $TAG"

echo "Building Docker image $IMAGE_NAME:$TAG..."
docker build --build-arg VITE_APP_BUILD=$BUILD_NUM -t $IMAGE_NAME:$TAG -t $IMAGE_NAME:latest .

if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
    
    read -p "Do you want to push to Docker Hub? (y/N): " PUSH
    if [[ "$PUSH" =~ ^[Yy]$ ]]; then
        read -p "Enter Docker Hub username [$NAMESPACE]: " USERNAME
        USERNAME=${USERNAME:-$NAMESPACE}
        
        echo "Logging into Docker Hub as $USERNAME..."
        docker login
        
        FULL_TAG="$USERNAME/$IMAGE_NAME:$TAG"
        FULL_LATEST="$USERNAME/$IMAGE_NAME:latest"
        
        echo "Tagging images..."
        docker tag $IMAGE_NAME:$TAG $FULL_TAG
        docker tag $IMAGE_NAME:latest $FULL_LATEST
        
        echo "Pushing $FULL_LATEST first (for layer caching)..."
        docker push $FULL_LATEST
        
        echo "Pushing $FULL_TAG..."
        docker push $FULL_TAG
        
        if [ $? -eq 0 ]; then
            echo "✅ Successfully pushed to Docker Hub!"
        else
            echo "❌ Push failed!"
        fi
    fi

    echo ""
    read -p "Do you want to deploy locally now? (docker compose up -d) (y/N): " DEPLOY
    if [[ "$DEPLOY" =~ ^[Yy]$ ]]; then
        echo "🚀 Launching with Docker Compose..."
        docker compose up -d --build
        echo "✅ Deployed! Check logs with 'docker compose logs -f'"
    fi
    
else
    echo "❌ Build failed!"
    exit 1
fi
