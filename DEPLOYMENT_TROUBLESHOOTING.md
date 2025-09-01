# 🚨 Railway Deployment Troubleshooting Guide

## Common Issues and Solutions

### 1. **Nixpacks Build Error: externally-managed-environment**

**Error:**
```
error: externally-managed-environment
This environment is externally managed
```

**Solution:**
We've switched to Dockerfile deployment. The project now uses:
- `Dockerfile` - Main deployment method
- `railway.json` - Updated to use Dockerfile
- Virtual environment setup in Docker

### 2. **Python Import Errors**

**Error:**
```
ModuleNotFoundError: No module named 'module_name'
```

**Solution:**
- Check `requirements.txt` has all dependencies
- Ensure virtual environment is activated
- Verify Python version compatibility (3.11+)

### 3. **Port Binding Issues**

**Error:**
```
Address already in use
```

**Solution:**
- Railway automatically sets `$PORT` environment variable
- Use `0.0.0.0:$PORT` in configuration
- Don't hardcode port numbers

### 4. **Environment Variables Missing**

**Error:**
```
KeyError: 'PIONEX_API_KEY'
```

**Solution:**
Set these in Railway dashboard:
```
PIONEX_API_KEY=your_key
PIONEX_SECRET_KEY=your_secret
BYBIT_API_KEY=your_key
BYBIT_SECRET_KEY=your_secret
SECRET_KEY=your_secret
ENVIRONMENT=production
DEBUG=False
```

## 🔧 **Deployment Methods**

### **Method 1: Dockerfile (Recommended)**
```json
{
  "build": {
    "builder": "DOCKERFILE"
  }
}
```

### **Method 2: Nixpacks (Alternative)**
```toml
[phases.setup]
nixPkgs = ["python311", "python311Packages.pip", "python311Packages.virtualenv"]

[phases.install]
cmds = [
  "python -m venv /opt/venv",
  "source /opt/venv/bin/activate",
  "pip install -r requirements.txt"
]
```

## 🚀 **Quick Fix Commands**

### **Force Rebuild:**
```bash
# In Railway dashboard
# Settings → Redeploy → Force Rebuild
```

### **Check Logs:**
```bash
# Railway dashboard → Deployments → View Logs
```

### **Environment Variables:**
```bash
# Railway dashboard → Variables → Add/Edit
```

## 📋 **Pre-Deployment Checklist**

- [ ] All dependencies in `requirements.txt`
- [ ] Environment variables set in Railway
- [ ] `.env` file not committed to Git
- [ ] `main.py` exports `app` variable
- [ ] Port binding uses `$PORT` environment variable
- [ ] Health check endpoint exists (`/`)

## 🆘 **Still Having Issues?**

1. **Check Railway Logs** - Detailed error information
2. **Verify Environment Variables** - All required vars set
3. **Test Locally First** - `python main.py` should work
4. **Check Dependencies** - `pip install -r requirements.txt`
5. **Contact Support** - Railway Discord or GitHub Issues

## 🔄 **Fallback Deployment**

If Dockerfile fails, try:
1. Switch to Nixpacks in Railway dashboard
2. Use the updated `nixpacks.toml`
3. Force rebuild the project

---

**Remember:** Always test locally before deploying to Railway!
