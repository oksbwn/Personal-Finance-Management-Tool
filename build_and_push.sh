#!/bin/bash

# Read version from version.json
MAJOR=$(grep -oP '"major": \K\d+' version.json)
MINOR=$(grep -oP '"minor": \K\d+' version.json)
PATCH=$(grep -oP '"patch": \K\d+' version.json)
VERSION="$MAJOR.$MINOR.$PATCH"

IMAGE_NAME="wealthfam"
# Generate build string: master hash-date (e.g., c196-20260124)
GIT_HASH=$(git rev-parse master 2>/dev/null | cut -c1-4 || echo "0000")
BUILD_DATE=$(date +%Y%m%d)
BUILD_NUM="$GIT_HASH-$BUILD_DATE"
TAG="v$VERSION-b$BUILD_NUM"

echo "Building Docker image $IMAGE_NAME:$TAG..."
docker build --build-arg VITE_APP_BUILD=$BUILD_NUM -t $IMAGE_NAME:$TAG -t $IMAGE_NAME:latest .

if [ $? -eq 0 ]; then
    echo "Build successful!"
    
    read -p "Do you want to push to Docker Hub? (y/N): " PUSH
    if [[ "$PUSH" =~ ^[Yy]$ ]]; then
        read -p "Enter Docker Hub username [WGLabz]: " USERNAME
        USERNAME=${USERNAME:-WGLabz}
        docker tag $IMAGE_NAME:$TAG $USERNAME/$IMAGE_NAME:$TAG
        docker tag $IMAGE_NAME:latest $USERNAME/$IMAGE_NAME:latest
        docker push $USERNAME/$IMAGE_NAME:$TAG
        docker push $USERNAME/$IMAGE_NAME:latest
    fi

    echo ""
    read -p "Do you want to deploy locally now? (docker-compose up -d) (y/N): " DEPLOY
    if [[ "$DEPLOY" =~ ^[Yy]$ ]]; then
        echo "Launching with Docker Compose..."
        docker compose up -d --build
    fi
else
    echo "Build failed!"
    exit 1
fi
