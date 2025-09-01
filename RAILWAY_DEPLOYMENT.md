# 🚀 Railway Deployment Guide

## 📋 Prerequisites
- GitHub account
- Railway account (https://railway.app)
- Your AutoTrade Bot code

## 🔧 Step-by-Step Deployment

### 1. **GitHub Repository Setup**
```bash
# Initialize git if not already done
git init
git add .
git commit -m "Initial commit for Railway deployment"

# Push to GitHub
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

### 2. **Railway Dashboard Setup**
1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository
5. Click "Deploy Now"

### 3. **Environment Variables Setup**
Railway dashboard এ যান এবং Environment Variables set করুন:

**Required Variables:**
```
PIONEX_API_KEY=your_real_pionex_api_key
PIONEX_SECRET_KEY=your_real_pionex_secret_key
BYBIT_API_KEY=your_real_bybit_api_key
BYBIT_SECRET_KEY=your_real_bybit_secret_key
SECRET_KEY=your_secure_flask_secret_key
ENVIRONMENT=production
DEBUG=False
```

**Optional Variables:**
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
SENDER_EMAIL=your_email
SENDER_PASSWORD=your_email_password
```

### 4. **Deployment Configuration**
Railway automatically detect করবে:
- ✅ Python 3.11
- ✅ Requirements.txt
- ✅ Procfile
- ✅ Main.py

### 5. **Custom Domain (Optional)**
1. Railway dashboard এ যান
2. "Settings" tab এ যান
3. "Custom Domains" section এ custom domain add করুন

## 🌐 Access Your App
Deployment complete হওয়ার পর:
- **Railway URL**: `https://your-app-name.railway.app`
- **Custom Domain**: `https://yourdomain.com` (if configured)

## 📊 Monitoring
Railway dashboard এ দেখতে পাবেন:
- ✅ Build logs
- ✅ Deployment status
- ✅ Environment variables
- ✅ Custom domains
- ✅ Usage metrics

## 🔄 Auto-Deploy
GitHub এ push করলেই automatically deploy হবে!

## 🚨 Troubleshooting

### Build Errors
```bash
# Check logs in Railway dashboard
# Common issues:
# - Missing dependencies in requirements.txt
# - Python version mismatch
# - Import errors
```

### Runtime Errors
```bash
# Check Railway logs
# Verify environment variables
# Test locally first
```

## 📱 Testing Your Deployed App
1. **Health Check**: Visit your Railway URL
2. **API Test**: Test trading endpoints
3. **WebSocket**: Check real-time updates
4. **Database**: Verify data persistence

## 🎉 Success!
Your AutoTrade Bot is now running on Railway! 🚀

## 📞 Support
- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- GitHub Issues: Your repository
