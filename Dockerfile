FROM public.ecr.aws/lambda/python:3.14

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy requirements file
COPY pyproject.toml ${LAMBDA_TASK_ROOT}

# Install only core deps (same as Lambda layer). boto3 comes with Lambda runtime.
RUN pip install --no-cache-dir -e .

WORKDIR ${LAMBDA_TASK_ROOT}

# Copy application code
COPY ./app ${LAMBDA_TASK_ROOT}/app
COPY lambda_handler.py ${LAMBDA_TASK_ROOT}/

# Handler: lambda_handler.lambda_handler
