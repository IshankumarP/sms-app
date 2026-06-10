# Bulk SMS Sender

A simple web UI that sends bulk SMS using your Android phone's SIM via SMSGate.

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000 in your browser.

## Deploy to Railway (free, permanent link)

1. Push this folder to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub
3. Select your repo — Railway auto-detects Python
4. Add a start command:  `gunicorn app:app`
5. Deploy — Railway gives you a public URL like `https://your-app.up.railway.app`
6. Share that link with anyone who needs to send SMS

## CSV Format

Your CSV file must have a column named `phone`:

```
phone
9876543210
8765432109
+917654321098
```

Numbers without a country code get +91 (India) added automatically.

## How it works

1. User opens the web page
2. Enters their SMSGate cloud credentials (from the app on their phone)
3. Uploads a CSV of phone numbers
4. Types their message
5. Hits Send — the backend loops through numbers and calls SMSGate's cloud API
6. SMSGate cloud relays each message to their phone
7. Their phone sends it as a regular SMS via their SIM
