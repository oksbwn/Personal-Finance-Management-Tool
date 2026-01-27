# 🎯 Getting Started with WealthFam Deployment

Welcome! This guide will help you deploy WealthFam in under 5 minutes.

## 🚀 Quick Links

- 🐳 **Docker Hub**: [wglabz/wealthfam](https://hub.docker.com/r/wglabz/wealthfam)
- 📱 **Mobile APK**: [Download Latest](../mobile_app/build/app/outputs/flutter-apk/app-release.apk)
- 📖 **Full Deployment Guide**: [DEPLOYMENT.md](DEPLOYMENT.md)
- ✅ **Deployment Checklist**: [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

## 🌟 Choose Your Deployment Method

### Option 1: One-Click Cloud Deploy (Recommended for Beginners)

**Best for**: Quick demos, hobby projects, trying WealthFam

**Time**: 2-3 minutes

**Cost**: Free tier available

**Steps**:
1. Click one of these buttons:
   - [![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&repository=github.com/oksbwn/wealthfam&branch=main&name=wealthfam)
   - [![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/wealthfam)

2. Sign in with GitHub
3. Click "Deploy"
4. Wait ~3 minutes
5. Access your instance! 🎉

### Option 2: Docker (Recommended for Self-Hosting)

**Best for**: Home servers, Raspberry Pi, full control

**Time**: 1 minute

**Cost**: Free (your hardware)

**Steps**:
```bash
# 1. Pull the image
docker pull wglabz/wealthfam:latest

# 2. Run it
docker run -d \
  -p 80:80 \
  -v $(pwd)/data:/data \
  --name wealthfam \
  wglabz/wealthfam:latest

# 3. Access at http://localhost
```

Or use Docker Compose:
```bash
# 1. Create docker-compose.yml
curl -o docker-compose.yml https://raw.githubusercontent.com/oksbwn/wealthfam/main/docker-compose.yml

# 2. Start
docker-compose up -d

# 3. Access at http://localhost
```

### Option 3: Demo Setup (Recommended for Testing)

**Best for**: Local testing, development

**Time**: 2 minutes

**Steps**:
```bash
# Download and run setup script
curl -fsSL https://raw.githubusercontent.com/oksbwn/wealthfam/main/setup_demo.sh | bash

# Access at http://localhost:8080
```

## 📱 After Deployment

### 1. First Login
- Open your deployment URL
- Register your account (first user = admin)
- Explore the dashboard

### 2. Mobile App Setup (Optional)
1. Download [WealthFam Mobile APK](../mobile_app/build/app/outputs/flutter-apk/app-release.apk)
2. Install on Android device
3. Configure backend URL in Settings
4. Login with your credentials

### 3. Configure AI Features (Optional)
1. Get Gemini API key: https://makersuite.google.com/app/apikey
2. Add to environment variables:
   - **Platform deployments**: Add `GEMINI_API_KEY` in dashboard
   - **Docker**: Add to `.env` or docker-compose.yml
3. Restart your instance

### 4. Import Your Data
- **Bank Statements**: Upload CSV files
- **Mutual Funds**: Upload CAS PDF from email
- **Email Sync**: Configure IMAP settings
- **Manual Entry**: Add transactions one by one

## 🔧 Configuration

### Essential Environment Variables

Only required for advanced features:

```bash
# AI-powered transaction parsing
GEMINI_API_KEY=your_api_key_here

# Secure your deployment (auto-generated if not set)
SECRET_KEY=$(openssl rand -hex 32)

# Email sync (optional)
IMAP_SERVER=imap.gmail.com
IMAP_USERNAME=your@email.com
IMAP_PASSWORD=your_app_password
```

## ✅ Verify Deployment

Check if everything is working:

```bash
# 1. Health check
curl http://your-domain/health

# Expected response:
# {"status":"healthy","service":"WealthFam","database":"connected"}

# 2. API documentation
# Visit: http://your-domain/api/v1/docs

# 3. Frontend
# Visit: http://your-domain
# Should see WealthFam login page
```

## 🆘 Common Issues

### "Cannot access the application"
- Check if container is running: `docker ps`
- Check logs: `docker logs wealthfam`
- Verify port is not in use: `netstat -an | grep 80`

### "Database not persisting"
- Ensure volume is mounted: `docker inspect wealthfam`
- Check volume permissions: `ls -la data/`

### "Health check failing"
- Visit `/health` endpoint directly
- Check database file exists: `ls data/*.duckdb`
- Review application logs

### "Mobile app can't connect"
- Ensure backend URL is correct (include http/https)
- Check if backend is publicly accessible
- Verify no firewall blocking connection

## 📚 Next Steps

Once deployed and verified:

1. **Read the guides**:
   - [Full Deployment Guide](DEPLOYMENT.md) - All deployment options
   - [Deployment Checklist](DEPLOYMENT_CHECKLIST.md) - Production checklist

2. **Explore features**:
   - Add your first transaction
   - Upload a bank statement
   - Try AI transaction parsing
   - Set up budgets and goals

3. **Customize**:
   - Set up email sync for automatic ingestion
   - Configure family members
   - Create custom categories
   - Set up recurring transactions

4. **Secure**:
   - Enable 2FA (if available)
   - Backup your data regularly
   - Use strong passwords
   - Keep your instance updated

## 🌐 Demo Instance

Try WealthFam without deploying:

**URL**: https://demo.wealthfam.app  
**Username**: demo@wealthfam.app  
**Password**: demo123

> ⚠️ Demo data resets daily. Don't use for real financial data!

## 💬 Get Help

- 📖 Documentation: See all guides in `/docs`
- 🐛 Issues: [GitHub Issues](https://github.com/oksbwn/wealthfam/issues)
- 💬 Community: [Discord](https://discord.gg/wealthfam)
- 📧 Email: support@wealthfam.app

## 🎉 Success!

You're now running WealthFam! Start tracking your finances like a pro.

**Happy financing! 💰**

---

*Last Updated: 2026-01-27*
