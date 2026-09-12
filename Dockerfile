# twicetold-npc API image, built FROM this repo by `docker compose up -d --build`.
# Never published as a prebuilt image (ruled): psycopg is LGPL-3.0-only, and
# redistribution stays the integrator's own packaging act, never this project's.
# Pinned to an exact patch tag (repo rule); the digest form is available if
# supply-chain pinning is ever ruled in.
FROM python:3.14.7-slim-trixie

# HF_HOME is set here so the bake below and the runtime hit the SAME cache path.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf-cache

WORKDIR /app

# Layer 1: dependencies. Cache-keyed on requirements.txt alone.
COPY requirements.txt .
# CPU-only torch. The coref model runs device='cpu', and on Linux the default
# torch wheel drags in ~5GB of CUDA libraries (cuda-toolkit, cudnn, nccl, triton)
# that can never execute here. Install torch from the CPU index FIRST so
# fastcoref's transitive torch>=1.10.0 is already satisfied and the second pip
# never fetches the CUDA build. The version tracks the deps-probe resolution and
# is the one pin living outside requirements.txt, paired with fastcoref==2.1.6.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch==2.14.0" \
    && pip install --no-cache-dir -r requirements.txt

# Non-root before the bake: the cache lands owned by the runtime user with no
# layer-duplicating chown. The API is an unauthenticated network service.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /opt/hf-cache \
    && chown appuser:appuser /opt/hf-cache
USER appuser

# Layer 2: bake the fastcoref weights (biu-nlp/f-coref, MIT) into the image so a
# cold container start needs NO network. The spaCy models need no bake (they are
# pip wheels already in site-packages); this FCoref init also loads its internal
# en_core_web_sm, exercising the whole warm path once at build.
RUN python -c "from fastcoref import FCoref; FCoref(device='cpu')"

# From here on, including at runtime, the HuggingFace stack is hard-offline: a
# missing cache file raises loudly instead of downloading. AFTER the bake on
# purpose, so the bake itself is still allowed to fetch.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# Layer 3: the application (changes often; never invalidates layers 1 and 2).
COPY app/ app/
COPY db/ db/
COPY data/lexicons/ data/lexicons/
COPY ledger/index.html ledger/index.html
COPY LICENSE NOTICE ./

# app.config expects the gitignored .env AT /app/.env. The compose api service
# bind-mounts it read-only; it is dockerignored and must NEVER be COPY'd here.

EXPOSE 8000
# --host 0.0.0.0: loopback scoping happens at the compose port publish, not here.
# SelectorEventLoop in app.serve is a Windows workaround, harmless on Linux.
CMD ["python", "-m", "app.serve", "--host", "0.0.0.0"]
