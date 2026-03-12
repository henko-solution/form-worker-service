#!/bin/bash

# 🚀 Script de Despliegue con Terraform Cloud
# Autor: Henko Form Worker Service
# Uso: ./scripts/deploy-terraform-cloud.sh [environment]

set -e

# Función de limpieza
cleanup() {
    log_info "🧹 Limpiando archivos temporales..."
    if [[ -d "lambda-layer" ]]; then
        rm -rf lambda-layer
    fi
    if [[ -d "lambda-code" ]]; then
        rm -rf lambda-code
    fi
    if [[ -f "requirements.txt" ]]; then
        rm -f requirements.txt
    fi
}

# Configurar trap para limpiar al salir
trap cleanup EXIT

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para logging
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Configuración (única fuente de verdad para Lambda)
PYTHON_VERSION="${LAMBDA_PYTHON_VERSION:-3.14}"

# Verificar argumentos
ENVIRONMENT=${1:-"qa"}
AUTO_APPLY=false
[[ "${2:-}" == "--yes" ]] && AUTO_APPLY=true
[[ -n "${TF_AUTO_APPLY:-}" ]] && AUTO_APPLY=true

if [[ ! "$ENVIRONMENT" =~ ^(qa|staging|prod)$ ]]; then
    log_error "Environment debe ser: qa, staging, o prod"
    exit 1
fi

log_info "🚀 Iniciando despliegue a $ENVIRONMENT con Terraform Cloud"

# Verificar que estamos en el directorio correcto
if [[ ! -f "pyproject.toml" ]]; then
    log_error "Debes ejecutar este script desde el directorio raíz del proyecto"
    exit 1
fi

# Verificar dependencias
log_info "🔍 Verificando dependencias..."

# Verificar Terraform
if ! command -v terraform &> /dev/null; then
    log_error "Terraform no está instalado. Instálalo desde: https://www.terraform.io/downloads"
    exit 1
fi

# Verificar GitHub CLI
if ! command -v gh &> /dev/null; then
    log_error "GitHub CLI no está instalado. Instálalo desde: https://cli.github.com/"
    exit 1
fi

# Verificar Docker (requerido para construir Lambda layer con Python 3.14)
if ! command -v docker &> /dev/null; then
    log_error "Docker no está instalado o no está en PATH. Necesario para construir el Lambda layer."
    exit 1
fi
if ! docker info &> /dev/null; then
    log_error "Docker no está en ejecución. Inicia Docker Desktop y vuelve a intentar."
    exit 1
fi

log_success "Dependencias verificadas"

# Configurar variables de entorno
log_info "⚙️  Configurando variables de entorno..."

# Contexto Terraform Cloud:
# - QA/Staging: org henko-solution, workspace form-worker-service-qa|form-worker-service-staging
#   (puede sobreescribirse vía TF_WORKSPACE_QA)
# - Prod: org huvantia-solution, workspace form-worker-service-prod
if [[ "$ENVIRONMENT" == "prod" ]]; then
    export TF_CLOUD_ORGANIZATION="${TF_CLOUD_ORGANIZATION_PROD:-huvantia-solution}"
    export TF_WORKSPACE="${TF_WORKSPACE_PROD:-form-worker-service-prod}"
else
    export TF_CLOUD_ORGANIZATION="${TF_CLOUD_ORGANIZATION_QA:-henko-solution}"
    # Para QA/Staging el workspace por defecto sigue el patrón
    # form-worker-service-{env} (por ejemplo: form-worker-service-qa),
    # a menos que se especifique explícitamente TF_WORKSPACE_QA.
    export TF_WORKSPACE="${TF_WORKSPACE_QA:-form-worker-service-${ENVIRONMENT}}"
fi

export TF_VAR_environment="${ENVIRONMENT}"

# Obtener variables desde GitHub CLI
log_info "📥 Obteniendo variables desde GitHub..."

# Variables de GitHub
export TF_VAR_aws_region=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="AWS_REGION") | .value' 2>/dev/null || echo "us-east-1")
export TF_VAR_form_service_url=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="FORM_SERVICE_URL") | .value' 2>/dev/null || echo "")
export TF_VAR_employee_service_url=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="EMPLOYEE_SERVICE_URL") | .value' 2>/dev/null || echo "")

# Cognito Configuration
export TF_VAR_cognito_user_pool_id=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="COGNITO_USER_POOL_ID") | .value' 2>/dev/null || echo "")
export TF_VAR_cognito_client_id=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="COGNITO_CLIENT_ID") | .value' 2>/dev/null || echo "")
export TF_VAR_cognito_client_secret=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="COGNITO_CLIENT_SECRET") | .value' 2>/dev/null || echo "")
export TF_VAR_cognito_client_secret_secret_name=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="COGNITO_CLIENT_SECRET_SECRET_NAME") | .value' 2>/dev/null || echo "")
export TF_VAR_cognito_system_username=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="COGNITO_SYSTEM_USERNAME") | .value' 2>/dev/null || echo "")
export TF_VAR_cognito_system_password=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="COGNITO_SYSTEM_PASSWORD") | .value' 2>/dev/null || echo "")
export TF_VAR_cognito_system_password_secret_name=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="COGNITO_SYSTEM_PASSWORD_SECRET_NAME") | .value' 2>/dev/null || echo "")

# Variables con valores por defecto
export TF_VAR_assignment_batch_size=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="ASSIGNMENT_BATCH_SIZE") | .value' 2>/dev/null || echo "100")
export TF_VAR_max_retries=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="MAX_RETRIES") | .value' 2>/dev/null || echo "3")
export TF_VAR_retry_delay_seconds=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="RETRY_DELAY_SECONDS") | .value' 2>/dev/null || echo "5")
export TF_VAR_log_level=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="LOG_LEVEL") | .value' 2>/dev/null || echo "INFO")
export TF_VAR_log_retention_days=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="LOG_RETENTION_DAYS") | .value' 2>/dev/null || echo "30")
export TF_VAR_sqs_batch_size=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="SQS_BATCH_SIZE") | .value' 2>/dev/null || echo "10")
export TF_VAR_sqs_maximum_batching_window=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="SQS_MAXIMUM_BATCHING_WINDOW") | .value' 2>/dev/null || echo "5")
export TF_VAR_candidate_form_names=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="CANDIDATE_FORM_NAMES") | .value' 2>/dev/null || echo "Huvantia Measure,Integridad,Valores Huvantia,Habilidades Cognitivas,Motivaciones,Liderazgo,Personalidad")
# Verificar variables requeridas
if [[ -z "$TF_VAR_form_service_url" ]]; then
    log_error "FORM_SERVICE_URL es requerido. Configúralo en GitHub Variables"
    exit 1
fi

if [[ -z "$TF_VAR_employee_service_url" ]]; then
    log_error "EMPLOYEE_SERVICE_URL es requerido. Configúralo en GitHub Variables"
    exit 1
fi

if [[ -z "$TF_VAR_cognito_user_pool_id" ]]; then
    log_error "COGNITO_USER_POOL_ID es requerido. Configúralo en GitHub Variables"
    exit 1
fi

if [[ -z "$TF_VAR_cognito_client_id" ]]; then
    log_error "COGNITO_CLIENT_ID es requerido. Configúralo en GitHub Variables"
    exit 1
fi

if [[ -z "$TF_VAR_cognito_system_username" ]]; then
    log_error "COGNITO_SYSTEM_USERNAME es requerido. Configúralo en GitHub Variables"
    exit 1
fi

if [[ -z "$TF_VAR_cognito_system_password" && -z "$TF_VAR_cognito_system_password_secret_name" ]]; then
    log_error "COGNITO_SYSTEM_PASSWORD es requerido. Configúralo en GitHub Variables"
    exit 1
fi

# Mostrar variables obtenidas para debugging
log_info "📋 Variables obtenidas desde GitHub:"
log_info "  AWS_REGION: $TF_VAR_aws_region"
log_info "  FORM_SERVICE_URL: $TF_VAR_form_service_url"
log_info "  EMPLOYEE_SERVICE_URL: $TF_VAR_employee_service_url"
log_info "  COGNITO_USER_POOL_ID: $TF_VAR_cognito_user_pool_id"
log_info "  COGNITO_CLIENT_ID: $TF_VAR_cognito_client_id"
log_info "  COGNITO_CLIENT_SECRET: [SET]"
log_info "  COGNITO_SYSTEM_USERNAME: $TF_VAR_cognito_system_username"
log_info "  COGNITO_SYSTEM_PASSWORD: [SET]"
log_info "  ASSIGNMENT_BATCH_SIZE: $TF_VAR_assignment_batch_size"
log_info "  MAX_RETRIES: $TF_VAR_max_retries"
log_info "  RETRY_DELAY_SECONDS: $TF_VAR_retry_delay_seconds"
log_info "  LOG_LEVEL: $TF_VAR_log_level"
log_info "  LOG_RETENTION_DAYS: $TF_VAR_log_retention_days"
log_info "  SQS_BATCH_SIZE: $TF_VAR_sqs_batch_size"
log_info "  SQS_MAXIMUM_BATCHING_WINDOW: $TF_VAR_sqs_maximum_batching_window"
log_info "  CANDIDATE_FORM_NAMES: $TF_VAR_candidate_form_names"

log_success "Variables configuradas para $ENVIRONMENT"

# Verificar autenticación de GitHub
log_info "🔐 Verificando autenticación de GitHub..."
if ! gh auth status &> /dev/null; then
    log_error "No estás autenticado en GitHub. Ejecuta: gh auth login"
    exit 1
fi

GITHUB_USER=$(gh api user --jq .login)
log_success "Autenticado en GitHub como: $GITHUB_USER"

# Verificar autenticación de Terraform Cloud
log_info "🔐 Verificando autenticación de Terraform Cloud..."
# TF_TOKEN_app_terraform_io es la variable estándar para Terraform Cloud
if [[ -z "$TF_API_TOKEN" && -z "$TF_TOKEN_app_terraform_io" ]]; then
    log_error "TF_API_TOKEN o TF_TOKEN_app_terraform_io no está configurado. Configúralo con:"
    log_error "export TF_TOKEN_app_terraform_io=tu_token_de_terraform_cloud"
    log_error "Obtén tu token en: https://app.terraform.io/app/settings/tokens"
    exit 1
fi
# Usar TF_TOKEN_app_terraform_io si TF_API_TOKEN no está configurado
if [[ -z "$TF_API_TOKEN" && -n "$TF_TOKEN_app_terraform_io" ]]; then
    export TF_API_TOKEN="$TF_TOKEN_app_terraform_io"
fi

# Configurar workspace para Terraform Cloud
log_info "🔍 Configurando workspace para Terraform Cloud..."
log_info "Workspace: $TF_WORKSPACE"
log_info "Organización: $TF_CLOUD_ORGANIZATION"

# Ejecutar validaciones locales
log_info "🔍 Ejecutando validaciones locales..."

# Verificar sintaxis de Terraform
log_info "📝 Verificando sintaxis de Terraform..."
cd terraform
terraform init
terraform validate
log_success "Sintaxis de Terraform válida"

# Verificar formato de Terraform
log_info "🎨 Verificando formato de Terraform..."
if ! terraform fmt -check -recursive; then
    log_warning "Formato de Terraform incorrecto. Aplicando formato..."
    terraform fmt -recursive
fi
log_success "Formato de Terraform correcto"

cd ..

# Crear archivos ZIP para Lambda
log_info "📦 Creando archivos ZIP para Lambda..."

# Directorio raíz del proyecto (permite ejecutar el script desde cualquier sitio)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Crear Lambda Layer con Docker (instalación nativa = compatibilidad con Lambda)
log_info "🐳 Construyendo Lambda Layer (Python ${PYTHON_VERSION}, imagen Lambda)..."
mkdir -p lambda-layer

# No actualizar pip: pip 26 rompe pip-tools (allow_all_prereleases). Ver: https://github.com/scikit-learn/scikit-learn/issues/33174
docker run --rm --platform linux/amd64 --entrypoint "" \
    -v "${PROJECT_ROOT}:/work" \
    -w /work \
    "public.ecr.aws/lambda/python:${PYTHON_VERSION}" \
    bash -c 'set -e
pip install -q pip-tools --root-user-action=ignore && pip-compile pyproject.toml -o requirements.txt
pip install -r requirements.txt -t lambda-layer/python --no-cache-dir --upgrade --root-user-action=ignore'

if [[ $? -ne 0 ]]; then
    log_error "Falló la construcción del Lambda layer en Docker"
    exit 1
fi

log_success "Lambda layer construido exitosamente"

# Limpiar archivos innecesarios del layer (en el host; la imagen Lambda no incluye find)
log_info "🧹 Limpiando archivos innecesarios del Lambda Layer..."
find lambda-layer/python -name "*.pyc" -delete 2>/dev/null || true
find lambda-layer/python -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Crear ZIP del layer
cd lambda-layer
zip -X -r ../lambda-layer.zip .
cd ..

# Crear Lambda Code Package
log_info "🔨 Creando Lambda Code Package..."
mkdir -p lambda-code

# Copiar código con exclusiones explícitas (evita .pyc, __pycache__, etc.)
log_info "📂 Copiando app/ con exclusiones..."
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' \
  --exclude='.mypy_cache' --exclude='.pytest_cache' --exclude='.git' \
  app/ lambda-code/app/
cp lambda_handler.py lambda-code/

# Limpieza adicional por si acaso
log_info "🧹 Limpiando archivos innecesarios del Lambda Code..."
find lambda-code -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find lambda-code -name "*.pyc" -delete 2>/dev/null || true
find lambda-code -name "*.pyo" -delete 2>/dev/null || true

# Crear ZIP del código
cd lambda-code
zip -X -r ../lambda-code.zip .
cd ..

# Verificar tamaños
log_info "📊 Tamaños de los archivos:"
ls -lh lambda-layer.zip lambda-code.zip

# Mover ZIPs a la carpeta terraform
log_info "📁 Moviendo archivos ZIP a la carpeta terraform..."
mv lambda-layer.zip terraform/
mv lambda-code.zip terraform/

log_success "Archivos ZIP creados y movidos exitosamente"

# Limpiar archivos temporales
log_info "🧹 Limpiando archivos temporales..."
rm -rf lambda-layer
rm -rf lambda-code
rm -f requirements.txt

# Plan de Terraform
log_info "📋 Ejecutando Terraform Plan..."
cd terraform

# Variables específicas para el plan
PLAN_ARGS=(
    "-var=environment=$ENVIRONMENT"
    "-var=aws_region=$TF_VAR_aws_region"
    "-var=form_service_url=$TF_VAR_form_service_url"
    "-var=employee_service_url=$TF_VAR_employee_service_url"
    "-var=cognito_user_pool_id=$TF_VAR_cognito_user_pool_id"
    "-var=cognito_client_id=$TF_VAR_cognito_client_id"
    "-var=cognito_client_secret=$TF_VAR_cognito_client_secret"
    "-var=cognito_client_secret_secret_name=${TF_VAR_cognito_client_secret_secret_name:-}"
    "-var=cognito_system_username=$TF_VAR_cognito_system_username"
    "-var=cognito_system_password=$TF_VAR_cognito_system_password"
    "-var=cognito_system_password_secret_name=${TF_VAR_cognito_system_password_secret_name:-}"
    "-var=assignment_batch_size=$TF_VAR_assignment_batch_size"
    "-var=max_retries=$TF_VAR_max_retries"
    "-var=retry_delay_seconds=$TF_VAR_retry_delay_seconds"
    "-var=log_level=$TF_VAR_log_level"
    "-var=log_retention_days=$TF_VAR_log_retention_days"
    "-var=sqs_batch_size=$TF_VAR_sqs_batch_size"
    "-var=sqs_maximum_batching_window=$TF_VAR_sqs_maximum_batching_window"
    "-var=lambda_filename=lambda-code.zip"
)

terraform plan "${PLAN_ARGS[@]}" -out=tfplan

if [[ $? -ne 0 ]]; then
    log_error "Terraform plan falló"
    exit 1
fi

log_success "Plan de Terraform generado exitosamente"

# Confirmar despliegue (omitir con --yes o TF_AUTO_APPLY=1)
if [[ "$AUTO_APPLY" != "true" ]]; then
    echo ""
    log_warning "🚨 ¿Estás seguro de que quieres desplegar a $ENVIRONMENT?"
    log_warning "Esto puede tomar varios minutos y puede incurrir en costos de AWS."
    echo ""
    read -p "Escribe 'yes' para continuar: " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_info "Despliegue cancelado"
        exit 0
    fi
fi

# Aplicar cambios
log_info "🚀 Aplicando cambios con Terraform..."
terraform apply tfplan

if [[ $? -ne 0 ]]; then
    log_error "Terraform apply falló"
    exit 1
fi

cd ..

# Obtener outputs
log_info "📊 Obteniendo outputs del despliegue..."
cd terraform
terraform output -json > ../terraform-outputs.json
cd ..

# Mostrar información del despliegue
log_success "🎉 ¡Despliegue completado exitosamente!"

# Mostrar outputs importantes
if [[ -f "terraform-outputs.json" ]]; then
    log_info "📋 Información del despliegue:"

    # Extraer información relevante
    LAMBDA_FUNCTION=$(python3 -c "import json; data=json.load(open('terraform-outputs.json')); print(data.get('lambda_function_name', {}).get('value', 'N/A'))")
    SQS_QUEUE_URL=$(python3 -c "import json; data=json.load(open('terraform-outputs.json')); print(data.get('sqs_queue_url', {}).get('value', 'N/A'))")
    SQS_QUEUE_ARN=$(python3 -c "import json; data=json.load(open('terraform-outputs.json')); print(data.get('sqs_queue_arn', {}).get('value', 'N/A'))")
    SQS_DLQ_URL=$(python3 -c "import json; data=json.load(open('terraform-outputs.json')); print(data.get('sqs_dlq_url', {}).get('value', 'N/A'))")

    echo ""
    echo "🔧 Lambda Function: $LAMBDA_FUNCTION"
    echo "📬 SQS Queue URL: $SQS_QUEUE_URL"
    echo "📬 SQS Queue ARN: $SQS_QUEUE_ARN"
    echo "📬 SQS DLQ URL: $SQS_DLQ_URL"
    echo ""

    # Guardar información en archivo
    cat > "deployment-info-${ENVIRONMENT}.txt" << EOF
Despliegue completado: $(date)
Environment: $ENVIRONMENT
Lambda Function: $LAMBDA_FUNCTION
SQS Queue URL: $SQS_QUEUE_URL
SQS Queue ARN: $SQS_QUEUE_ARN
SQS DLQ URL: $SQS_DLQ_URL
EOF

    log_success "Información guardada en deployment-info-${ENVIRONMENT}.txt"
fi

log_success "🎯 Despliegue completado. ¡Tu worker está listo!"
