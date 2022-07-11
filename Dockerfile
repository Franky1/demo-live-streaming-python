FROM python:3.8-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

# we probably need build tools?
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    curl \
    wget \
    git

WORKDIR /app
COPY requirements.txt requirements.txt

# if we have a packages.txt, install it
# but packages.txt must have only LF endings
# COPY packages.txt packages.txt
# RUN xargs -a packages.txt apt-get install --yes

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

CMD ["python", "main.py"]

# docker build --progress=plain --tag lemon:latest .
# docker run -ti --rm lemon:latest /bin/bash
# docker run -ti --rm lemon:latest
# docker run -ti -v ${pwd}:/app --rm lemon:latest
# docker run -ti -v ${pwd}:/app --rm lemon:latest /bin/bash
