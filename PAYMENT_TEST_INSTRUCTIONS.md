# 💳 Инструкция по тестированию платежей

## ✅ **Что уже настроено:**

### **Webhook YooKassa:**
- **URL:** `https://vm16784.hosted-by.it-garage.pro/webhook/yookassa`
- **События:** `payment.succeeded`, `payment.canceled`
- **Обработчик:** обновлен для обоих событий

### **Код обработки:**
- ✅ `payment.succeeded` - создает подписку
- ✅ `payment.canceled` - логирует отмену
- ✅ Все события сохраняются в файлы `/tmp/webhooks/`

---

## 🧪 **Способы тестирования:**

### **1. Тест webhook (локально):**
```bash
./test_webhook.sh
```
Отправляет тестовые webhook события на сервер

### **2. Создание реального платежа:**
```bash
python3 test_payment.py
```
Создает настоящий платеж через YooKassa API

### **3. Тест через бота:**
1. Откройте бот @vpn_club_pro_bot
2. Выберите `/start`
3. Выберите тариф
4. Выберите "🥇 YooKassa" для оплаты
5. Выполните тестовую оплату

---

## 📋 **Что проверить:**

### **После успешной оплаты:**
1. ✅ Webhook получен на сервере
2. ✅ Статус платежа изменился на `succeeded`
3. ✅ Создана подписка пользователя
4. ✅ Отправлен VPN ключ
5. ✅ Запланировано уведомление об истечении

### **После отмены платежа:**
1. ✅ Webhook получен на сервере
2. ✅ Статус платежа изменился на `canceled`
3. ✅ Подписка НЕ создана
4. ✅ Логи содержат информацию об отмене

---

## 🔍 **Проверка логов:**

### **На сервере:**
```bash
# Логи бота
docker-compose logs -f bot | grep webhook

# Логи nginx
docker-compose logs -f nginx | grep yookassa

# Файлы webhook
ls -la /tmp/webhooks/
```

### **Локально:**
```bash
# Проверка созданных платежей
python3 -c "
import asyncio
from app.database import AsyncSessionLocal
from app.models import Payment
from sqlalchemy import select

async def check_payments():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Payment).order_by(Payment.created_at.desc()).limit(5))
        payments = result.scalars().all()
        for p in payments:
            print(f'ID: {p.yookassa_payment_id}, Status: {p.status}, Amount: {p.amount}')

asyncio.run(check_payments())
"
```

---

## 🎯 **Что должно работать:**

### **Полный цикл оплаты:**
1. **Создание платежа** → YooKassa API
2. **Перенаправление** → пользователь оплачивает
3. **Webhook** → сервер получает уведомление
4. **Обработка** → создание подписки
5. **Уведомление** → отправка VPN ключа

### **Поддерживаемые события:**
- ✅ `payment.succeeded` - успешная оплата
- ✅ `payment.canceled` - отмена платежа

---

## 🚨 **Возможные проблемы:**

### **1. Webhook не получен:**
- Проверьте SSL сертификат
- Проверьте URL в настройках YooKassa
- Проверьте работу nginx

### **2. Платеж не обработан:**
- Проверьте логи обработчика
- Проверьте файлы в `/tmp/webhooks/`
- Проверьте подключение к БД

### **3. Подписка не создана:**
- Проверьте работу SubscriptionService
- Проверьте работу OutlineService
- Проверьте логи планировщика

---

## 📞 **Готовность к тестированию:**

**Webhook URL:** `https://vm16784.hosted-by.it-garage.pro/webhook/yookassa`
**События:** `payment.succeeded`, `payment.canceled`
**Статус:** ✅ Готов к тестированию 