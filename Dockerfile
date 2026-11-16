# CTBench-PQ locked toolchain
# Reproducible environment: python 3.13 + MiKTeX (pdflatex) + gcc 15.2 (for tool baseline)
FROM python:3.13-slim

# MiKTeX for manuscript rebuild
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make \
    && rm -rf /var/lib/apt/lists/*

# Python deps for analysis scripts
RUN pip install --no-cache-dir pypdf PyPDF2 python-docx numpy

# Copy package
WORKDIR /CTBench-PQ
COPY . .

# Entry: reproduction
CMD ["bash", "reproduce.sh"]
