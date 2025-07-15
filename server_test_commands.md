# 🖥️ Команды для тестирования на сервере

## 📋 **Подключение к серверу:**
```bash
ssh deployer@vm16784.hosted-by.it-garage.pro
# или
ssh deployer@178.236.243.9
```

## 🧪 **Тестирование webhook:**

### **1. Тест payment.succeeded:**
```bash
curl -X POST "http://localhost:8000/webhook/yookassa" \
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
```

### **2. Тест payment.canceled:**
```bash
curl -X POST "http://localhost:8000/webhook/yookassa" \
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
```

### **3. Проверка работы сервера:**
```bash
# Проверка доступности API
curl -I http://localhost:8000/

# Проверка webhook endpoint
curl -I http://localhost:8000/webhook/yookassa

# Статус контейнеров
docker-compose ps

# Логи бота
docker-compose logs -f bot | grep webhook
```

## 📁 **Проверка файлов webhook:**
```bash
# Проверка папки webhooks
ls -la /tmp/webhooks/

# Содержимое файлов
cat /tmp/webhooks/payment_*.json
```

## 📊 **Проверка базы данных:**
```bash
# Подключение к БД
docker-compose exec db psql -U postgres -d vpn_club

# Проверка платежей
SELECT id, yookassa_payment_id, status, amount, tariff_type, created_at 
FROM payments 
ORDER BY created_at DESC 
LIMIT 10;

# Проверка подписок
SELECT id, user_id, tariff_type, start_date, end_date, is_active 
FROM subscriptions 
ORDER BY created_at DESC 
LIMIT 10;
```

## 🔍 **Мониторинг логов:**
```bash
# Логи в реальном времени
docker-compose logs -f bot | grep -E "(webhook|payment|subscription)"

# Логи nginx
docker-compose logs -f nginx | grep yookassa

# Все логи
docker-compose logs --tail=100 bot
```

## ✅ **Ожидаемый результат:**

### **При успешном тесте:**
1. **Ответ:** `{"status": "ok"}`
2. **Логи:** `💳 Processing successful payment: test_payment_123`
3. **Файл:** `/tmp/webhooks/payment_test_payment_123.json`

### **При отмене платежа:**
1. **Ответ:** `{"status": "ok"}`
2. **Логи:** `❌ Processing canceled payment: test_payment_456`
3. **Файл:** `/tmp/webhooks/payment_canceled_test_payment_456.json`

## 🎯 **Настройки YooKassa:**
- **URL:** `https://vm16784.hosted-by.it-garage.pro/webhook/yookassa`
- **События:** `payment.succeeded`, `payment.canceled`
- **Статус:** ✅ Готов к тестированию 