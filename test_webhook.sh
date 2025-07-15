#!/bin/bash

# 🔧 Тест webhook для YooKassa
echo "🔧 Тестирование webhook YooKassa..."

WEBHOOK_URL="https://vm16784.hosted-by.it-garage.pro/webhook/yookassa"

# Тест 1: payment.succeeded
echo "📋 Тест 1: payment.succeeded"
curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "payment.succeeded",
    "object": {
      "id": "test_payment_123",
      "status": "succeeded",
      "amount": {
        "value": "150.00",
        "currency": "RUB"
      },
      "metadata": {
        "user_id": "123",
        "tariff_type": "monthly"
      }
    }
  }'

echo -e "\n"

# Тест 2: payment.canceled
echo "📋 Тест 2: payment.canceled"
curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "payment.canceled",
    "object": {
      "id": "test_payment_456",
      "status": "canceled",
      "amount": {
        "value": "150.00",
        "currency": "RUB"
      },
      "metadata": {
        "user_id": "123",
        "tariff_type": "monthly"
      }
    }
  }'

echo -e "\n"

# Тест 3: Проверка доступности
echo "📋 Тест 3: Проверка доступности"
curl -I "$WEBHOOK_URL"

echo -e "\n✅ Тесты завершены"
echo "🔗 Webhook URL: $WEBHOOK_URL"
echo "📋 События: payment.succeeded, payment.canceled" 