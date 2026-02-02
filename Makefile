# =============================================================================
# Henko Form Worker Service - Makefile
# =============================================================================
#
# Comandos de desarrollo para el worker service.
# Proporciona acceso rápido a las funciones más comunes.
#
# Uso: make [target]
# =============================================================================

.PHONY: help setup install quality lint format clean pre-commit-install pre-commit-run pre-commit-update

# Variables
PYTHON_VENV ?= python3.14
VENV_DIR = .venv
PYTHON = $(VENV_DIR)/bin/python
PIP = $(VENV_DIR)/bin/pip

# Colores para output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

# Función para imprimir mensajes
define print_status
	@echo "$(BLUE)🔧 $(1)$(NC)"
endef

define print_success
	@echo "$(GREEN)✅ $(1)$(NC)"
endef

define print_warning
	@echo "$(YELLOW)⚠️  $(1)$(NC)"
endef

define print_error
	@echo "$(RED)❌ $(1)$(NC)"
endef

# Target por defecto
help: ## Muestra esta ayuda
	@echo "Henko Form Worker Service - Comandos Disponibles"
	@echo "=============================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

venv: ## Crea .venv para ambiente host (solo pre-commit; los hooks se instalan aislados por pre-commit)
	$(call print_status,Creando venv con $(PYTHON_VENV)...)
	@command -v $(PYTHON_VENV) >/dev/null 2>&1 || { echo "$(RED)❌ $(PYTHON_VENV) no encontrado. Instálalo (ej. brew install python@3.14) o define PYTHON_VENV.$(NC)"; exit 1; }
	@$(PYTHON_VENV) -m venv $(VENV_DIR)
	$(call print_status,Instalando deps de host (solo pre-commit)...)
	@$(PIP) install -q -e ".[dev]"
	$(call print_success,Venv creado en $(VENV_DIR))
	@echo ""
	@echo "  Activar: source $(VENV_DIR)/bin/activate"
	@echo "  Luego:   pre-commit run --all-files   (o make pre-commit-run)"
	@echo ""

setup: venv ## Configura el entorno de desarrollo (venv + pre-commit)
	$(call print_status,Instalando pre-commit hooks...)
	@$(VENV_DIR)/bin/pre-commit install || $(call print_warning,Pre-commit no disponible)
	$(call print_success,Entorno configurado correctamente)
	@echo ""
	@echo "$(YELLOW)⚠️  No olvides copiar env.example a .env y configurar las variables$(NC)"

install: ## Instala las dependencias en el venv actual
	$(call print_status,Instalando dependencias...)
	$(PIP) install -e ".[local,all]"
	$(call print_success,Dependencias instaladas)

quality: pre-commit-run ## Ejecuta todas las verificaciones de calidad (pre-commit)
	$(call print_success,Verificaciones de calidad completadas)

lint: ## Ejecuta linters vía pre-commit
	$(call print_status,Ejecutando linters...)
	@pre-commit run flake8 --all-files
	@pre-commit run mypy --all-files
	@pre-commit run bandit --all-files
	$(call print_success,Linters completados)

format: ## Formatea el código vía pre-commit (black, isort)
	$(call print_status,Formateando código...)
	@pre-commit run black --all-files
	@pre-commit run isort --all-files
	$(call print_success,Código formateado)

format-check: ## Verifica el formato sin modificar
	$(call print_status,Verificando formato...)
	@$(PYTHON) -m black --check app lambda_handler.py 2>/dev/null || black --check app lambda_handler.py
	@$(PYTHON) -m isort --check app lambda_handler.py 2>/dev/null || isort --check app lambda_handler.py
	$(call print_success,Formato verificado)

clean: ## Limpia archivos temporales
	$(call print_status,Limpieza de archivos temporales...)
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -r {} + 2>/dev/null || true
	rm -f .coverage coverage.xml
	$(call print_success,Limpieza completada)

clean-all: clean ## Limpia todo incluyendo venv
	$(call print_status,Limpieza completa...)
	rm -rf .venv
	$(call print_success,Limpieza completa finalizada)

.PHONY: check-env
check-env: ## Verifica que las variables de entorno estén configuradas
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)⚠️  Archivo .env no encontrado$(NC)"; \
		echo "Copia env.example a .env y configura las variables"; \
		exit 1; \
	fi
	$(call print_success,Archivo .env encontrado)

# Pre-commit hooks
pre-commit-install: ## Instala pre-commit hooks
	$(call print_status,Instalando pre-commit hooks...)
	@$(VENV_DIR)/bin/pre-commit install 2>/dev/null || pre-commit install
	$(call print_success,Pre-commit hooks instalados)

pre-commit-run: ## Ejecuta pre-commit en todos los archivos
	$(call print_status,Ejecutando pre-commit en todos los archivos...)
	@pre-commit run --all-files
	$(call print_success,Pre-commit completado)

pre-commit-update: ## Actualiza pre-commit hooks
	$(call print_status,Actualizando pre-commit hooks...)
	@pre-commit autoupdate
	$(call print_success,Pre-commit hooks actualizados)
