-- Создание таблиц для системы поддержки
-- Дата: 2025-06-18
-- Описание: Добавление системы тикетов поддержки

-- Таблица тикетов поддержки
CREATE TABLE IF NOT EXISTS support_tickets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticket_number VARCHAR(20) UNIQUE NOT NULL,
    subject VARCHAR(255),
    message TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'new' CHECK (status IN ('new', 'in_progress', 'closed')),
    priority VARCHAR(10) DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    category VARCHAR(50),
    admin_response TEXT,
    admin_id INTEGER,
    responded_at TIMESTAMP WITH TIME ZONE,
    closed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Таблица сообщений в тикетах
CREATE TABLE IF NOT EXISTS support_messages (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    admin_id INTEGER,
    message TEXT NOT NULL,
    is_from_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы для оптимизации
CREATE INDEX IF NOT EXISTS idx_support_tickets_user_id ON support_tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at ON support_tickets(created_at);
CREATE INDEX IF NOT EXISTS idx_support_tickets_ticket_number ON support_tickets(ticket_number);

CREATE INDEX IF NOT EXISTS idx_support_messages_ticket_id ON support_messages(ticket_id);
CREATE INDEX IF NOT EXISTS idx_support_messages_created_at ON support_messages(created_at);

-- Комментарии к таблицам
COMMENT ON TABLE support_tickets IS 'Тикеты службы поддержки';
COMMENT ON TABLE support_messages IS 'Сообщения в тикетах поддержки';

-- Комментарии к колонкам
COMMENT ON COLUMN support_tickets.ticket_number IS 'Уникальный номер тикета в формате SUP-YYYYMMDD-XXXXX';
COMMENT ON COLUMN support_tickets.status IS 'Статус тикета: new, in_progress, closed';
COMMENT ON COLUMN support_tickets.priority IS 'Приоритет: low, normal, high, urgent';
COMMENT ON COLUMN support_tickets.category IS 'Категория обращения: connection, payment, technical, setup, other';

COMMENT ON COLUMN support_messages.is_from_admin IS 'Сообщение от администратора (true) или пользователя (false)';

-- Триггер для обновления updated_at
CREATE OR REPLACE FUNCTION update_support_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_support_tickets_updated_at
    BEFORE UPDATE ON support_tickets
    FOR EACH ROW
    EXECUTE FUNCTION update_support_updated_at_column();

CREATE TRIGGER update_support_messages_updated_at
    BEFORE UPDATE ON support_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_support_updated_at_column(); 