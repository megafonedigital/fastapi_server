#!/bin/bash
set -e

# Configurar permissões para bibliotecas
echo "Configurando permissões para bibliotecas..."
find /usr/local/lib/python3.11/site-packages/ctranslate2 -name "*.so*" -exec chmod +x {} \; || true

# Iniciar a aplicação
echo "Iniciando a aplicação..."
exec "$@"