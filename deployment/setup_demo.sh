#!/bin/bash

# WealthFam Demo Setup Script
# This script sets up a demo instance with sample data

set -e

echo "🎯 WealthFam Demo Setup"
echo "======================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DEMO_USER="demo@wealthfam.app"
DEMO_PASSWORD="demo123"
DEMO_NAME="Demo User"

echo -e "${BLUE}Step 1: Checking prerequisites...${NC}"
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed. Aborting."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose is required but not installed. Aborting."; exit 1; }
echo -e "${GREEN}✅ Prerequisites met${NC}"
echo ""

echo -e "${BLUE}Step 2: Pulling latest WealthFam image...${NC}"
docker pull wglabz/wealthfam:latest
echo -e "${GREEN}✅ Image pulled${NC}"
echo ""

echo -e "${BLUE}Step 3: Creating demo directory...${NC}"
DEMO_DIR="wealthfam-demo"
mkdir -p $DEMO_DIR
cd $DEMO_DIR
echo -e "${GREEN}✅ Directory created: $DEMO_DIR${NC}"
echo ""

echo -e "${BLUE}Step 4: Creating docker-compose.yml...${NC}"
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  wealthfam:
    image: wglabz/wealthfam:latest
    container_name: wealthfam-demo
    restart: unless-stopped
    ports:
      - "8080:80"
    volumes:
      - ./data:/data
    environment:
      - DATABASE_URL=duckdb:////data/family_finance_v3.duckdb
      - DEMO_MODE=true
EOF
echo -e "${GREEN}✅ Configuration created${NC}"
echo ""

echo -e "${BLUE}Step 5: Starting WealthFam...${NC}"
docker-compose up -d
echo -e "${GREEN}✅ Container started${NC}"
echo ""

echo -e "${BLUE}Step 6: Waiting for service to be ready...${NC}"
sleep 10

# Wait for health check
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Service is healthy${NC}"
        break
    fi
    echo -n "."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${YELLOW}⚠️  Service health check timed out. Check logs with: docker-compose logs${NC}"
fi

echo ""
echo -e "${GREEN}🎉 WealthFam Demo is ready!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${BLUE}📍 Access URL:${NC}     http://localhost:8080"
echo -e "${BLUE}🔐 Username:${NC}       $DEMO_USER"
echo -e "${BLUE}🔑 Password:${NC}       $DEMO_PASSWORD"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "  1. Open http://localhost:8080 in your browser"
echo "  2. Create your first account (first user becomes admin)"
echo "  3. Start adding transactions or upload bank statements"
echo "  4. Explore AI-powered insights and analytics"
echo ""
echo -e "${YELLOW}🛠️  Useful Commands:${NC}"
echo "  View logs:        cd $DEMO_DIR && docker-compose logs -f"
echo "  Stop demo:        cd $DEMO_DIR && docker-compose down"
echo "  Restart demo:     cd $DEMO_DIR && docker-compose restart"
echo "  Remove demo:      cd $DEMO_DIR && docker-compose down -v && cd .. && rm -rf $DEMO_DIR"
echo ""
echo -e "${BLUE}📱 Mobile App:${NC}"
echo "  Download the Android APK from:"
echo "  https://github.com/oksbwn/wealthfam/releases/latest"
echo ""
echo -e "${GREEN}Happy financing! 💰${NC}"
