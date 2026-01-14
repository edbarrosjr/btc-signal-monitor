FROM python:3.11-slim

WORKDIR /app

# Instalar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Criar diretório de logs
RUN mkdir -p /app/logs

# Executar
CMD ["python", "main.py"]
