#!/bin/bash

# 🚀 Script de Despliegue con Terraform Cloud
# Autor: Henko Form Worker Service
# Uso: ./scripts/deploy-terraform-cloud.sh [environment]

set -e

# Función de limpieza
cleanup() {
    log_info "🧹 Limpiando archivos temporales..."
    if [[ -d ".temp-venv" ]]; then
        rm -rf .temp-venv
    fi
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

# Verificar argumentos
ENVIRONMENT=${1:-"qa"}
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

# Verificar Python
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 no está instalado"
    exit 1
fi

log_success "Dependencias verificadas"

# Configurar variables de entorno
log_info "⚙️  Configurando variables de entorno..."

export TF_CLOUD_ORGANIZATION="henko-solution"
export TF_WORKSPACE="form-worker-service-${ENVIRONMENT}"
export TF_VAR_environment="${ENVIRONMENT}"

# Obtener variables desde GitHub CLI
log_info "📥 Obteniendo variables desde GitHub..."

# Variables de GitHub
export TF_VAR_aws_region=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="AWS_REGION") | .value' 2>/dev/null || echo "us-east-1")
export TF_VAR_form_service_url=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="FORM_SERVICE_URL") | .value' 2>/dev/null || echo "")
export TF_VAR_employee_service_url=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="EMPLOYEE_SERVICE_URL") | .value' 2>/dev/null || echo "")

# Variables con valores por defecto
export TF_VAR_assignment_batch_size=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="ASSIGNMENT_BATCH_SIZE") | .value' 2>/dev/null || echo "100")
export TF_VAR_max_retries=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="MAX_RETRIES") | .value' 2>/dev/null || echo "3")
export TF_VAR_retry_delay_seconds=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="RETRY_DELAY_SECONDS") | .value' 2>/dev/null || echo "5")
export TF_VAR_log_level=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="LOG_LEVEL") | .value' 2>/dev/null || echo "INFO")
export TF_VAR_log_retention_days=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="LOG_RETENTION_DAYS") | .value' 2>/dev/null || echo "30")
export TF_VAR_sqs_batch_size=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="SQS_BATCH_SIZE") | .value' 2>/dev/null || echo "10")
export TF_VAR_sqs_maximum_batching_window=$(gh variable list --repo henko-solution/form-worker-service --json name,value --jq '.[] | select(.name=="SQS_MAXIMUM_BATCHING_WINDOW") | .value' 2>/dev/null || echo "5")

# Verificar variables requeridas
if [[ -z "$TF_VAR_form_service_url" ]]; then
    log_error "FORM_SERVICE_URL es requerido. Configúralo en GitHub Variables"
    exit 1
fi

if [[ -z "$TF_VAR_employee_service_url" ]]; then
    log_error "EMPLOYEE_SERVICE_URL es requerido. Configúralo en GitHub Variables"
    exit 1
fi

# Mostrar variables obtenidas para debugging
log_info "📋 Variables obtenidas desde GitHub:"
log_info "  AWS_REGION: $TF_VAR_aws_region"
log_info "  FORM_SERVICE_URL: $TF_VAR_form_service_url"
log_info "  EMPLOYEE_SERVICE_URL: $TF_VAR_employee_service_url"
log_info "  ASSIGNMENT_BATCH_SIZE: $TF_VAR_assignment_batch_size"
log_info "  MAX_RETRIES: $TF_VAR_max_retries"
log_info "  RETRY_DELAY_SECONDS: $TF_VAR_retry_delay_seconds"
log_info "  LOG_LEVEL: $TF_VAR_log_level"
log_info "  LOG_RETENTION_DAYS: $TF_VAR_log_retention_days"
log_info "  SQS_BATCH_SIZE: $TF_VAR_sqs_batch_size"
log_info "  SQS_MAXIMUM_BATCHING_WINDOW: $TF_VAR_sqs_maximum_batching_window"

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
if [[ -z "$TF_API_TOKEN" ]]; then
    log_error "TF_API_TOKEN no está configurado. Configúralo con:"
    log_error "export TF_API_TOKEN=tu_token_de_terraform_cloud"
    log_error "Obtén tu token en: https://app.terraform.io/app/settings/tokens"
    exit 1
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

# Crear ambiente virtual temporal
log_info "🐍 Creando ambiente virtual temporal..."

# Try to use Python 3.13 if available (compatibility with pip-tools)
if command -v python3.13 &> /dev/null; then
    PYTHON_CMD=python3.13
    log_info "Using Python 3.13 for pip-compile compatibility"
elif command -v python3.12 &> /dev/null; then
    PYTHON_CMD=python3.12
    log_info "Using Python 3.12 for pip-compile compatibility"
else
    PYTHON_CMD=python3
    log_info "Using default Python 3 (may have compatibility issues with pip-tools)"
fi

$PYTHON_CMD -m venv .temp-venv
source .temp-venv/bin/activate

# Crear Lambda Layer
log_info "🔨 Creando Lambda Layer..."
mkdir -p lambda-layer/python

# Instalar dependencias para el layer
# Use compatible versions to avoid pip-tools compatibility issues with Python 3.13+
python -m pip install --upgrade "pip<25.0" "setuptools<70" wheel
python -m pip install pip-tools

# Generar requirements.txt para el layer
log_info "📋 Generando requirements.txt para Lambda Layer..."
pip-compile pyproject.toml --output-file requirements.txt

# Actualizar pip a la última versión antes de instalar dependencias
log_info "🔄 Actualizando pip a la última versión..."
python -m pip install --upgrade pip

# Instalar dependencias en el layer
log_info "📥 Instalando dependencias en Lambda Layer..."
python -m pip install \
    --platform manylinux2014_x86_64 \
    --target=lambda-layer/python \
    --implementation cp \
    --python-version 3.13 \
    --only-binary=:all: \
    --upgrade \
    -r requirements.txt

# Limpiar archivos innecesarios del layer
log_info "🧹 Limpiando archivos innecesarios del Lambda Layer..."
# No necesitamos limpiar uvicorn, websockets, etc. porque este worker no los usa
# Pero podemos limpiar archivos Python compilados
find lambda-layer/python -name "*.pyc" -delete
find lambda-layer/python -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Crear ZIP del layer
cd lambda-layer
zip -X -r ../lambda-layer.zip .
cd ..

# Crear Lambda Code Package
log_info "🔨 Creando Lambda Code Package..."
mkdir -p lambda-code

# Copiar archivos del código con la estructura correcta
cp -r app/ lambda-code/app/
cp lambda_handler.py lambda-code/ 2>/dev/null || true

# Limpiar archivos innecesarios del código
log_info "🧹 Limpiando archivos innecesarios del Lambda Code..."
find lambda-code -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find lambda-code -name "*.pyc" -delete 2>/dev/null || true

# Crear ZIP del código
cd lambda-code
zip -X -r ../lambda-code.zip .
cd ..

# Verificar tamaños
log_info "📊 Tamaños de los archivos:"
ls -lh lambda-layer.zip lambda-code.zip 2>/dev/null || true

# Mover ZIPs a la carpeta terraform
log_info "📁 Moviendo archivos ZIP a la carpeta terraform..."
mv lambda-layer.zip terraform/ 2>/dev/null || true
mv lambda-code.zip terraform/

log_success "Archivos ZIP creados y movidos exitosamente"

# Limpiar archivos temporales
log_info "🧹 Limpiando archivos temporales..."
rm -rf lambda-layer
rm -rf lambda-code
rm -f requirements.txt

# Desactivar ambiente virtual temporal
log_info "🐍 Desactivando ambiente virtual temporal..."
deactivate
rm -rf .temp-venv

# Plan de Terraform
log_info "📋 Ejecutando Terraform Plan..."
cd terraform

# Variables específicas para el plan
PLAN_ARGS=(
    "-var=environment=$ENVIRONMENT"
    "-var=aws_region=$TF_VAR_aws_region"
    "-var=form_service_url=$TF_VAR_form_service_url"
    "-var=employee_service_url=$TF_VAR_employee_service_url"
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

# Confirmar despliegue
echo ""
log_warning "🚨 ¿Estás seguro de que quieres desplegar a $ENVIRONMENT?"
log_warning "Esto puede tomar varios minutos y puede incurrir en costos de AWS."
echo ""
read -p "Escribe 'yes' para continuar: " confirm

if [[ "$confirm" != "yes" ]]; then
    log_info "Despliegue cancelado"
    exit 0
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

