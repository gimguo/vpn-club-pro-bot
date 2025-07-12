from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.subscription_service import SubscriptionService
from app.services.user_service import UserService
from app.database import AsyncSessionLocal
from config import settings
import asyncio
from datetime import datetime

class NotificationScheduler:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        
    def start(self):
        """Запуск планировщика"""
        # Ежедневная проверка в 10:00
        self.scheduler.add_job(
            self.check_expiring_subscriptions,
            CronTrigger(hour=10, minute=0),
            id="check_expiring"
        )
        
        # Ежедневная проверка истекших подписок в 10:30
        self.scheduler.add_job(
            self.check_expired_subscriptions,
            CronTrigger(hour=10, minute=30),
            id="check_expired"
        )
        
        # Обработка webhook файлов каждые 30 секунд
        self.scheduler.add_job(
            self.process_webhook_files,
            "interval",
            seconds=30,
            id="process_webhooks"
        )
        
        self.scheduler.start()
        
    def stop(self):
        """Остановка планировщика"""
        self.scheduler.shutdown()
        
    async def check_expiring_subscriptions(self):
        """Проверка подписок, истекающих через 3 дня"""
        try:
            async with AsyncSessionLocal() as session:
                subscription_service = SubscriptionService(session)
                user_service = UserService(session)
                expiring_subscriptions = await subscription_service.get_expiring_subscriptions(3)
                
                for subscription in expiring_subscriptions:
                    try:
                        # Получаем пользователя через UserService для избежания проблем с async
                        user = await user_service.get_user_by_id(subscription.user_id)
                        if not user:
                            print(f"Пользователь {subscription.user_id} не найден")
                            continue
                        
                        text = """⚠️ <b>Срок действия вашего ключа подходит к концу!</b>

⏰ Осталось: 3 дня

Можете продлить подписку или изменить существующий тариф в разделе "Тарифы"."""
                        
                        await self.bot.send_message(
                            user.telegram_id,
                            text,
                            parse_mode="HTML"
                        )
                        print(f"📤 Отправлено уведомление пользователю {user.telegram_id}")
                        
                    except Exception as e:
                        print(f"Ошибка отправки уведомления пользователю {subscription.user_id}: {e}")
                        
        except Exception as e:
            print(f"Ошибка при проверке истекающих подписок: {e}")
            
    async def check_expired_subscriptions(self):
        """Проверка и деактивация истекших подписок"""
        try:
            async with AsyncSessionLocal() as session:
                subscription_service = SubscriptionService(session)
                user_service = UserService(session)
                expired_subscriptions = await subscription_service.get_expired_subscriptions()
                
                for subscription in expired_subscriptions:
                    try:
                        # Получаем пользователя через UserService для избежания проблем с async
                        user = await user_service.get_user_by_id(subscription.user_id)
                        if not user:
                            print(f"Пользователь {subscription.user_id} не найден")
                            continue
                        
                        # Уведомляем пользователя
                        text = """❌ <b>Срок действия вашего ключа истёк</b>

Вы можете приобрести новый в разделе "Тарифы".

Спасибо, что были с нами! 🙏"""
                        
                        await self.bot.send_message(
                            user.telegram_id,
                            text,
                            parse_mode="HTML"
                        )
                        
                        # Деактивируем подписку
                        await subscription_service.deactivate_subscription(subscription)
                        print(f"✅ Деактивирована подписка {subscription.id} пользователя {user.telegram_id}")
                        
                    except Exception as e:
                        print(f"Ошибка обработки истекшей подписки {subscription.id}: {e}")
                        
        except Exception as e:
            print(f"Ошибка при проверке истекших подписок: {e}")
            
    async def send_broadcast_message(self, message_text: str):
        """Отправка массового сообщения всем активным пользователям"""
        try:
            async with AsyncSessionLocal() as session:
                user_service = UserService(session)
                active_users = await user_service.get_all_active_users()
                
                sent_count = 0
                failed_count = 0
                
                for user in active_users:
                    try:
                        await self.bot.send_message(
                            user.telegram_id,
                            message_text,
                            parse_mode="HTML"
                        )
                        sent_count += 1
                        # Небольшая задержка чтобы не превысить лимиты API
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        failed_count += 1
                        print(f"Не удалось отправить сообщение пользователю {user.telegram_id}: {e}")
                
                print(f"Рассылка завершена. Отправлено: {sent_count}, Ошибок: {failed_count}")
                return sent_count, failed_count
                
        except Exception as e:
            print(f"Ошибка при массовой рассылке: {e}")
            return 0, 0 
            
    async def process_webhook_files(self):
        """Обработка webhook файлов из /tmp/webhooks"""
        try:
            import os
            import json
            
            webhook_dir = "/tmp/webhooks"
            if not os.path.exists(webhook_dir):
                return
                
            # Получаем все файлы webhook
            webhook_files = [f for f in os.listdir(webhook_dir) if f.startswith("payment_") and f.endswith(".json")]
            
            if not webhook_files:
                return
                
            print(f"🔍 Найдено {len(webhook_files)} webhook файлов для обработки")
            
            async with AsyncSessionLocal() as session:
                from app.services.payment_service import PaymentService
                from app.services.subscription_service import SubscriptionService
                from app.services.user_service import UserService
                
                payment_service = PaymentService(session)
                subscription_service = SubscriptionService(session)
                user_service = UserService(session)
                
                for webhook_file in webhook_files:
                    try:
                        file_path = os.path.join(webhook_dir, webhook_file)
                        
                        # Читаем данные webhook
                        with open(file_path, "r") as f:
                            webhook_data = json.load(f)
                        
                        payment_id = webhook_data["payment_id"]
                        print(f"💳 Обрабатываем webhook для платежа: {payment_id}")
                        
                        # Обновляем статус платежа
                        payment = await payment_service.update_payment_status(payment_id, "succeeded")
                        
                        if payment:
                            print(f"✅ Payment {payment_id} marked as succeeded")
                            
                            # Создаем подписку
                            subscription = await subscription_service.create_subscription(
                                payment.user_id, 
                                payment.tariff_type
                            )
                            
                            # Отправляем уведомление пользователю
                            user = await user_service.get_user_by_id(payment.user_id)
                            if user:
                                from app.keyboards.tariff_keyboard import TariffKeyboard
                                tariff_names = TariffKeyboard.get_tariff_names()
                                
                                success_text = """🎉 <b>Оплата прошла успешно!</b>

🔑 <b>Ваш ключ доступа:</b>"""
                                
                                info_text = f"""📋 <b>Информация о подписке:</b>
📦 Тариф: {tariff_names[payment.tariff_type]}
🚀 Безлимитный трафик
⏰ Активна до: {subscription.end_date.strftime('%d.%m.%Y')}

📱 Не забудьте скачать приложение и настроить VPN!"""
                                
                                # Отправляем подтверждение оплаты
                                await self.bot.send_message(
                                    chat_id=user.telegram_id,
                                    text=success_text,
                                    parse_mode="HTML"
                                )
                                # Отправляем ключ отдельным сообщением
                                await self.bot.send_message(
                                    chat_id=user.telegram_id,
                                    text=f"<code>{subscription.access_url}</code>",
                                    parse_mode="HTML"
                                )
                                # Отправляем информацию о подписке
                                await self.bot.send_message(
                                    chat_id=user.telegram_id,
                                    text=info_text,
                                    parse_mode="HTML"
                                )
                                
                                print(f"📱 Notification sent to user {user.telegram_id}")
                        
                        # Удаляем обработанный файл
                        os.remove(file_path)
                        print(f"🗑️ Webhook file processed and removed: {webhook_file}")
                        
                    except Exception as e:
                        print(f"❌ Ошибка обработки webhook файла {webhook_file}: {e}")
                        
        except Exception as e:
            print(f"❌ Ошибка при обработке webhook файлов: {e}") 