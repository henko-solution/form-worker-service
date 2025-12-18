FROM public.ecr.aws/lambda/python:3.13

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy requirements file
COPY pyproject.toml ${LAMBDA_TASK_ROOT}

# Update pip to latest version
RUN pip install --upgrade pip

# Install Python dependencies
# Note: boto3 is already included in the Lambda base image
# Install local, test, and all (includes quality tools) for development
RUN pip install --no-cache-dir -e .[local,test,all]

WORKDIR ${LAMBDA_TASK_ROOT}

# Copy application code
COPY ./app ${LAMBDA_TASK_ROOT}/app

# Copy tests (for local development/testing)
COPY ./tests ${LAMBDA_TASK_ROOT}/tests

# Lambda handler is in app/lambda_handler.py
# Set handler in Lambda configuration: app.lambda_handler.lambda_handler
