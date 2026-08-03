# ប្រើ Python 3.11 (មិនមែន 3.14)
FROM python:3.11-slim

# ដំឡើង ffmpeg និង dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libsm6 \
        libxext6 \
        libgl1 \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# កំណត់ working directory
WORKDIR /app

# ចម្លង requirements ជាមុន
COPY requirements.txt .

# ដំឡើង Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ចម្លងកូដទាំងអស់
COPY . .

# បើក port 8000
EXPOSE 8000

# រត់ bot
CMD ["python", "main.py"]
