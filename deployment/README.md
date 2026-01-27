# 🚀 WealthFam Deployment

This folder contains all deployment configurations and scripts for WealthFam.

## 📁 Contents

### Platform Configuration Files

- **`.koyeb.yml`** - Koyeb deployment configuration (YAML format)
- **`koyeb.json`** - Koyeb detailed template with health checks
- **`railway.json`** - Railway platform configuration
- **`render.yaml`** - Render platform configuration
- **`fly.toml`** - Fly.io deployment configuration

### Scripts & Utilities

- **`setup_demo.sh`** - Quick demo deployment script for local testing
- **`.env.example`** - Environment variables template (copy to root as `.env`)

### Documentation References

See `/docs` folder for comprehensive deployment guides:
- `/docs/DEPLOYMENT.md` - Complete deployment guide
- `/docs/DEPLOYMENT_CHECKLIST.md` - Production deployment checklist
- `/docs/QUICK_DEPLOY.md` - Quick command reference
- `/docs/GETTING_STARTED.md` - Beginner's deployment guide

---

## 🎯 Quick Start

### One-Click Cloud Deployment

Choose your preferred platform and click to deploy:

#### Koyeb (Free Tier Available)
[![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&repository=github.com/oksbwn/wealthfam&branch=main&name=wealthfam)

**Features**: Free tier, global edge network, automatic SSL

#### Railway ($5/month credit)
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/wealthfam)

**Features**: Easy setup, automatic deployments, built-in metrics

---

### Local Demo Deployment

Quick local testing with Docker:

```bash
# From this deployment folder
bash setup_demo.sh

# Access at http://localhost:8080
```

---

## 🐳 Docker Deployment

### Quick Start
```bash
# Pull latest image
docker pull wglabz/wealthfam:latest

# Run with Docker Compose (from project root)
docker-compose up -d
```

### Manual Docker Run
```bash
docker run -d \
  -p 80:80 \
  -v $(pwd)/data:/data \
  --name wealthfam \
  wglabz/wealthfam:latest
```

---

## ⚙️ Platform-Specific Deployment

### Koyeb

**Configuration**: Uses `koyeb.json`

**Deploy via CLI**:
```bash
koyeb service create wealthfam \
  --docker wglabz/wealthfam:latest \
  --ports 80:http \
  --routes /:80 \
  --env DATABASE_URL=duckdb:////data/family_finance_v3.duckdb
```

**Deploy via Button**: Click the Koyeb badge above

---

### Railway

**Configuration**: Uses `railway.json`

**Deploy**:
1. Click the Railway badge above
2. Connect your GitHub repository
3. Railway auto-detects Dockerfile
4. Add environment variables if needed
5. Deploy

---

### Render

**Configuration**: Uses `render.yaml`

**Deploy**:
1. Create new Web Service on Render
2. Connect your repository
3. Select "Docker" as runtime
4. Add persistent disk at `/data` (1GB minimum)
5. Deploy

---

### Fly.io

**Configuration**: Uses `fly.toml`

**Deploy via CLI**:
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
flyctl auth login

# Launch (from project root)
flyctl launch

# Create volume for database
flyctl volumes create wealthfam_data --size 1

# Deploy
flyctl deploy
```

---

## 🔧 Environment Variables

Copy `.env.example` to project root as `.env` and configure:

### Essential Variables

```bash
# Database (required)
DATABASE_URL=duckdb:////data/family_finance_v3.duckdb

# Security (auto-generated if not set)
SECRET_KEY=your-secret-key-here
```

### Optional Features

```bash
# AI-powered features
GEMINI_API_KEY=your_gemini_api_key

# Email sync
IMAP_SERVER=imap.gmail.com
IMAP_USERNAME=your@email.com
IMAP_PASSWORD=your_app_password
```

See `.env.example` for complete list.

---

## 📊 Platform Comparison

| Platform | Free Tier | Deploy Method | Best For |
|----------|-----------|---------------|----------|
| **Koyeb** | ✅ Yes | One-click | Quick demos, testing |
| **Railway** | $5 credit | One-click | Hobby projects |
| **Render** | ✅ Yes | Manual setup | Production apps |
| **Fly.io** | ✅ Yes | CLI | Global deployment |
| **Docker** | N/A | Self-hosted | Full control |

---

## ✅ Health Check

All deployments include a health check endpoint:

```bash
# Check if deployment is healthy
curl https://your-deployment-url/health

# Expected response:
{
  "status": "healthy",
  "service": "WealthFam",
  "database": "connected"
}
```

---

## 🔄 Updates & Maintenance

### Update Deployed Instance

**Platform Deployments** (Koyeb/Railway/Render):
- Push to main branch → Automatic redeployment
- Or trigger manual redeploy in platform dashboard

**Docker Self-Hosted**:
```bash
# Pull latest image
docker pull wglabz/wealthfam:latest

# Restart with new image
docker-compose down
docker-compose up -d

# Or using Docker directly
docker stop wealthfam
docker rm wealthfam
docker run -d -p 80:80 -v $(pwd)/data:/data --name wealthfam wglabz/wealthfam:latest
```

---

## 🆘 Troubleshooting

### Common Issues

**Container won't start**:
```bash
# Check logs
docker logs wealthfam

# Or platform-specific
koyeb service logs wealthfam
flyctl logs
```

**Database not persisting**:
- Ensure volume is mounted at `/data`
- Check volume permissions
- Verify persistent storage is configured in platform

**Health check failing**:
```bash
# Test health endpoint
curl https://your-url/health

# Check database file exists
ls -la data/
```

**Cannot access application**:
- Check port mapping (80:80)
- Verify firewall rules
- Check platform logs for errors

### Getting Help

- 📖 **Documentation**: `/docs/DEPLOYMENT.md`
- 🐛 **Issues**: [GitHub Issues](https://github.com/oksbwn/wealthfam/issues)
- 💬 **Community**: [Discord](https://discord.gg/wealthfam)

---

## 📚 Additional Resources

### Complete Documentation

Located in `/docs` folder:

1. **DEPLOYMENT.md** - Detailed deployment guide for all platforms
2. **DEPLOYMENT_CHECKLIST.md** - Production deployment checklist
3. **QUICK_DEPLOY.md** - Quick command reference
4. **GETTING_STARTED.md** - Beginner's guide

### Files in This Folder

```
deployment/
├── README.md                 # This file
├── .koyeb.yml               # Koyeb YAML config
├── koyeb.json               # Koyeb detailed template
├── railway.json             # Railway configuration
├── render.yaml              # Render configuration
├── fly.toml                 # Fly.io configuration
├── setup_demo.sh            # Demo deployment script
└── .env.example             # Environment template
```

---

## 🎯 Next Steps

1. **Choose a platform** from the options above
2. **Review the configuration** file for your platform
3. **Deploy using** one-click button or CLI
4. **Configure environment** variables if needed
5. **Verify deployment** using health check
6. **Access your instance** and start using WealthFam!

---

## 🔐 Security Notes

- Never commit `.env` files with real credentials
- Use strong `SECRET_KEY` in production
- Enable HTTPS (automatic on all cloud platforms)
- Configure CORS for your specific domain
- Regular backups of `/data` volume

---

## 🎉 Success!

Once deployed, you'll have WealthFam running with:
- ✅ Persistent database storage
- ✅ Automatic HTTPS
- ✅ Health monitoring
- ✅ Live updates via git push

**Happy financing! 💰**

---

*For detailed instructions, see `/docs/DEPLOYMENT.md`*
