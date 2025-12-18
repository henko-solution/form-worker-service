# =============================================================================
# Henko Form Worker Service - Makefile
# =============================================================================
#
# Comandos de desarrollo para el worker service.
# Proporciona acceso rápido a las funciones más comunes.
#
# Uso: make [target]
# =============================================================================

.PHONY: help setup install test test-unit test-integration quality lint format clean pre-commit-install pre-commit-run pre-commit-update

# Variables
PYTHON = python3
PIP = pip3

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

setup: ## Configura el entorno de desarrollo
	$(call print_status,Configurando entorno de desarrollo...)
	$(PYTHON) -m venv .venv || true
	$(call print_status,Instalando dependencias...)
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[local,test,all]"
	$(call print_status,Instalando pre-commit hooks...)
	@.venv/bin/pre-commit install || $(call print_warning,Pre-commit no disponible, instalando...)
	@if command -v pre-commit > /dev/null 2>&1; then \
		pre-commit install; \
	else \
		.venv/bin/pip install pre-commit; \
		.venv/bin/pre-commit install; \
	fi
	$(call print_success,Entorno configurado correctamente)
	@echo ""
	@echo "$(YELLOW)⚠️  No olvides copiar env.example a .env y configurar las variables$(NC)"

install: ## Instala las dependencias
	$(call print_status,Instalando dependencias...)
	$(PIP) install -e ".[local,test,all]"
	$(call print_success,Dependencias instaladas)

test: ## Ejecuta todos los tests
	$(call print_status,Ejecutando tests...)
	pytest tests/ -v
	$(call print_success,Tests completados)

test-unit: ## Ejecuta solo los tests unitarios
	$(call print_status,Ejecutando tests unitarios...)
	pytest tests/unit/ -v
	$(call print_success,Tests unitarios completados)

test-integration: ## Ejecuta solo los tests de integración
	$(call print_status,Ejecutando tests de integración...)
	pytest tests/integration/ -v
	$(call print_success,Tests de integración completados)

test-coverage: ## Ejecuta tests con cobertura
	$(call print_status,Ejecutando tests con cobertura...)
	pytest tests/ --cov=app --cov-report=html --cov-report=term
	$(call print_success,Cobertura generada en htmlcov/index.html)

quality: lint format pre-commit-run ## Ejecuta todas las verificaciones de calidad
	$(call print_success,Verificaciones de calidad completadas)

lint: ## Ejecuta linters (flake8, mypy, bandit)
	$(call print_status,Ejecutando linters...)
	flake8 app tests
	mypy app
	bandit -r app
	$(call print_success,Linters completados)

format: ## Formatea el código (black, isort)
	$(call print_status,Formateando código...)
	black app tests
	isort app tests
	$(call print_success,Código formateado)

format-check: ## Verifica el formato sin modificar
	$(call print_status,Verificando formato...)
	black --check app tests
	isort --check app tests
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
	@pre-commit install
	$(call print_success,Pre-commit hooks instalados)

pre-commit-run: ## Ejecuta pre-commit en todos los archivos
	$(call print_status,Ejecutando pre-commit en todos los archivos...)
	@pre-commit run --all-files
	$(call print_success,Pre-commit completado)

pre-commit-update: ## Actualiza pre-commit hooks
	$(call print_status,Actualizando pre-commit hooks...)
	@pre-commit autoupdate
	$(call print_success,Pre-commit hooks actualizados)
