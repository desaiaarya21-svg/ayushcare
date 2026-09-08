# Ayush Patient Case-Taking Software (MVP)
SIH26047 - Ministry of Ayush

## How to run
1. Install Python 3.8+ if not already installed.
2. Open a terminal in this folder.
3. Install Flask:
      pip install -r requirements.txt
4. Run the app:
      python app.py
5. Open your browser at: http://127.0.0.1:5000
6. Login PIN: 1234 (change DEFAULT_PIN in app.py)

## What's included
- Offline PIN login (no internet needed to run the app)
- Patient registration with auto-generated Patient Code (e.g. AYU0001)
- QR code shown on each patient's profile (generated in-browser)
- Patient list with search
- Tabbed case-taking form: Chief Complaints, Medical History, Medicines,
  Prakriti/Dosha, Nidan Panchak, Diagnosis
- Patient history timeline + Digital Medical Report view
- Dashboard with total patients and today's case count

## Database
Uses SQLite (ayush.db) - a single local file, created automatically the
first time you run the app. No external database setup needed.

## Notes for your team
- app.py contains all backend routes/logic - read the comments, it's built
  to be easy to extend.
- templates/ folder has one HTML file per screen.
- static/css/style.css has all the styling - change colors/branding here.
- To add a new field to the case-taking form: add the input in
  templates/case_form.html, then add the matching column in the
  case_records table in app.py (init_db function) and in the INSERT
  statement inside new_case().
