# Deployment & Sharing Guide

This guide covers how to share the **SQL Server → Snowflake DDL Converter** with teammates, deploy it to the cloud, or containerize it for local/private hosting.

## Option 1: Streamlit Cloud (Easiest for Web UI)

**Streamlit Cloud** is the simplest way to host and share the Streamlit UI publicly.

### Steps

1. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit: DDL Converter"
   git remote add origin https://github.com/YOUR_USERNAME/ddl-converter.git
   git push -u origin main
   ```

2. **Create a Streamlit Cloud account** at [share.streamlit.io](https://share.streamlit.io)

3. **Deploy:**
   - Click "New app" → Connect your GitHub repository
   - Select branch, file path: `streamlit_app.py`
   - Deploy

4. **Share the URL** (e.g., `https://share.streamlit.io/YOUR_USERNAME/ddl-converter/main/streamlit_app.py`) with teammates

### Environment Variables

If you want Claude API integration on Streamlit Cloud:
1. In Streamlit Cloud dashboard, go to **App settings** → **Secrets**
2. Add:
   ```
   CLAUDE_API_KEY = "sk-your-key-here"
   ```
3. Save; the app auto-reloads

**Cost:** Free tier supports 3 deployments; paid tiers available.

---

## Option 2: Docker (Local/Private Hosting)

Deploy the app locally or to a Docker-compatible server (AWS ECS, Azure Container Instances, DigitalOcean, etc.).

### Build & Run Locally

```bash
docker build -t ddl-converter .
docker run -p 8502:8502 \
  -e CLAUDE_API_KEY="sk-your-key" \
  ddl-converter
```

Open http://localhost:8502

### Deploy to a Server

Push the image to Docker Hub or a private registry, then pull and run on your server:

```bash
# On your server (Ubuntu/Debian example)
docker run -d \
  --name ddl-converter \
  -p 80:8502 \
  -e CLAUDE_API_KEY="sk-your-key" \
  YOUR_DOCKER_USERNAME/ddl-converter:latest
```

**Cost:** Depends on hosting (DigitalOcean Droplet ~$5–15/month, AWS varies).

---

## Option 3: Heroku (Deprecated but still available)

Heroku has deprecated the free tier as of Nov 2022, but paid dynos still work.

### Steps

1. Install the Heroku CLI
2. Create a `Procfile`:
   ```
   web: streamlit run streamlit_app.py --server.port $PORT
   ```
3. Deploy:
   ```bash
   heroku create your-app-name
   heroku config:set CLAUDE_API_KEY=sk-your-key
   git push heroku main
   ```

**Cost:** $5–7/month minimum for a dyno.

---

## Option 4: GitHub + Command Line (For Technical Teams)

Share the code on GitHub and let users run it locally.

### Steps for End Users

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/ddl-converter.git
   cd ddl-converter
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables (optional for Claude):**
   ```bash
   # Windows PowerShell
   $env:CLAUDE_API_KEY = "sk-your-key"
   # Unix-like
   export CLAUDE_API_KEY="sk-your-key"
   ```

4. **Run the CLI:**
   ```bash
   python cli.py my_table.sql -o my_table_snowflake.sql
   ```

   Or run the Streamlit UI:
   ```bash
   streamlit run streamlit_app.py
   ```

5. **Run tests:**
   ```bash
   python run_tests.py
   ```

---

## Option 5: AWS Lambda / Serverless

For a lightweight API-only deployment (no UI).

### Quick Setup

1. Create a simple `lambda_handler.py`:
   ```python
   from converter import convert
   import json
   
   def lambda_handler(event, context):
       sql_text = event.get('body', '')
       res = convert(sql_text)
       return {
           'statusCode': 200,
           'body': json.dumps({
               'snowflake_ddl': res.snowflake_ddl,
               'transformations': res.transformations,
               'manual_review': res.manual_review,
           })
       }
   ```

2. Package and deploy via AWS CLI or Serverless Framework.

**Cost:** Free tier covers ~1M requests/month; then ~$0.20 per million requests.

---

## Option 6: Google Cloud Run

Lightweight, serverless, very simple Docker deployment.

### Steps

1. Ensure you have a `Dockerfile`
2. Authenticate with Google Cloud:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

3. Build and deploy:
   ```bash
   gcloud run deploy ddl-converter \
     --source . \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars CLAUDE_API_KEY="sk-your-key"
   ```

4. Google Cloud prints your public URL.

**Cost:** Free tier: 2M requests/month + 360k CPU-seconds; then ~$0.40 per million requests.

---

## Option 7: Azure Container Instances

Similar to Google Cloud Run; simple pay-as-you-go deployment.

```bash
az container create \
  --resource-group myResourceGroup \
  --name ddl-converter \
  --image YOUR_REGISTRY/ddl-converter \
  --environment-variables CLAUDE_API_KEY="sk-your-key" \
  --ports 8502
```

---

## Comparison Table

| Option | Ease | Cost | Public URL | Best For |
|--------|------|------|-----------|----------|
| **Streamlit Cloud** | ⭐⭐⭐⭐⭐ | Free (limited) | ✓ | Quick web demo, small teams |
| **Docker + Server** | ⭐⭐⭐ | $5–20/mo | ✓ | Private/internal deployment |
| **GitHub + CLI** | ⭐⭐ | Free | ✗ | Technical users, local use |
| **AWS Lambda** | ⭐⭐⭐⭐ | Free tier + pay-per-call | ✓ (via API Gateway) | APIs, serverless |
| **Google Cloud Run** | ⭐⭐⭐⭐ | Free tier + pay-per-call | ✓ | Serverless, simple |
| **Heroku** | ⭐⭐⭐⭐ | $5+/month | ✓ | Paid hobby apps |

---

## Sharing via Email / USB / Cloud Storage

For a one-off share without deployment:

1. **Zip the project:**
   ```bash
   zip -r ddl-converter.zip . -x "*.git*" "__pycache__/*" ".pytest*"
   ```

2. **Share via:**
   - Email attachment (if < 25 MB)
   - Google Drive / OneDrive / Dropbox
   - USB stick

3. **Recipient:**
   - Extract zip
   - Run `pip install -r requirements.txt`
   - Run `python cli.py` or `streamlit run streamlit_app.py`

---

## Security Considerations

### API Key Management

- **Never commit `CLAUDE_API_KEY` to Git.** Use `.env` file locally (in `.gitignore`) or environment variables on the server.
- On Streamlit Cloud / Docker, pass keys via environment variables or secrets manager.
- Rotate keys regularly; use separate keys for dev/test/prod.

### Public Deployments

- If hosting publicly, consider:
  - Rate limiting (via Streamlit Cloud settings or reverse proxy)
  - Authentication (add a login layer via Streamlit or nginx)
  - Input validation (already built into the converter, but double-check for edge cases)

### Private Deployments

- Docker on a private VPC or intranet
- Password-protect via HTTP Basic Auth (nginx reverse proxy)
- Use private GitHub repositories

---

## Next Steps

1. Choose an option above
2. Follow the setup steps
3. Test locally: `streamlit run streamlit_app.py`
4. Share the URL or code with your team

For questions, see the main [README.md](README.md).
