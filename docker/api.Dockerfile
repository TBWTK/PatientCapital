FROM mirror.gcr.io/library/python:3.13-slim@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-rus \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN python -m pip install --no-cache-dir .

COPY docker/api-entrypoint.sh /usr/local/bin/patientcapital-api-entrypoint
RUN useradd --create-home --uid 10001 patientcapital \
    && chown -R patientcapital:patientcapital /app

USER patientcapital
EXPOSE 8000

ENTRYPOINT ["patientcapital-api-entrypoint"]
