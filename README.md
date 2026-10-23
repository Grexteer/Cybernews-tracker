# CyberNews Tracker

Flask-Website fuer Cybersecurity-News (Kursprojekt).

Start: `.venv\Scripts\python web_app.py` -> http://127.0.0.1:5000  (Debug nur mit `FLASK_DEBUG=1`)

Beim ersten Start wird `data/cybernews.db` (SQLite) mit Demo-Artikeln und Demo-Accounts angelegt:
`alice / alicepass` (user), `bob / bobpass` (admin).

## Funktionen
- Startseite mit Featured- und Latest-Artikeln, Artikelseiten, About, Kontaktformular
- News-Seite: Suche, Kategorie- und Quellenfilter (per fetch() von `/api/articles`), Live-Feed (NewsAPI, Fallback lokal)
- Registrierung, Login mit serverseitigen Sessions (HttpOnly, SameSite), Rollen user/admin
- Admin-Dashboard: Artikel anlegen/bearbeiten/loeschen, Sessions, Accounts, Login-Audit-Log, Kontaktnachrichten

## Sicherheit
- Passwort-Hashing (Werkzeug), parametrisierte SQL-Queries, Jinja-Autoescaping, `textContent` im JS
- CSRF-Token (Double-Submit-Cookie) auf allen POSTs, Sperre nach 5 Fehllogins pro IP in 5 Min
- Rolle kommt immer vom Server, CSP und weitere Security-Header, Eingabevalidierung
