# definiçoes do SO do container -> equivalente ao bootstrap.sh do vagrant
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=America/Recife \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    gnupg \
    software-properties-common \
    build-essential \
    libpq-dev \
    autoconf \
    unzip \
    pkg-config \
    libssl-dev \
    python3 \
    python3-dev \
    python3-pip \
    python-is-python3 \
    graphviz \
    graphviz-dev \
    libmagickwand-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir "setuptools<58" wheel debugpy

COPY resources/requirements.txt /app/resources/requirements.txt
RUN pip install --no-cache-dir -r /app/resources/requirements.txt

COPY resources/django/settings.py-tpl /app/resources/django/settings.py-tpl
RUN DJANGO_DIR=$(python -c "import django, os; print(os.path.dirname(django.__file__))") && \
    cp /app/resources/django/settings.py-tpl "$DJANGO_DIR/conf/project_template/project_name/settings.py-tpl"

WORKDIR /app/web-folder
EXPOSE 8000 8001
CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:8001", "manage.py", "runserver", "0.0.0.0:8000"]
