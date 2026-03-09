import asyncio
import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.services.subscription_service import SubscriptionService
from app.services.user_service import UserService
from app.database import AsyncSessionLocal
from config import settings

logger = logging.getLogger(__name__)


_MAX_PROCESSED_PAYMENTS = 10_000  # Предел кэша обработанных платежей


class NotificationScheduler:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.processed_payments: set[str] = set()  # Для избежания дублирования
        
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
        
    def schedule_subscription_notification(self, user_id: int, subscription_end_date: datetime):
        """Планирование уведомлений об истечении подписки"""
        try:
            # Планируем уведомление за 3 дня до окончания
            notification_date = subscription_end_date - timedelta(days=3)
            
            # Планируем только если дата в будущем
            if notification_date > datetime.now(pytz.UTC):
                job_id = f"expiring_notification_{user_id}_{subscription_end_date.timestamp()}"
                
                # Удаляем предыдущие уведомления для этого пользователя если есть
                try:
                    existing_jobs = [job for job in self.scheduler.get_jobs() if job.id.startswith(f"expiring_notification_{user_id}_")]
                    for job in existing_jobs:
                        self.scheduler.remove_job(job.id)
                except Exception as exc:
                    logger.debug(f"Could not remove old notification jobs for user {user_id}: {exc}")
                
                # Добавляем новое уведомление
                self.scheduler.add_job(
                    self.send_expiring_notification,
                    DateTrigger(run_date=notification_date),
                    args=[user_id],
                    id=job_id
                )
                
                logger.info(f"📅 Запланировано уведомление для пользователя {user_id} на {notification_date}")
                
        except Exception as e:
            logger.error(f"Ошибка при планировании уведомления: {e}")
            
    async def send_expiring_notification(self, user_id: int):
        """Отправка уведомления о скором истечении подписки"""
        try:
            async with AsyncSessionLocal() as session:
                user_service = UserService(session)
                user = await user_service.get_user_by_id(user_id)
                
                if user:
                    text = """⚠️ <b>Срок действия вашего ключа подходит к концу!</b>

⏰ Осталось: 3 дня

Можете продлить подписку или изменить существующий тариф в разделе "Тарифы"."""
                    
                    await self.bot.send_message(
                        user.telegram_id,
                        text,
                        parse_mode="HTML"
                    )
                    logger.info(f"📤 Отправлено персональное уведомление пользователю {user.telegram_id}")
                    
        except Exception as e:
            logger.error(f"Ошибка отправки персонального уведомления пользователю {user_id}: {e}")
        
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
                            logger.warning(f"Пользователь {subscription.user_id} не найден")
                            continue
                        
                        text = """⚠️ <b>Срок действия вашего ключа подходит к концу!</b>

⏰ Осталось: 3 дня

Можете продлить подписку или изменить существующий тариф в разделе "Тарифы"."""
                        
                        await self.bot.send_message(
                            user.telegram_id,
                            text,
                            parse_mode="HTML"
                        )
                        logger.info(f"📤 Отправлено уведомление пользователю {user.telegram_id}")
                        
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления пользователю {subscription.user_id}: {e}")
                        
        except Exception as e:
            logger.error(f"Ошибка при проверке истекающих подписок: {e}")
            
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
                            logger.warning(f"Пользователь {subscription.user_id} не найден")
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
                        logger.info(f"✅ Деактивирована подписка {subscription.id} пользователя {user.telegram_id}")
                        
                    except Exception as e:
                        logger.error(f"Ошибка обработки истекшей подписки {subscription.id}: {e}")
                        
        except Exception as e:
            logger.error(f"Ошибка при проверке истекших подписок: {e}")
            
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
                        logger.error(f"Не удалось отправить сообщение пользователю {user.telegram_id}: {e}")
                
                logger.info(f"Рассылка завершена. Отправлено: {sent_count}, Ошибок: {failed_count}")
                return sent_count, failed_count
                
        except Exception as e:
            logger.error(f"Ошибка при массовой рассылке: {e}")
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
            webhook_files = [f for f in os.listdir(webhook_dir) if f.startswith("payment") and f.endswith(".json")]
            
            if not webhook_files:
                return
                
            logger.info(f"🔍 Найдено {len(webhook_files)} webhook файлов для обработки")
            
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
                        event_type = webhook_data.get("event", "")
                        
                        # ── Обрабатываем ТОЛЬКО succeeded ──
                        if event_type != "payment.succeeded":
                            logger.info(f"⏭️ Пропускаем webhook {event_type} для платежа {payment_id}")
                            if event_type == "payment.canceled":
                                await payment_service.update_payment_status(payment_id, "canceled")
                                logger.info(f"❌ Payment {payment_id} marked as canceled")
                            os.remove(file_path)
                            logger.info(f"🗑️ Webhook file removed: {webhook_file}")
                            continue
                        
                        # Проверяем, не обрабатывался ли этот платеж уже
                        if payment_id in self.processed_payments:
                            logger.info(f"💳 Платеж {payment_id} уже был обработан, пропускаем")
                            os.remove(file_path)
                            continue
                        
                        logger.info(f"💳 Обрабатываем succeeded webhook для платежа: {payment_id}")
                        
                        # Дополнительная проверка через API YooKassa
                        is_really_paid = await payment_service.verify_payment(payment_id)
                        if not is_really_paid:
                            logger.warning(f"⚠️ Payment {payment_id} не подтверждён через API YooKassa, пропускаем")
                            os.remove(file_path)
                            continue
                        
                        # Обновляем статус платежа
                        payment = await payment_service.update_payment_status(payment_id, "succeeded")
                        
                        if payment:
                            logger.info(f"✅ Payment {payment_id} marked as succeeded (verified)")
                            
                            # Создаем подписку
                            subscription = await subscription_service.create_subscription(
                                payment.user_id, 
                                payment.tariff_type
                            )
                            
                            # Планируем уведомление об истечении подписки
                            self.schedule_subscription_notification(payment.user_id, subscription.end_date)
                            
                            # Отправляем уведомление пользователю
                            user = await user_service.get_user_by_id(payment.user_id)
                            if user:
                                from app.keyboards.tariff_keyboard import TariffKeyboard
                                tariff_names = TariffKeyboard.get_tariff_names()
                                
                                success_text = """🎉 <b>Оплата прошла успешно!</b>

🔑 <b>Ваш ключ доступа:</b>"""
                                
                                # Добавляем "активна до" для всех подписок
                                traffic_info = "🚀 Безлимитный трафик"
                                if payment.tariff_type == "trial":
                                    traffic_info = f"📊 Лимит: {settings.trial_traffic_gb} ГБ"
                                
                                info_text = f"""📋 <b>Информация о подписке:</b>
📦 Тариф: {tariff_names[payment.tariff_type]}
{traffic_info}
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
                                
                                logger.info(f"📱 Notification sent to user {user.telegram_id}")
                            
                            # Добавляем в список обработанных (с защитой от утечки памяти)
                            if len(self.processed_payments) >= _MAX_PROCESSED_PAYMENTS:
                                # Сбрасываем половину кэша (самые старые уже точно не нужны)
                                self.processed_payments.clear()
                            self.processed_payments.add(payment_id)
                        
                        # Удаляем обработанный файл
                        os.remove(file_path)
                        logger.info(f"🗑️ Webhook file processed and removed: {webhook_file}")
                        
                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки webhook файла {webhook_file}: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке webhook файлов: {e}") 