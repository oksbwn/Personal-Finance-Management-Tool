# 🚀 Quick Deployment Reference

Quick commands and URLs for deploying WealthFam.

## One-Click Deployments

```
Koyeb:   https://app.koyeb.com/deploy?type=git&repository=github.com/oksbwn/wealthfam&branch=main&name=wealthfam
Railway: https://railway.app/template/wealthfam  
Render:  https://render.com/deploy?repo=https://github.com/oksbwn/wealthfam
```

## CLI Deployments

### Fly.io
```bash
# Setup
curl -L https://fly.io/install.sh | sh
flyctl auth login

# Deploy
flyctl launch
flyctl volumes create wealthfam_data --size 1
flyctl deploy
```

### Docker (Self-Hosted)
```bash
# Quick start
docker pull wglabz/wealthfam:latest
docker run -d -p 80:80 -v $(pwd)/data:/data wglabz/wealthfam:latest

# Or with compose
curl -o docker-compose.yml https://raw.githubusercontent.com/oksbwn/wealthfam/main/docker-compose.yml
docker-compose up -d
```

## Build Commands

```bash
# Build locally
docker build -t wealthfam:local .

# Test locally
docker run -p 8080:80 -v $(pwd)/data:/data wealthfam:local

# Push to registry (requires login)
docker tag wealthfam:local wglabz/wealthfam:latest
docker push wglabz/wealthfam:latest
```

## Health Checks

```bash
# Check health
curl http://your-domain/health

# Expected response
{"status":"healthy","service":"WealthFam","database":"connected"}
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Container won't start | Check logs: `docker logs <container_id>` |
| Database not persisting | Ensure volume is mounted at `/data` |
| Health check failing | Verify database permissions in volume |
| Cannot access frontend | Check port mapping and firewall rules |

## Environment Variables Quick Reference

```bash
# Minimum viable deployment
DATABASE_URL=duckdb:////data/family_finance_v3.duckdb

# With AI features
GEMINI_API_KEY=your_key_here

# Production security
SECRET_KEY=$(openssl rand -hex 32)
```

## Demo Setup

```bash
# Run setup script
curl -fsSL https://raw.githubusercontent.com/oksbwn/wealthfam/main/setup_demo.sh | bash

# Or manually
bash setup_demo.sh
```

## Update Deployment

```bash
# Docker
docker-compose pull
docker-compose up -d --force-recreate

# Fly.io
flyctl deploy

# Platform-managed (Koyeb/Railway/Render)
# Push to main branch or trigger redeploy in dashboard
```

## Backup & Restore

```bash
# Backup (while running)
docker cp wealthfam:/data/family_finance_v3.duckdb ./backup_$(date +%Y%m%d).duckdb

# Restore (container stopped)
docker cp ./backup_20260127.duckdb wealthfam:/data/family_finance_v3.duckdb
```

## Useful URLs

- Main Docs: `docs/DEPLOYMENT.md`
- Checklist: `docs/DEPLOYMENT_CHECKLIST.md`
- API Docs: `http://your-domain/api/v1/docs`
- Health Check: `http://your-domain/health`

---

*For complete instructions, see [DEPLOYMENT.md](DEPLOYMENT.md)*
