# 📋 Deployment Checklist

Use this checklist to ensure a smooth deployment of your WealthFam instance.

## Pre-Deployment

### Repository Setup
- [ ] Code is pushed to GitHub/GitLab
- [ ] Repository is public OR deployment platform has access
- [ ] `.env.example` is committed (never commit `.env` with secrets!)
- [ ] `version.json` is up to date
- [ ] All deployment config files are present:
  - [ ] `Dockerfile`
  - [ ] `docker-compose.yml`
  - [ ] `.dockerignore`
  - [ ] `koyeb.json` (for Koyeb)
  - [ ] `railway.json` (for Railway)
  - [ ] `render.yaml` (for Render)
  - [ ] `fly.toml` (for Fly.io)

### Docker Image (if self-hosting)
- [ ] Docker image builds successfully: `docker build -t wealthfam:test .`
- [ ] Test run works: `docker run -p 8080:80 wealthfam:test`
- [ ] Health endpoint responds: `curl http://localhost:8080/health`
- [ ] Push to registry: `docker push wglabz/wealthfam:latest`

### Environment Variables
- [ ] `DATABASE_URL` configured for persistent volume
- [ ] `SECRET_KEY` generated (for production): `openssl rand -hex 32`
- [ ] `GEMINI_API_KEY` obtained (optional): https://makersuite.google.com/app/apikey
- [ ] Email sync credentials ready (optional)
- [ ] All required env vars documented in platform secrets

## Deployment Steps

### Choose Your Platform

#### Koyeb
- [ ] Click deploy button or use Koyeb CLI
- [ ] Configure persistent volume at `/data` (1GB minimum)
- [ ] Set environment variables
- [ ] Enable health checks at `/health`
- [ ] Select region (fra recommended)
- [ ] Deploy and wait for build

#### Railway
- [ ] Connect GitHub repository
- [ ] Add PostgreSQL/volume storage
- [ ] Configure environment variables
- [ ] Enable Dockerfile build
- [ ] Generate domain or add custom domain
- [ ] Deploy

#### Render
- [ ] Create new Web Service
- [ ] Connect repository
- [ ] Select Docker runtime
- [ ] Add persistent disk at `/data` (1GB)
- [ ] Configure environment variables
- [ ] Set health check path: `/health`
- [ ] Deploy

#### Fly.io
- [ ] Install flyctl: `curl -L https://fly.io/install.sh | sh`
- [ ] Login: `flyctl auth login`
- [ ] Launch app: `flyctl launch`
- [ ] Create volume: `flyctl volumes create wealthfam_data --size 1`
- [ ] Deploy: `flyctl deploy`

#### Self-Hosted (Docker)
- [ ] SSH into server
- [ ] Install Docker and Docker Compose
- [ ] Clone repository or download files
- [ ] Create `.env` from `.env.example`
- [ ] Run: `docker-compose up -d`
- [ ] Verify: `docker-compose logs -f`

## Post-Deployment

### Verification
- [ ] Application is accessible at deployment URL
- [ ] Health check passes: `/health` returns `{"status": "healthy"}`
- [ ] API docs accessible: `/api/v1/docs`
- [ ] Frontend loads without errors
- [ ] Can register/login successfully
- [ ] Database persists across restarts

### Security
- [ ] HTTPS is enabled (most platforms do this automatically)
- [ ] Default admin password changed (if applicable)
- [ ] Environment secrets are not exposed in logs
- [ ] CORS is properly configured for your domain
- [ ] Rate limiting is enabled (if available on platform)

### Performance
- [ ] Response times are acceptable
- [ ] Health checks are passing consistently
- [ ] Database queries are optimized
- [ ] Frontend assets are being served correctly
- [ ] Consider upgrading instance if needed

### Monitoring
- [ ] Set up uptime monitoring (UptimeRobot, Pingdom, etc.)
- [ ] Configure error tracking (Sentry, etc.)
- [ ] Enable platform logs/metrics
- [ ] Set up backup strategy for `/data` volume
- [ ] Document rollback procedure

### Documentation
- [ ] Update README with your deployment URL
- [ ] Document any custom configuration
- [ ] Share credentials with team (securely!)
- [ ] Create runbook for common issues

## Testing Production

### Functional Tests
- [ ] User registration works
- [ ] Login/logout works
- [ ] Can create transactions
- [ ] Can upload bank statements
- [ ] AI parsing works (if Gemini key provided)
- [ ] Email sync works (if configured)
- [ ] Mobile app can connect
- [ ] Charts and analytics display correctly

### Data Persistence
- [ ] Create test transaction
- [ ] Restart container/app
- [ ] Verify data is still there
- [ ] Check database file exists in volume

## Mobile App Setup

- [ ] Download latest APK from releases
- [ ] Configure backend URL in app settings
- [ ] Test SMS ingestion
- [ ] Verify device approval flow
- [ ] Test biometric login (if enabled)

## Backup Strategy

- [ ] Set up automated backups of `/data` volume
- [ ] Test restore procedure
- [ ] Document backup schedule
- [ ] Store backups in different location
- [ ] Consider database export scripts

## Maintenance

### Regular Tasks
- [ ] Weekly: Check logs for errors
- [ ] Monthly: Review resource usage
- [ ] Monthly: Update to latest version
- [ ] Quarterly: Review and rotate secrets
- [ ] Quarterly: Database optimization/vacuum

### Updates
- [ ] Pull latest image: `docker pull wglabz/wealthfam:latest`
- [ ] Backup data before update
- [ ] Apply update: `docker-compose up -d --force-recreate`
- [ ] Verify health: `/health`
- [ ] Test critical features

## Troubleshooting

### Common Issues
- [ ] If health check fails → Check database volume permissions
- [ ] If frontend is blank → Check browser console for errors
- [ ] If API returns 500 → Check application logs
- [ ] If image won't pull → Verify Docker Hub credentials
- [ ] If volume data lost → Check mount path configuration

### Getting Help
- [ ] Check [Deployment Guide](DEPLOYMENT.md)
- [ ] Search [GitHub Issues](https://github.com/oksbwn/wealthfam/issues)
- [ ] Ask on [Discord](https://discord.gg/wealthfam)
- [ ] Email: support@wealthfam.app

## Rollback Plan

In case of issues:
1. [ ] Document the issue
2. [ ] Stop current deployment
3. [ ] Revert to previous version/tag
4. [ ] Restore database backup (if needed)
5. [ ] Verify health check
6. [ ] Notify users (if applicable)

---

## ✅ Deployment Complete!

Congratulations! Your WealthFam instance is live.

**Next Steps:**
1. Share the URL with your team
2. Configure integrations (email, AI)
3. Import historical data
4. Set up mobile apps
5. Start tracking your finances!

---

*Last Updated: 2026-01-27*
