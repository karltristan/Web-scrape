Starlink Usage Tracker
A Flask web app that parses Starlink saved HTML pages and visualizes daily data usage.
Setup

Install dependencies:

bash   pip install -r requirements.txt

Run the app:

bash python app.py

Open your browser at:

http://localhost:5000
How to use

Save your Starlink usage pages as HTML (Ctrl+S in browser)
Upload them via the web UI (drag & drop or click to browse)
Click Parse Usage Data
View daily chart, monthly totals, and full table
Click Export CSV to download the data

File naming
The app auto-detects the month from the filename, e.g.:

Nov-December.html → starts at November 2025
Jan-Feb.html      → starts at January 2026
april-may.html    → starts at April 2026

Folder structure
starlink_scraper/
├── app.py
├── requirements.txt
├── templates/
│   └── index.html
└── uploads/       ← auto-created on first run
