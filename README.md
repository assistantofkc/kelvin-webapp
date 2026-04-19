# Personal Homepage - PythonAnywhere Deployment Guide

## Step 1: Create PythonAnywhere Account
1. Go to https://www.pythonanywhere.com
2. Sign up for a free account (Beginner tier)
3. Verify your email

## Step 2: Upload Files to PythonAnywhere

### Option A: Use PythonAnywhere Web UI

1. Log in to PythonAnywhere
2. Go to **Files** tab
3. Navigate to `/home/yourusername/` (or create a folder called `webapp`)
4. Click **Upload** and upload these files:
   - `app.py`
   - `requirements.txt`
5. Create folder `templates` and upload `templates/index.html`

### Option B: Use Git (Recommended)

1. Push this folder to GitHub/GitLab
2. In PythonAnywhere Bash console:
   ```bash
   cd ~
   git clone https://github.com/YOURUSERNAME/webapp.git
   ```

## Step 3: Set Up Virtual Environment

In PythonAnywhere Bash console:
```bash
cd ~/webapp
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 4: Configure Web App

1. Go to **Web** tab
2. Click **Add a new web app**
3. Choose **Manual configuration**
4. Select **Python 3.x**
5. For WSGI file, click **Edit** and replace content with:

```python
import sys
path = '/home/yourusername/webapp'
if path not in sys.path:
    sys.path.append(path)

from app import app as application
```

## Step 5: Configure Static Files

In the Web tab, add a static files mapping:
- URL: `/static/`
- Path: `/home/yourusername/webapp/static/`

## Step 6: Reload and Access

1. Click **Reload** button
2. Your site will be at: `https://yourusername.pythonanywhere.com`

---

## Troubleshooting

### 500 Internal Server Error
- Check the **Error log** in Web tab
- Common issues:
  - Wrong path in WSGI file
  - Missing templates folder
  - Virtual environment not activated

### Static files not loading
- Make sure `/static/` mapping is configured in Web tab

### Need to edit files?
- Use PythonAnywhere **Files** tab or
- Edit locally and re-upload

---

## Customization

Edit `templates/index.html` to update:
- Your name
- Bio text
- Social links
- Avatar emoji
- Colors/styles

Then reload the web app to see changes.

---

## Free Tier Limitations

- Web app goes to sleep after 3 months of inactivity (wake it up by visiting)
- Only one web app per account on free tier
- No custom domain (uses pythonanywhere.com subdomain)
- Limited to Python web apps only

For better reliability, consider upgrading to Hacker plan ($5/month).
