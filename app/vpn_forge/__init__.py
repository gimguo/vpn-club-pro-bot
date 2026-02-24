"""
VPN Forge — Автономная система управления VPN-инфраструктурой.

Компоненты:
- models:       Модели данных (VPNServer, ServerEvent, HealthCheck)
- ssh_client:   Асинхронный SSH-клиент
- deployer:     Автоустановка Outline VPN на серверах
- monitor:      Мониторинг здоровья серверов
- healer:       Автоматическое восстановление
- ai_agent:     ИИ-диагностика через DeepSeek (OpenRouter)
- orchestrator: Автомасштабирование флота
- providers:    Интеграция с облачными провайдерами (Hetzner, ...)
- manager:      Центральный менеджер + интеграция с ботом
"""
