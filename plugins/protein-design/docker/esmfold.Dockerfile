FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/conda/bin:${PATH}"
ENV MAX_JOBS=2

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -o /tmp/miniforge.sh \
    && bash /tmp/miniforge.sh -b -p /opt/conda \
    && rm /tmp/miniforge.sh \
    && conda install -y --override-channels -c conda-forge python=3.9 pip \
    && conda clean -afy

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu118 \
    && pip install --no-cache-dir "fair-esm[esmfold]" \
    && pip install --no-cache-dir 'dllogger @ git+https://github.com/NVIDIA/dllogger.git' \
    && git clone https://github.com/aqlaboratory/openfold.git /tmp/openfold \
    && cd /tmp/openfold \
    && git checkout 4b41059694619831a7db195b7e0988fc4ff3a307 \
    && python -c "from pathlib import Path; p=Path('setup.py'); p.write_text(p.read_text().replace('-std=c++14', '-std=c++17'))" \
    && pip install --no-cache-dir . \
    && rm -rf /tmp/openfold

WORKDIR /work
CMD ["esm-fold", "--help"]
