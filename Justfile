# ==============================================================================
# LiBros - Library Management System (FH Salzburg SWD)
# Automatisierung mit just & uv
# ==============================================================================

set dotenv-load := true

# Zeigt alle verfügbaren Befehle an
default:
    @just --list

# Virtuelle Umgebung erstellen und Abhängigkeiten via uv synchronisieren
install:
    uv sync

# Abhängigkeiten inklusive PostgreSQL-Treiber installieren (Marcel)
install-postgres:
    uv sync --extra postgres

# Django-Entwicklungsserver starten
run:
    uv run python manage.py runserver

# Django-Entwicklungsserver auf speziellem Port starten (z. B. just run-port 8080)
run-port port="8000":
    uv run python manage.py runserver {{port}}

# Datenbank-Migrationen anwenden (SQL-Schema initialisieren/aktualisieren)
migrate:
    uv run python manage.py migrate

# Neue Migrationen für Modelle erstellen (z. B. just makemigrations core)
makemigrations app="":
    uv run python manage.py makemigrations {{app}}

# Initiale Test- und Stammdaten (Medien, Exemplare, Kunden) einspielen
seed:
    uv run python manage.py seed_data

# Automatisierte Unit-Tests ausführen
test:
    uv run python manage.py test

# Bestimmte Test-Suite ausführen (z. B. just test-app loans)
test-app app:
    uv run python manage.py test apps.{{app}}

# Django System-Checks durchführen
check:
    uv run python manage.py check

# Interaktive Django-Shell öffnen
shell:
    uv run python manage.py shell

# Django Superuser für Admin-Zugang erstellen
createsuperuser:
    uv run python manage.py createsuperuser

# Bereinigt temporäre Dateien, Cache und Bytecode
clean:
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
