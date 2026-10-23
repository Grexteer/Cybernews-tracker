# CyberNews Tracker

Flask-Website für Cybersecurity-News (Kursprojekt).

## Starten
1. Eine Datei `.env` anlegen (Vorlage: `.env.example`) und den eigenen Key von https://newsapi.org eintragen.
2. `.venv\Scripts\python web_app.py` ausführen und http://127.0.0.1:5000 öffnen (Debug-Modus nur mit `FLASK_DEBUG=1`).

Beim ersten Start wird `data/cybernews.db` (SQLite) angelegt, mit zwei Demo-Accounts:
`alice / alicepass` (user), `bob / bobpass` (admin).
Die Artikel werden dabei automatisch von der NewsAPI importiert (im Admin-Dashboard geht das auch per Knopf).

## Funktionen
- Startseite mit Featured- und Latest-Artikeln, Artikelseiten, About, Kontaktformular
- News-Seite: Suche, Kategorie- und Quellenfilter (per fetch() von `/api/articles`), Live-Feed (NewsAPI, Fallback lokal)
- Registrierung, Login mit serverseitigen Sessions (HttpOnly, SameSite), Rollen user/admin
- Admin-Dashboard: Artikel anlegen/bearbeiten/löschen, News-Import, Sessions, Accounts, Login-Audit-Log, Kontaktnachrichten

## Sicherheit
- Passwort-Hashing (Werkzeug), parametrisierte SQL-Queries, Jinja-Autoescaping, `textContent` im JS
- CSRF-Token (Double-Submit-Cookie) auf allen POSTs, Sperre nach 5 Fehllogins pro IP in 5 Min
- Rolle kommt immer vom Server, CSP und weitere Security-Header, Eingabevalidierung
