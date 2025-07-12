#!/bin/bash

# Создаем директорию для SSL сертификатов
mkdir -p ssl

# Генерируем самоподписанный сертификат
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout ssl/server.key \
    -out ssl/server.crt \
    -subj "/C=RU/ST=Moscow/L=Moscow/O=VpnClubPro/CN=5.129.196.245"

echo "SSL certificate generated successfully!"
echo "Certificate: ssl/server.crt"
echo "Private key: ssl/server.key" 