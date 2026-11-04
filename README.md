# ITS-B-SWD-Library: LiBros Bibliothekssystem

Software Design - Lab Projekt (Fachhochschule Salzburg GmbH)  
Technologie-Stack: **Python 3.12+, Django 6, uv, just**  
Architektur: **Client-Server-Architektur mit Schichtenmodell**

---

## 👥 Team & Aufgabenverteilung

| Rolle | Teammitglied | Zuständigkeit |
| :--- | :--- | :--- |
| **1. Autor** | **Alexander Graf** | Base-Setup & **Use Case 1: Medium ausleihen (Loan)** (Web-App / Kiosk) |
| **2. Autor** | **David Leberbauer** | **Use Case 2: Medium zurückgeben (Return)** (Rückgabestation Hardware-Simulation) |
| **3. Autor** | **Marcel Kitzmantel** | **Use Case 3: Medium reservieren (Reservation)** & **SQL-Datenbankanbindung** |

---

## 🛠️ Voraussetzungen & Tooling

Das Projekt verwendet modernstes Python-Tooling:
- [**uv**](https://github.com/astral-sh/uv) – Extrem schneller Python-Paket- & Projektmanager von Astral.
- [**just**](https://github.com/casey/just) – Moderner Command-Runner zur einfachen Ausführung aller Workflows.

### Installation der Tools (falls noch nicht vorhanden):

**macOS (mit Homebrew):**
```bash
brew install uv just
```

**Linux / macOS (Standalone):**
```bash
# uv installieren
curl -LsSf https://astral.sh/uv/install.sh | sh

# just installieren
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin
```

---

## 🚀 Schnelleinstieg mit `just`

Mit `just` lassen sich alle Entwicklungs- und Testschritte mit Einzeilern ausführen:

```bash
# 1. Alle verfügbaren Befehle anzeigen
just

# 2. Virtuelle Umgebung erstellen und Abhängigkeiten synchronisieren
just install

# 3. Datenbank-Migrationen ausführen (SQL-Schema aufbauen)
just migrate

# 4. Initiale Stammdaten (Medien, Fächer, Kunden) laden
just seed

# 5. Django-Entwicklungsserver starten
just run

# 6. Automatisierte Tests ausführen
just test
```

### Übersicht aller `just`-Befehle

| Befehl | Beschreibung | Entsprechender Befehl |
| :--- | :--- | :--- |
| `just` | Zeigt alle verfügbaren Befehle an | `just --list` |
| `just install` | Installiert alle Abhängigkeiten via `uv` | `uv sync` |
| `just install-postgres` | Installiert Abhängigkeiten inkl. PostgreSQL-Treiber | `uv sync --extra postgres` |
| `just migrate` | Wendet Datenbank-Migrationen an | `uv run python manage.py migrate` |
| `just makemigrations [app]` | Erstellt neue Migrationsdateien | `uv run python manage.py makemigrations` |
| `just seed` | Lädt Stammdaten & Exemplare für Demos/Tests | `uv run python manage.py seed_data` |
| `just run` | Startet den Entwicklungsserver auf Port 8000 | `uv run python manage.py runserver` |
| `just run-port 8080` | Startet Server auf bestimmtem Port | `uv run python manage.py runserver 8080` |
| `just test` | Führt alle Unit-Tests aus | `uv run python manage.py test` |
| `just test-app loans` | Führt Tests für eine bestimmte App aus | `uv run python manage.py test apps.loans` |
| `just check` | Führt Django-Systemprüfungen durch | `uv run python manage.py check` |
| `just shell` | Öffnet eine interaktive Django-Shell | `uv run python manage.py shell` |
| `just createsuperuser` | Erstellt einen Admin-Benutzer | `uv run python manage.py createsuperuser` |
| `just clean` | Bereinigt Cache und `__pycache__` | `find . -type d -name ...` |

---

## 💻 Alternative: Direkte Ausführung mit `uv`

Falls `just` nicht verwendet wird, können alle Befehle direkt mit `uv` ausgeführt werden:

```bash
# Projekt synchronisieren (erstellt automatisch .venv)
uv sync

# Migrationen anwenden
uv run python manage.py migrate

# Stammdaten generieren
uv run python manage.py seed_data

# Server starten
uv run python manage.py runserver

# Tests ausführen
uv run python manage.py test
```

---

## 🗄️ SQL-Datenbankanbindung (Marcel Kitzmantel)

Das Projekt besitzt eine vollständige relationale SQL-Anbindung:

1. **Standardmäßig (SQLite):**
   - Vorkonfiguriert über `django.db.backends.sqlite3` in `db.sqlite3`.
   - Läuft sofort lokal ohne jegliche Konfiguration oder externe Serverdienste.

2. **Produktiv / PostgreSQL / MySQL:**
   - Kopiere [`.env.example`](.env.example) nach `.env` und passe die Werte an:
     ```bash
     DB_ENGINE=postgresql
     DB_NAME=libros_db
     DB_USER=libros_user
     DB_PASSWORD=secret_password
     DB_HOST=localhost
     DB_PORT=5432
     ```
   - Installiere den PostgreSQL-Treiber:
     ```bash
     just install-postgres
     # bzw.:
     uv sync --extra postgres
     ```

---

## 📂 Projekt- & Datei-Struktur

```text
ITS-B-SWD-Library/
├── pyproject.toml                   # uv-Projekt- und Abhängigkeitskonfiguration
├── Justfile                         # just-Automatisierungsbefehle
├── requirements.txt                 # Fallback-Abhängigkeiten (pip)
├── .env.example                     # Vorlage für DB- & Umgebungskonfiguration
├── manage.py
├── db.sqlite3                       # SQL-Datenbank
│
├── libros_project/                  # Django-Projektkonfiguration
│   ├── settings.py                  # Settings inkl. SQL-Datenbankanbindung
│   ├── urls.py                      # Root URL Routing
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   ├── core/                        # Persistence Layer & Stammdaten
│   │   ├── models.py                # Relationales Datenmodell (Klassendiagramm)
│   │   ├── admin.py                 # Django Admin-Registrierung
│   │   ├── concurrency.py           # Concurrency & Lock Manager (IConcurrencyLock)
│   │   ├── policies.py              # Rule & Policy Engine (FSK, Gebühren, Fristen)
│   │   ├── repositories.py          # Master Data & Transaction Repositories
│   │   └── management/commands/
│   │       └── seed_data.py         # Seed Data für Test- & Demozwecke
│   │
│   ├── loans/                       # USE CASE 1: Medium ausleihen (Alex)
│   │   ├── loan_service.py          # ILoanService (Geschäftslogik)
│   │   ├── views.py                 # Web & Kiosk Controller
│   │   ├── urls.py                  # URL-Routen
│   │   ├── forms.py                 # Formulare & Eingaben
│   │   ├── tests.py                 # Automatisierte Unit-Tests
│   │   └── templates/loans/
│   │       └── loan_form.html       # Web/Kiosk Template
│   │
│   ├── returns/                     # USE CASE 2: Medium zurückgeben (David)
│   │   ├── return_service.py        # IReturnService (Geschäftslogik)
│   │   ├── views.py                 # Return Station API & Views
│   │   ├── urls.py                  # URL-Routen
│   │   ├── forms.py                 # Barcode-Scan / Formulare
│   │   ├── tests.py                 # Automatisierte Unit-Tests
│   │   └── templates/returns/
│   │       └── return_station.html  # Rückgabestation HTML-Simulation
│   │
│   └── reservations/                # USE CASE 3: Medium reservieren (Marcel)
│       ├── reservation_service.py   # IReservationService (Geschäftslogik)
│       ├── views.py                 # Web Controller
│       ├── urls.py                  # URL-Routen
│       ├── forms.py                 # Zeitintervall / Formulare
│       ├── tests.py                 # Automatisierte Unit-Tests
│       └── templates/reservations/
│           └── reservation_form.html# Reservierungs-Template
│
└── templates/                       # Globale Web-Templates
    ├── base.html                    # Bootstrap 5 Basis-Template
    └── index.html                   # Startseite
```
