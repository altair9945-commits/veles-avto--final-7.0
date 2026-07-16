# VERSION: VELES_BOT_V7_2_PUBLIC_TONCENTER_NO_KEY_2026_07_17

import os
import re
import asyncio
import hashlib
import urllib.parse
import urllib.request
import urllib.error
import csv
import json
import time
import sqlite3
import logging
import tempfile
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta
from html import escape

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
try:
    import qrcode
    QR_AVAILABLE = True
except Exception:
    qrcode = None
    QR_AVAILABLE = False

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_PIN = os.getenv("ADMIN_PIN", "").strip()

ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    DATA_DIR = Path(".")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "veles_trade_v3.sqlite3"

WARN_LIMIT_DEFAULT = int(os.getenv("WARN_LIMIT", "3"))
MUTE_SECONDS = int(os.getenv("MUTE_SECONDS", "1800"))

ORDER_DAILY_LIMIT = int(os.getenv("ORDER_DAILY_LIMIT", "5"))
ORDER_ACTIVE_LIMIT = int(os.getenv("ORDER_ACTIVE_LIMIT", "1"))
ORDER_COOLDOWN_SECONDS = int(os.getenv("ORDER_COOLDOWN_SECONDS", "900"))  # 15 min
ORDER_SPAM_BLOCK_SECONDS = int(os.getenv("ORDER_SPAM_BLOCK_SECONDS", "10800"))  # 3h
ORDER_SPAM_HITS_LIMIT = int(os.getenv("ORDER_SPAM_HITS_LIMIT", "3"))
PAYMENT_TTL_SECONDS = int(os.getenv("PAYMENT_TTL_SECONDS", "1800"))  # 30 min

TONCENTER_API_KEY = os.getenv("TONCENTER_API_KEY", "").strip()
TONCENTER_API_BASE = os.getenv("TONCENTER_API_BASE", "https://toncenter.com/api/v2").rstrip("/")
TON_PAYMENT_POLL_SECONDS = max(10, int(os.getenv("TON_PAYMENT_POLL_SECONDS", "20")))
TON_PAYMENT_TOLERANCE = float(os.getenv("TON_PAYMENT_TOLERANCE", "0.02"))
LOW_STOCK_THRESHOLD = max(1, int(os.getenv("LOW_STOCK_THRESHOLD", "10")))

SEED_OPTIONS = [1, 2, 3, 5, 10]

ORDER_STATUS = {
    "new": "🆕 Новый",
    "accepted": "👀 Принят",
    "awaiting_payment": "⏳ Ожидает оплаты",
    "tx_wait": "⛓ Ожидает подтверждений",
    "paid": "💰 Оплачен",
    "receipt_sent": "📎 Чек отправлен",
    "work": "📦 В работе",
    "sent": "🚚 Передан",
    "closed": "✅ Закрыт",
    "cancelled": "❌ Отменён",
    "expired": "⌛ Просрочен",
}

TERMINAL_STATUSES = {"closed", "cancelled", "expired"}
CLIENT_CANCEL_ALLOWED = {"new", "accepted", "awaiting_payment"}
ADMIN_ROLES = {"owner": "👑 Владелец", "admin": "🛡 Админ", "operator": "📦 Оператор"}

VIP_STATUSES = [
    (200, "👑 Золотой Тигр Дома"),
    (150, "🐆 Барс Дома"),
    (100, "🐅 Тигр Дома"),
    (75, "🐈‍⬛ Рысь Дома"),
    (50, "🦊 Лис Дома"),
    (25, "🐇 Заяц Дома"),
    (10, "🦔 Ёжик Дома"),
    (5, "🐿️ Белка Дома"),
    (1, "🐾 Первый След"),
    (0, "🌿 Гость Дома"),
]

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.WARNING,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

PRETTY_PAYMENT_HELP_TEXT = """💳 Инструкция по пополнению баланса через xRocket / Bitpapa

Перед тем как писать администрации, вам нужно самостоятельно обменять деньги на крипту.

✅ Нужная крипта: TON / GRAM
❌ Без крипты — не пишите
❌ С вопросами “как оплатить картой?” — не пишите
❌ Рубли / карта / наличка — не принимаются

Сначала покупаете крипту.
Только потом пишете администрации.

━━━━━━━━━━━━━━━

🚀 Вариант 1: xRocket

1️⃣ Откройте xRocket в Telegram
2️⃣ Зайдите в раздел Купить / Пополнить / Обмен
3️⃣ Выберите крипту: TON / GRAM
4️⃣ Выберите удобный способ оплаты
5️⃣ Оплатите заявку
6️⃣ Дождитесь, пока крипта появится на вашем балансе
7️⃣ Проверьте, что TON / GRAM уже лежит у вас в кошельке
8️⃣ Только после этого пишите администрации

━━━━━━━━━━━━━━━

🟡 Вариант 2: Bitpapa

1️⃣ Откройте Bitpapa
2️⃣ Выберите покупку крипты
3️⃣ Укажите крипту: TON / GRAM
4️⃣ Выберите продавца и способ оплаты
5️⃣ Оплатите сделку по инструкции внутри Bitpapa
6️⃣ Дождитесь получения крипты
7️⃣ Проверьте баланс
8️⃣ После этого пишите администрации

━━━━━━━━━━━━━━━

📩 Когда пишете администрации — сразу указывайте:

• какая сумма у вас на балансе
• какая крипта: TON или GRAM
• где покупали: xRocket или Bitpapa
• готовы ли переводить сразу

━━━━━━━━━━━━━━━

⚠️ Важно

Администрация не занимается вашим обменом.
Администрация не объясняет каждому отдельно, как покупать крипту.
Сначала сами меняете деньги на TON / GRAM.
Потом пишете администрации.

❌ Нет крипты — не пишите.
✅ Есть TON / GRAM на балансе — пишите.

Не тратьте своё и чужое время.
"""



# =========================
# DB
# =========================

PRETTY_WELCOME_TEXT = """⚜️ VELES TRADE

Добро пожаловать в Дом.

Здесь можно:
🛒 открыть витрину;
📦 посмотреть свои заказы;
🏅 проверить статус;
📜 прочитать правила;
🚀 узнать, как оплатить.

Выберите действие кнопками ниже.
"""

PRETTY_RULES_TEXT = """📜 ПРАВИЛА ДОМА

⚜️ Добро пожаловать в Дом.

Здесь держим порядок, уважение и спокойное общение.
Без лишнего шума, спама и пустых сообщений.

━━━━━━━━━━━━━━━

🐻 1. Уважение к участникам

Общаемся спокойно.
Без оскорблений, провокаций и лишней грязи.

━━━━━━━━━━━━━━━

🚫 2. Запрещено

— спамить в чат;
— флудить одинаковыми сообщениями;
— кидать стороннюю рекламу;
— отправлять подозрительные ссылки;
— провоцировать участников;
— мешать работе администрации.

━━━━━━━━━━━━━━━

🔗 3. Ссылки и реклама

Любые ссылки, реклама, приглашения в другие каналы и группы — только с разрешения администрации.

━━━━━━━━━━━━━━━

🎲 4. Игровые анимации и мусор

Не закидываем чат кубиками, мячами, казино-анимациями и другим мусором.

Чат не помойка.

━━━━━━━━━━━━━━━

⚠️ 5. Предупреждения

За нарушение правил администрация может выдать предупреждение, мут или ограничение.

Систему не испытываем.

━━━━━━━━━━━━━━━

👑 6. Администрация

Администрация следит за порядком и принимает окончательное решение в спорных ситуациях.

Если есть вопрос — пишите спокойно и по делу.

━━━━━━━━━━━━━━━

⚜️ Главное правило простое:

Уважай Дом, уважай людей, не создавай хаос.
"""

PRETTY_CLIENT_RULES_TEXT = """📜 ПРАВИЛА ДЛЯ КЛИЕНТОВ

Перед оформлением заказа внимательно прочитайте правила.

Это нужно, чтобы всё проходило быстро, спокойно и без путаницы.

━━━━━━━━━━━━━━━

🛒 1. Заказ оформляется через бот

Для заказа используйте кнопку:

🛒 Витрина

Выберите позицию, количество и район / способ получения.

━━━━━━━━━━━━━━━

🧾 2. Один клиент — один активный заказ

Пока старый заказ не закрыт или не отменён, новый создать нельзя.

Это защита от дублей и путаницы.

━━━━━━━━━━━━━━━

⏳ 3. Лимиты по заявкам

В системе действует ограничение:

— 1 активный заказ;
— до 5 заявок в сутки;
— пауза между заявками 15 минут.

Спам заявками может привести к стоп-листу.

━━━━━━━━━━━━━━━

💳 4. Оплата

После подтверждения заказа бот покажет:

🧾 номер заказа;
💰 сумму;
💼 TON / GRAM кошелёк;
📝 комментарий / memo;
⏳ время на оплату.

Оплата действительна 30 минут.

━━━━━━━━━━━━━━━

💎 5. Валюта оплаты

Основная оплата принимается в TON / GRAM в сети TON.

Перед отправкой внимательно проверьте:

✅ сумму;
✅ TON / GRAM адрес;
✅ сеть TON;
✅ комментарий / memo с номером заказа;
✅ чек или hash после оплаты.

BTC — только резервный вариант через администратора.
Если бот показывает TON / GRAM кошелёк, BTC отправлять нельзя.

━━━━━━━━━━━━━━━

✅ 6. После оплаты

После оплаты нажмите кнопку:

✅ Я оплатил

Затем отправьте чек / скрин оплаты.

hash / ссылку транзакции можно отправить дополнительно, если есть.
Без чека заказ в работу не берётся.

━━━━━━━━━━━━━━━

🔍 7. Проверка оплаты

Оплата считается принятой только после проверки администрацией.

Если отправлен hash / ссылка транзакции, админ сможет быстрее найти перевод.

━━━━━━━━━━━━━━━

❌ 8. Отмена заказа

Клиент может отменить заказ только на раннем этапе.

После оплаты и передачи заказа в работу отмена решается через администрацию.

━━━━━━━━━━━━━━━

🚫 9. Запрещено

— отправлять фейковые чеки;
— спамить заявками;
— создавать ложные заказы;
— отвлекать администрацию без готовности оплатить;
— пытаться обойти правила.

За нарушение доступ к заказам может быть ограничен.

━━━━━━━━━━━━━━━

📦 10. Статус заказа

Проверить свои заказы можно через кнопку:

📦 Мои заказы

Проверить статус в Доме:

🏅 Мой статус

━━━━━━━━━━━━━━━

⚜️ Работаем спокойно, быстро и по порядку.

Уважайте своё время и время администрации.
"""



def now_ts() -> int:
    return int(time.time())


def fmt_dt(ts: int | None) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(int(ts)).strftime("%d.%m.%Y %H:%M")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL DEFAULT 'admin',
            username TEXT,
            first_name TEXT,
            added_at INTEGER NOT NULL
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            first_seen INTEGER NOT NULL,
            last_seen INTEGER NOT NULL,
            purchases INTEGER NOT NULL DEFAULT 0,
            notes TEXT DEFAULT '',
            order_banned_until INTEGER DEFAULT 0,
            order_ban_reason TEXT DEFAULT '',
            spam_hits INTEGER NOT NULL DEFAULT 0
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS districts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS item_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emoji TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'in_stock',
            stock INTEGER,
            type_id INTEGER,
            type_emoji TEXT DEFAULT '',
            type_enabled INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """)

        existing_item_cols = {r["name"] for r in c.execute("PRAGMA table_info(items)").fetchall()}
        item_migrations = {
            "type_id": "ALTER TABLE items ADD COLUMN type_id INTEGER",
            "type_emoji": "ALTER TABLE items ADD COLUMN type_emoji TEXT DEFAULT ''",
            "type_enabled": "ALTER TABLE items ADD COLUMN type_enabled INTEGER NOT NULL DEFAULT 1",
        }
        for col, ddl in item_migrations.items():
            if col not in existing_item_cols:
                c.execute(ddl)

        c.execute("""
        CREATE TABLE IF NOT EXISTS item_type_links (
            item_id INTEGER NOT NULL,
            type_id INTEGER NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            PRIMARY KEY (item_id, type_id)
        )
        """)

        # Перенос старой логики "один тип у позиции" в новую "несколько типов у позиции".
        c.execute(
            """
            INSERT OR IGNORE INTO item_type_links(item_id, type_id, enabled, created_at)
            SELECT id, type_id, IFNULL(type_enabled, 1), ?
            FROM items
            WHERE type_id IS NOT NULL
            """,
            (now_ts(),)
        )

        c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT UNIQUE,
            user_id INTEGER NOT NULL,
            username TEXT,
            item_id INTEGER,
            item_name TEXT,
            qty INTEGER NOT NULL DEFAULT 1,
            district_id INTEGER,
            district_name TEXT,
            amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'new',
            test_mode INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            expires_at INTEGER,
            accepted_by INTEGER,
            accepted_by_name TEXT,
            receipt_file_id TEXT,
            receipt_file_type TEXT,
            receipt_at INTEGER,
            paid_at INTEGER,
            sent_at INTEGER,
            closed_at INTEGER,
            cancelled_at INTEGER,
            cancel_reason TEXT DEFAULT '',
            admin_notes TEXT DEFAULT ''
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS digital_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            seq_no INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            file_unique_id TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'available',
            reserved_order_id INTEGER,
            delivered_order_id INTEGER,
            uploaded_by INTEGER,
            created_at INTEGER NOT NULL,
            reserved_at INTEGER,
            delivered_at INTEGER,
            last_error TEXT DEFAULT '',
            UNIQUE(item_id, seq_no),
            UNIQUE(file_unique_id)
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS payment_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_key TEXT NOT NULL UNIQUE,
            tx_hash TEXT DEFAULT '',
            wallet TEXT NOT NULL,
            sender TEXT DEFAULT '',
            amount_ton REAL NOT NULL,
            comment TEXT DEFAULT '',
            order_id INTEGER,
            detected_at INTEGER NOT NULL,
            raw_json TEXT DEFAULT ''
        )
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_digital_assets_queue
        ON digital_assets(item_id, status, seq_no)
        """)

        # Сначала добавляем недостающие столбцы в старую базу.
        # Индекс orders создаётся только ПОСЛЕ миграций, иначе SQLite падает
        # на старой таблице без wallet_used.
        # v3.2 migration: BTC hash auto-check fields
        existing_order_cols = {r["name"] for r in c.execute("PRAGMA table_info(orders)").fetchall()}
        order_migrations = {
            "tx_hash": "ALTER TABLE orders ADD COLUMN tx_hash TEXT DEFAULT ''",
            "tx_amount_sats": "ALTER TABLE orders ADD COLUMN tx_amount_sats INTEGER DEFAULT 0",
            "tx_confirmations": "ALTER TABLE orders ADD COLUMN tx_confirmations INTEGER DEFAULT 0",
            "tx_verified_at": "ALTER TABLE orders ADD COLUMN tx_verified_at INTEGER",
            "tx_check_result": "ALTER TABLE orders ADD COLUMN tx_check_result TEXT DEFAULT ''",
            "wallet_used": "ALTER TABLE orders ADD COLUMN wallet_used TEXT DEFAULT ''",
            "item_type_emoji": "ALTER TABLE orders ADD COLUMN item_type_emoji TEXT DEFAULT ''",
            "expected_ton": "ALTER TABLE orders ADD COLUMN expected_ton REAL DEFAULT 0",
            "payment_comment": "ALTER TABLE orders ADD COLUMN payment_comment TEXT DEFAULT ''",
            "auto_paid": "ALTER TABLE orders ADD COLUMN auto_paid INTEGER DEFAULT 0",
            "payment_tx_key": "ALTER TABLE orders ADD COLUMN payment_tx_key TEXT DEFAULT ''",
            "delivery_asset_id": "ALTER TABLE orders ADD COLUMN delivery_asset_id INTEGER",
            "delivered_at": "ALTER TABLE orders ADD COLUMN delivered_at INTEGER",
        }
        for col, ddl in order_migrations.items():
            if col not in existing_order_cols:
                c.execute(ddl)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_auto_payment
        ON orders(status, expires_at, wallet_used)
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS action_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            admin_id INTEGER,
            admin_name TEXT,
            action TEXT NOT NULL,
            target_type TEXT DEFAULT '',
            target_id TEXT DEFAULT '',
            details TEXT DEFAULT ''
        )
        """)

        defaults = {
            "bot_ready": "0",
            "orders_enabled": "0",
            "test_mode": "1",
            "service_mode": "0",
            "verified_only": "0",
            "daily_backup_enabled": "0",
            "last_backup_ts": "0",
            "auto_payment_enabled": "0",
            "ton_rub_rate": "0",
            "low_stock_threshold": "10",
            "digital_delivery_enabled": "1",
            "orders_chat_id": "",
            "project_name": "VELES MASTER HOUSE",
            "wallet_text": "",
            "ton_wallets_text": "",
            "btc_reserve_wallet_text": "",
            "seed_price": "0",
            "next_order_number": "1001",
            "btc_api_base": "https://blockstream.info/api",
            "btc_confirmations_required": "1",
            "btc_amount_check": "0",
            "welcome_photo_file_id": "",
            "payment_photo_file_id": "",
            "rules_photo_file_id": "",
            "shop_photo_file_id": "",
            "payment_help_text": PRETTY_PAYMENT_HELP_TEXT,
            "order_created_text": "🧾 Заказ создан. Проверьте сумму и TON / GRAM кошелёк, затем оплатите и отправьте чек.",
            "payment_confirmed_text": "✅ Оплата подтверждена. Заказ передан в работу.",
            "payment_rejected_text": "❌ Чек отклонён. Проверьте оплату и отправьте чек повторно.",
            "rules_text": PRETTY_RULES_TEXT,
            "client_rules_text": PRETTY_CLIENT_RULES_TEXT,
            "welcome_text": PRETTY_WELCOME_TEXT,
        }

        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (k, v))

        current_welcome = c.execute("SELECT value FROM settings WHERE key='welcome_text'").fetchone()
        current_rules = c.execute("SELECT value FROM settings WHERE key='rules_text'").fetchone()
        current_client_rules = c.execute("SELECT value FROM settings WHERE key='client_rules_text'").fetchone()
        if current_welcome and ("\\n" in current_welcome["value"] or "Выбери действие" in current_welcome["value"]):
            c.execute("UPDATE settings SET value=? WHERE key='welcome_text'", (PRETTY_WELCOME_TEXT,))
        if current_rules and ("\\n" in current_rules["value"] or "уважение, порядок, без спама" in current_rules["value"]):
            c.execute("UPDATE settings SET value=? WHERE key='rules_text'", (PRETTY_RULES_TEXT,))
        if current_client_rules and ("\\n" in current_client_rules["value"] or "Правила клиента VELES TRADE" in current_client_rules["value"]):
            c.execute("UPDATE settings SET value=? WHERE key='client_rules_text'", (PRETTY_CLIENT_RULES_TEXT,))
        current_payment_help = c.execute("SELECT value FROM settings WHERE key='payment_help_text'").fetchone()
        if current_payment_help and (
            "\\n" in current_payment_help["value"]
            or "hash / ссылка транзакции — пришлите" in current_payment_help["value"]
            or "КАК ОПЛАТИТЬ ЧЕРЕЗ X-ROCKET" in current_payment_help["value"]
            or "Bitcoin" in current_payment_help["value"]
            or "BTC" in current_payment_help["value"]
            or "КАК ОПЛАТИТЬ TON" in current_payment_help["value"]
            or "Как оплатить TON" in current_payment_help["value"]
            or "ВАРИАНТ 1 — X-ROCKET" in current_payment_help["value"]
            or "🚀 ВАРИАНТ 1 — X-ROCKET" in current_payment_help["value"]
        ):
            c.execute("UPDATE settings SET value=? WHERE key='payment_help_text'", (PRETTY_PAYMENT_HELP_TEXT,))

        for aid in ADMIN_IDS:
            c.execute(
                "INSERT OR IGNORE INTO admins(user_id, role, username, first_name, added_at) VALUES(?, 'owner', '', '', ?)",
                (aid, now_ts())
            )

        conn.commit()


def get_setting(key: str, default: str = "") -> str:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with db() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value))
        )
        conn.commit()


def bool_setting(key: str) -> bool:
    return get_setting(key, "0") == "1"


def seed_price() -> float:
    try:
        return float(get_setting("seed_price", "0"))
    except ValueError:
        return 0.0


def update_client(user):
    if not user:
        return
    with db() as conn:
        row = conn.execute("SELECT user_id FROM clients WHERE user_id=?", (user.id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE clients SET username=?, first_name=?, last_name=?, last_seen=? WHERE user_id=?",
                (user.username or "", user.first_name or "", user.last_name or "", now_ts(), user.id)
            )
        else:
            conn.execute(
                """INSERT INTO clients(user_id, username, first_name, last_name, first_seen, last_seen)
                   VALUES(?, ?, ?, ?, ?, ?)""",
                (user.id, user.username or "", user.first_name or "", user.last_name or "", now_ts(), now_ts())
            )
        conn.commit()


def get_client(user_id: int):
    with db() as conn:
        return conn.execute("SELECT * FROM clients WHERE user_id=?", (user_id,)).fetchone()


def is_admin_id(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    with db() as conn:
        row = conn.execute("SELECT user_id FROM admins WHERE user_id=?", (user_id,)).fetchone()
        return bool(row)


def admin_role(user_id: int) -> str | None:
    if user_id in ADMIN_IDS:
        return "owner"
    with db() as conn:
        row = conn.execute("SELECT role FROM admins WHERE user_id=?", (user_id,)).fetchone()
        return row["role"] if row else None


def has_perm(user_id: int, level: str = "operator") -> bool:
    role = admin_role(user_id)
    if not role:
        return False
    order = {"operator": 1, "admin": 2, "owner": 3}
    return order.get(role, 0) >= order.get(level, 1)


def admin_name(user) -> str:
    if not user:
        return "—"
    if user.username:
        return f"@{user.username}"
    return user.first_name or str(user.id)


def log_action(user, action: str, target_type: str = "", target_id: str = "", details: str = ""):
    with db() as conn:
        conn.execute(
            """INSERT INTO action_logs(ts, admin_id, admin_name, action, target_type, target_id, details)
               VALUES(?, ?, ?, ?, ?, ?, ?)""",
            (now_ts(), user.id if user else None, admin_name(user), action, target_type, str(target_id), details)
        )
        conn.commit()


# =========================
# TEXT HELPERS
# =========================

def mention_text(user_id: int, username: str = "", first_name: str = "") -> str:
    if username:
        return f"@{username}"
    return first_name or f"ID {user_id}"


def vip_status(purchases: int) -> str:
    for need, name in VIP_STATUSES:
        if purchases >= need:
            return name
    return "🌿 Гость Дома"


def next_vip_text(purchases: int) -> str:
    for need, name in sorted(VIP_STATUSES, key=lambda x: x[0]):
        if need > purchases:
            return f"До следующего статуса: {need - purchases} покупок → {name}"
    return "Максимальный статус Дома достигнут."


def status_name(status: str) -> str:
    return ORDER_STATUS.get(status, status)


def order_text(order) -> str:
    user = mention_text(order["user_id"], order["username"], "")
    test = "🧪 ТЕСТОВЫЙ ЗАКАЗ\n" if order["test_mode"] else ""
    tx_hash = row_get(order, "tx_hash", "") or ""
    tx_block = ""
    if tx_hash:
        tx_block = f"\n\n⛓ TON hash / ссылка транзакции: {tx_hash}"
    wallet = row_get(order, "wallet_used", "") or choose_ton_wallet(order["order_no"])
    wallet_short = wallet if len(wallet) <= 70 else wallet[:32] + "..." + wallet[-18:]
    return (
        f"{test}🧾 Заказ {order['order_no']}\n\n"
        f"👤 Клиент: {user}\n"
        f"🌰 Позиция: {((row_get(order, 'item_type_emoji', '') or '') + ' ' + order['item_name']).strip()}\n"
        f"🔢 Количество: {order['qty']} {seed_word(order['qty'])}\n"
        f"📍 Район: {order['district_name'] or '—'}\n"
        f"💰 Сумма: {order['amount']:g} ₽\n"
        f"💼 Кошелёк: {wallet_short or '—'}\n"
        f"📌 Статус: {status_name(order['status'])}\n"
        f"👀 Принял: {order['accepted_by_name'] or '—'}\n"
        f"🕒 Создан: {fmt_dt(order['created_at'])}\n"
        f"⏳ Оплата до: {fmt_dt(order['expires_at']) if order['expires_at'] else '—'}"
        f"{tx_block}"
    )


def client_card_text(user_id: int) -> str:
    client = get_client(user_id)
    if not client:
        return f"📋 Клиент ID {user_id}\nНе найден в базе."

    with db() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM orders WHERE user_id=?", (user_id,)).fetchone()["c"]
        active = conn.execute(
            f"SELECT COUNT(*) c FROM orders WHERE user_id=? AND status NOT IN ({','.join(['?']*len(TERMINAL_STATUSES))})",
            (user_id, *TERMINAL_STATUSES)
        ).fetchone()["c"]
        closed = conn.execute("SELECT COUNT(*) c FROM orders WHERE user_id=? AND status='closed'", (user_id,)).fetchone()["c"]
        cancelled = conn.execute("SELECT COUNT(*) c FROM orders WHERE user_id=? AND status IN ('cancelled','expired')", (user_id,)).fetchone()["c"]
        last_orders = conn.execute(
            "SELECT order_no, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5",
            (user_id,)
        ).fetchall()

    name = mention_text(client["user_id"], client["username"], client["first_name"])
    banned_until = int(client["order_banned_until"] or 0)
    ban_text = "нет"
    if banned_until > now_ts():
        ban_text = f"до {fmt_dt(banned_until)} — {client['order_ban_reason'] or 'без причины'}"

    lines = [
        f"📋 Клиент: {name}",
        f"🆔 ID: {client['user_id']}",
        f"📦 Покупок: {client['purchases']}",
        f"🏅 Статус: {vip_status(client['purchases'])}",
        f"🧾 Всего заказов: {total}",
        f"🔥 Активных: {active}",
        f"✅ Закрыто: {closed}",
        f"❌ Отменено/просрочено: {cancelled}",
        f"🚫 Стоп-лист: {ban_text}",
        f"📝 Заметка: {client['notes'] or '—'}",
        "",
        "История:",
    ]
    if not last_orders:
        lines.append("— заказов ещё нет")
    else:
        for o in last_orders:
            lines.append(f"{o['order_no']} — {status_name(o['status'])} — {fmt_dt(o['created_at'])}")

    return "\n".join(lines)


def seed_word(qty: int) -> str:
    if qty == 1:
        return "шт."
    if qty in (2, 3):
        return "шт."
    return "шт."


def store_status_label(status: str) -> str:
    return {
        "in_stock": "✅ В наличии",
        "soon": "⏳ Скоро",
        "hidden": "❌ Скрыто",
        "hot": "🔥 Горячее",
        "recommended": "⭐ Рекомендуем",
    }.get(status, status)


def payment_help_text() -> str:
    return get_setting("payment_help_text", "🚀 Инструкция оплаты пока не задана.")


def ton_rub_rate() -> float:
    try:
        return float(get_setting("ton_rub_rate", "0") or 0)
    except Exception:
        return 0.0


def expected_ton_for_rub(amount_rub: float) -> float:
    rate = ton_rub_rate()
    if rate <= 0:
        return 0.0
    return round(float(amount_rub) / rate, 4)


def ton_transfer_url(wallet: str, amount_ton: float, comment: str) -> str:
    wallet = (wallet or "").strip()
    if not wallet:
        return ""
    amount_nano = max(0, int(round(float(amount_ton) * 1_000_000_000)))
    params = urllib.parse.urlencode({"amount": amount_nano, "text": comment or ""})
    return f"ton://transfer/{wallet}?{params}"


def digital_stock_counts(item_id: int) -> dict:
    with db() as conn:
        row = conn.execute(
            """
            SELECT
              COUNT(*) total,
              SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) available,
              SUM(CASE WHEN status='reserved' THEN 1 ELSE 0 END) reserved,
              SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END) delivered
            FROM digital_assets WHERE item_id=?
            """,
            (item_id,)
        ).fetchone()
    return {
        "total": int(row["total"] or 0),
        "available": int(row["available"] or 0),
        "reserved": int(row["reserved"] or 0),
        "delivered": int(row["delivered"] or 0),
    }


def digital_delivery_menu_keyboard():
    return kb([
        [InlineKeyboardButton("📤 Загрузить фото", callback_data="digital_choose_upload")],
        [InlineKeyboardButton("📊 Остатки", callback_data="digital_stock")],
        [InlineKeyboardButton("📋 История выдачи", callback_data="digital_history")],
        [InlineKeyboardButton("⚙️ Автооплата", callback_data="auto_payment_menu")],
        [InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")],
    ])


def auto_payment_status_text() -> str:
    enabled = bool_setting("auto_payment_enabled")
    api = "✅ API key есть — расширенный лимит" if TONCENTER_API_KEY else "🟢 API key не нужен — публичный TON Center"
    rate = ton_rub_rate()
    wallets = len(ton_wallets_list())
    return (
        "⚡ Автоматическая оплата TON / GRAM\n\n"
        f"Статус: {'🟢 включена' if enabled else '🔴 выключена'}\n"
        f"{api}\n"
        f"Курс: 1 TON = {rate:g} ₽\n"
        f"Кошельков: {wallets}\n"
        f"Проверка каждые: {TON_PAYMENT_POLL_SECONDS} сек.\n\n"
        "Оплата находится по трём признакам:\n"
        "1. нужный кошелёк;\n"
        "2. memo с номером заказа;\n"
        "3. сумма TON с допустимым отклонением.\n\n"
        "После подтверждения бот сам выдаёт следующее фото позиции."
    )


def auto_payment_keyboard():
    enabled = bool_setting("auto_payment_enabled")
    return kb([
        [InlineKeyboardButton("🔴 Выключить" if enabled else "🟢 Включить", callback_data="auto_payment_toggle")],
        [InlineKeyboardButton("💱 Указать курс TON/₽", callback_data="auto_payment_rate")],
        [InlineKeyboardButton("🧪 Проверить сейчас", callback_data="auto_payment_check_now")],
        [InlineKeyboardButton("⬅️ Цифровая выдача", callback_data="digital_menu")],
    ])


def _fetch_ton_transactions_sync(wallet: str) -> list:
    query = {
        "address": wallet,
        "limit": 50,
        "archival": "true",
    }
    if TONCENTER_API_KEY:
        query["api_key"] = TONCENTER_API_KEY
    url = f"{TONCENTER_API_BASE}/getTransactions?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "VELES-BOT/7.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(payload.get("error") or "TON Center вернул ошибку")
    return payload.get("result") or []


async def fetch_ton_transactions(wallet: str) -> list:
    return await asyncio.to_thread(_fetch_ton_transactions_sync, wallet)


def parse_ton_incoming(tx: dict, wallet: str) -> dict | None:
    incoming = tx.get("in_msg") or {}
    value_raw = incoming.get("value")
    try:
        amount = int(value_raw or 0) / 1_000_000_000
    except Exception:
        return None
    if amount <= 0:
        return None
    comment = (
        incoming.get("message")
        or incoming.get("msg_data", {}).get("text")
        or ""
    )
    sender = incoming.get("source") or ""
    tx_hash = (
        tx.get("transaction_id", {}).get("hash")
        or tx.get("hash")
        or ""
    )
    lt = str(tx.get("transaction_id", {}).get("lt") or tx.get("lt") or "")
    tx_key = tx_hash or hashlib.sha256(
        f"{wallet}|{lt}|{sender}|{amount}|{comment}".encode("utf-8")
    ).hexdigest()
    return {
        "tx_key": tx_key,
        "tx_hash": tx_hash,
        "wallet": wallet,
        "sender": sender,
        "amount_ton": amount,
        "comment": str(comment or "").strip(),
        "raw_json": json.dumps(tx, ensure_ascii=False)[:12000],
    }


async def notify_low_stock(context, item_id: int):
    counts = digital_stock_counts(item_id)
    threshold = int(get_setting("low_stock_threshold", str(LOW_STOCK_THRESHOLD)) or LOW_STOCK_THRESHOLD)
    if counts["available"] > threshold:
        return
    with db() as conn:
        item = conn.execute("SELECT name FROM items WHERE id=?", (item_id,)).fetchone()
    chat_id = get_setting("orders_chat_id")
    if chat_id and item:
        try:
            await context.bot.send_message(
                chat_id=int(chat_id),
                text=f"⚠️ Низкий остаток цифрового склада\n\n{item['name']}\nОсталось: {counts['available']} фото"
            )
        except Exception:
            logging.exception("Не смог отправить low stock уведомление")


async def fulfill_digital_order(context, order_id: int, source: str = "auto") -> tuple[bool, str]:
    """
    Атомарная резервировка следующего фото конкретной позиции.
    Одна позиция = независимая очередь.
    """
    asset = None
    order = None
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            conn.rollback()
            return False, "Заказ не найден"
        if row_get(order, "delivery_asset_id"):
            conn.rollback()
            return True, "Уже выдано"
        asset = conn.execute(
            """
            SELECT * FROM digital_assets
            WHERE item_id=? AND status='available'
            ORDER BY seq_no ASC, id ASC
            LIMIT 1
            """,
            (order["item_id"],)
        ).fetchone()
        if not asset:
            conn.rollback()
            return False, "Фото закончились"
        now = now_ts()
        updated = conn.execute(
            """
            UPDATE digital_assets
            SET status='reserved', reserved_order_id=?, reserved_at=?, last_error=''
            WHERE id=? AND status='available'
            """,
            (order_id, now, asset["id"])
        ).rowcount
        if updated != 1:
            conn.rollback()
            return False, "Очередь занята, повтори"
        conn.commit()

    try:
        caption = (
            f"✅ Оплата подтверждена\n\n"
            f"🧾 Заказ: {order['order_no']}\n"
            f"📦 {order['item_name']}\n\n"
            f"Ваша выдача готова."
        )
        await context.bot.send_photo(
            chat_id=order["user_id"],
            photo=asset["file_id"],
            caption=caption,
            protect_content=True,
        )
    except Exception as exc:
        with db() as conn:
            conn.execute(
                """
                UPDATE digital_assets
                SET status='available', reserved_order_id=NULL, reserved_at=NULL, last_error=?
                WHERE id=? AND status='reserved' AND reserved_order_id=?
                """,
                (str(exc)[:500], asset["id"], order_id)
            )
            conn.commit()
        logging.exception("Ошибка цифровой выдачи")
        return False, f"Telegram не отправил фото: {exc}"

    now = now_ts()
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not row_get(current, "delivery_asset_id"):
            conn.execute(
                """
                UPDATE digital_assets
                SET status='delivered', delivered_order_id=?, delivered_at=?
                WHERE id=? AND status='reserved' AND reserved_order_id=?
                """,
                (order_id, now, asset["id"], order_id)
            )
            conn.execute(
                """
                UPDATE orders
                SET status='closed', updated_at=?, closed_at=?, delivered_at=?, delivery_asset_id=?
                WHERE id=?
                """,
                (now, now, now, asset["id"], order_id)
            )
            conn.execute("UPDATE clients SET purchases=purchases+1 WHERE user_id=?", (order["user_id"],))
            item = conn.execute("SELECT * FROM items WHERE id=?", (order["item_id"],)).fetchone()
            if item and item["stock"] is not None:
                new_stock = max(0, int(item["stock"]) - int(order["qty"]))
                conn.execute(
                    "UPDATE items SET stock=?, updated_at=? WHERE id=?",
                    (new_stock, now, item["id"])
                )
        conn.commit()

    await notify_low_stock(context, order["item_id"])
    chat_id = get_setting("orders_chat_id")
    if chat_id:
        try:
            await context.bot.send_message(
                chat_id=int(chat_id),
                text=(
                    f"🤖 Автовыдача завершена\n\n"
                    f"Заказ: {order['order_no']}\n"
                    f"Фото склада: #{asset['seq_no']}\n"
                    f"Источник оплаты: {source}"
                )
            )
        except Exception:
            logging.exception("Не смог уведомить админов об автовыдаче")
    return True, f"Выдано фото #{asset['seq_no']}"


async def process_detected_payment(context, tx: dict) -> bool:
    comment = tx["comment"]
    match = re.search(r"\bVT-\d+\b", comment.upper())
    if not match:
        return False
    order_no = match.group(0)
    with db() as conn:
        if conn.execute("SELECT 1 FROM payment_transactions WHERE tx_key=?", (tx["tx_key"],)).fetchone():
            return False
        order = conn.execute(
            """
            SELECT * FROM orders
            WHERE UPPER(order_no)=?
              AND status IN ('awaiting_payment','receipt_sent','tx_wait')
            """,
            (order_no,)
        ).fetchone()
        if not order:
            return False
        expected = float(row_get(order, "expected_ton", 0) or 0)
        if expected <= 0:
            return False
        if (order["wallet_used"] or "").strip() != tx["wallet"].strip():
            return False
        if tx["amount_ton"] + TON_PAYMENT_TOLERANCE < expected:
            return False

        now = now_ts()
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM payment_transactions WHERE tx_key=?", (tx["tx_key"],)).fetchone():
            conn.rollback()
            return False
        conn.execute(
            """
            INSERT INTO payment_transactions(
              tx_key, tx_hash, wallet, sender, amount_ton, comment,
              order_id, detected_at, raw_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx["tx_key"], tx["tx_hash"], tx["wallet"], tx["sender"],
                tx["amount_ton"], tx["comment"], order["id"], now, tx["raw_json"]
            )
        )
        conn.execute(
            """
            UPDATE orders
            SET status='paid', paid_at=?, updated_at=?, auto_paid=1,
                payment_tx_key=?, tx_hash=?, tx_check_result='TON auto verified'
            WHERE id=? AND status IN ('awaiting_payment','receipt_sent','tx_wait')
            """,
            (now, now, tx["tx_key"], tx["tx_hash"], order["id"])
        )
        conn.commit()

    ok, message = await fulfill_digital_order(context, order["id"], source="TON auto")
    if not ok:
        chat_id = get_setting("orders_chat_id")
        if chat_id:
            await context.bot.send_message(
                chat_id=int(chat_id),
                text=f"⚠️ Оплата найдена, но выдача не выполнена\n\n{order_no}\nПричина: {message}"
            )
    return True


async def check_ton_payments_once(context) -> int:
    if not bool_setting("auto_payment_enabled"):
        return 0
    if ton_rub_rate() <= 0:
        return 0

    processed = 0
    wallets = ton_wallets_list()
    for wallet_raw in wallets:
        wallet = wallet_raw.split()[-1].strip()
        try:
            transactions = await fetch_ton_transactions(wallet)
            for raw in transactions:
                tx = parse_ton_incoming(raw, wallet_raw)
                if tx and await process_detected_payment(context, tx):
                    processed += 1
        except Exception:
            logging.exception("TON payment poll failed for wallet %s", wallet_raw)
    return processed


async def ton_payment_worker(app):
    await asyncio.sleep(5)
    while True:
        try:
            await check_ton_payments_once(app)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("TON payment worker error")
        await asyncio.sleep(TON_PAYMENT_POLL_SECONDS)


async def post_init_v7(app):
    app.bot_data["ton_payment_task"] = asyncio.create_task(ton_payment_worker(app))


def normalize_wallet_line(text: str) -> str:
    return (text or "").strip()


def ton_wallets_list() -> list[str]:
    wallets = []
    primary = normalize_wallet_line(get_setting("wallet_text", ""))
    if primary:
        wallets.append(primary)
    extra = get_setting("ton_wallets_text", "")
    for line in extra.splitlines():
        w = normalize_wallet_line(line)
        if w and w not in wallets:
            wallets.append(w)
    return wallets


def save_ton_wallets(wallets: list[str]):
    clean = []
    for w in wallets:
        w = normalize_wallet_line(w)
        if w and w not in clean:
            clean.append(w)
    primary = clean[0] if clean else ""
    rest = "\n".join(clean[1:])
    set_setting("wallet_text", primary)
    set_setting("ton_wallets_text", rest)


def add_ton_wallet(wallet: str):
    wallets = ton_wallets_list()
    wallet = normalize_wallet_line(wallet)
    if wallet and wallet not in wallets:
        wallets.append(wallet)
    save_ton_wallets(wallets)
    return wallets


def choose_ton_wallet(order_no: str = "") -> str:
    wallets = ton_wallets_list()
    if not wallets:
        return ""
    digits = "".join(ch for ch in (order_no or "") if ch.isdigit())
    try:
        idx = int(digits) % len(wallets)
    except Exception:
        idx = 0
    return wallets[idx]


def payment_wallets_text_admin() -> str:
    wallets = ton_wallets_list()
    btc_reserve = get_setting("btc_reserve_wallet_text", "")
    text = "💳 Оплата\n\nОсновная валюта: TON / GRAM\nBTC: только резерв через администратора\n\n"
    if wallets:
        text += "💼 TON / GRAM кошельки:\n"
        for i, w in enumerate(wallets, 1):
            short = w if len(w) <= 70 else w[:32] + "..." + w[-18:]
            text += f"{i}. {short}\n"
    else:
        text += "❌ TON / GRAM кошельки не добавлены.\n"
    text += f"\n🪙 BTC резерв: {'указан' if btc_reserve else 'не указан'}\n"
    text += f"💰 Цена за 1 шт.: {seed_price():g} ₽"
    return text


def payment_wallets_keyboard():
    return kb([
        [InlineKeyboardButton("➕ Добавить TON / GRAM кошелёк", callback_data="wallet_add")],
        [InlineKeyboardButton("📋 Список TON / GRAM кошельков", callback_data="wallets_list"), InlineKeyboardButton("🧹 Очистить TON", callback_data="wallets_clear_prompt")],
        [InlineKeyboardButton("🪙 BTC резерв", callback_data="btc_reserve_set"), InlineKeyboardButton("📋 Показать BTC резерв", callback_data="btc_reserve_show")],
        [InlineKeyboardButton("💰 Изменить цену", callback_data="setup_price")],
        [InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")]
    ])


def make_wallet_qr_bytes(wallet_text: str):
    if not QR_AVAILABLE or not wallet_text:
        return None
    try:
        img = qrcode.make(wallet_text)
        bio = BytesIO()
        bio.name = "payment_wallet_qr.png"
        img.save(bio, format="PNG")
        bio.seek(0)
        return bio
    except Exception:
        logging.exception("Не смог создать QR-код")
        return None


def row_get(row, key: str, default=None):
    try:
        return row[key]
    except Exception:
        return default


def money(value) -> str:
    try:
        amount = float(value)
        return f"{amount:g} ₽"
    except Exception:
        return f"{value} ₽"


def item_type_links(item_id: int, only_enabled: bool = False):
    try:
        with db() as conn:
            where = "WHERE l.item_id=?"
            params = [item_id]
            if only_enabled:
                where += " AND l.enabled=1"
            return conn.execute(
                f"""
                SELECT t.id, t.emoji, l.enabled
                FROM item_type_links l
                JOIN item_types t ON t.id = l.type_id
                {where}
                ORDER BY t.id DESC
                """,
                params
            ).fetchall()
    except Exception:
        return []


def item_type_raw_emoji(row) -> str:
    # Старая совместимость: если у позиции ещё нет связей, берём старый type_emoji.
    links = item_type_links(row["id"], only_enabled=False) if row_get(row, "id", None) is not None else []
    if links:
        return " ".join([r["emoji"] for r in links])
    return (row_get(row, "type_emoji", "") or "").strip()


def item_type_enabled(row) -> bool:
    try:
        return int(row_get(row, "type_enabled", 1) or 0) == 1
    except Exception:
        return True


def item_type_emoji(row) -> str:
    links = item_type_links(row["id"], only_enabled=True) if row_get(row, "id", None) is not None else []
    if links:
        return " ".join([r["emoji"] for r in links])
    emoji = (row_get(row, "type_emoji", "") or "").strip()
    return emoji if emoji and item_type_enabled(row) else ""


def item_display_name(row) -> str:
    emoji = item_type_emoji(row)
    name = row["name"]
    return f"{emoji} {name}".strip() if emoji else name


def item_type_status_line(item_id: int) -> str:
    links = item_type_links(item_id, only_enabled=False)
    if not links:
        return "—"
    parts = []
    for r in links:
        parts.append(f"{r['emoji']} {'вкл' if int(r['enabled']) == 1 else 'выкл'}")
    return ", ".join(parts)


def btc_api_base() -> str:
    return get_setting("btc_api_base", "https://blockstream.info/api").rstrip("/")


def btc_confirmations_required() -> int:
    try:
        return max(0, int(get_setting("btc_confirmations_required", "1")))
    except ValueError:
        return 1


def extract_btc_address(wallet_text: str) -> str:
    """Pull a BTC address from a wallet label like 'TON: bc1...'."""
    if not wallet_text:
        return ""
    candidates = re.findall(
        r"(bc1[a-zA-Z0-9]{20,90}|tb1[a-zA-Z0-9]{20,90}|[13][a-km-zA-HJ-NP-Z1-9]{25,40}|[mn2][a-km-zA-HJ-NP-Z1-9]{25,60})",
        wallet_text,
    )
    return candidates[0] if candidates else wallet_text.strip()


def is_tx_hash(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", (value or "").strip()))


def fetch_json_url(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "VELES-TRADE-BOT/3.2"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def fetch_text_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "VELES-TRADE-BOT/3.2"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8").strip()


def btc_tx_check(tx_hash: str, wallet_text: str) -> dict:
    """Check BTC hash via Esplora-compatible API.

    Returns:
    {
      ok: bool,
      reason: str,
      address: str,
      amount_sats: int,
      amount_btc: float,
      confirmations: int,
      confirmed: bool,
      tx_hash: str
    }
    """
    tx_hash = (tx_hash or "").strip()
    if not is_tx_hash(tx_hash):
        return {"ok": False, "reason": "hash должен быть 64 символа HEX.", "tx_hash": tx_hash}

    address = extract_btc_address(wallet_text)
    if not address:
        return {"ok": False, "reason": "TON / GRAM адрес не найден в настройке кошелька.", "tx_hash": tx_hash}

    base = btc_api_base()
    try:
        tx = fetch_json_url(f"{base}/tx/{tx_hash}")
    except urllib.error.HTTPError as e:
        if getattr(e, "code", None) == 404:
            return {"ok": False, "reason": "Транзакция не найдена в блокчейне.", "tx_hash": tx_hash, "address": address}
        return {"ok": False, "reason": f"Ошибка API проверки hash: HTTP {getattr(e, 'code', '')}", "tx_hash": tx_hash, "address": address}
    except Exception as e:
        return {"ok": False, "reason": f"Ошибка API проверки hash: {e}", "tx_hash": tx_hash, "address": address}

    amount_sats = 0
    for vout in tx.get("vout", []):
        if vout.get("scriptpubkey_address") == address:
            try:
                amount_sats += int(vout.get("value", 0))
            except Exception:
                pass

    if amount_sats <= 0:
        return {
            "ok": False,
            "reason": "В этой транзакции нет выхода на наш TON / GRAM кошелёк.",
            "tx_hash": tx_hash,
            "address": address,
            "amount_sats": 0,
            "amount_btc": 0,
            "confirmations": 0,
            "confirmed": False,
        }

    status = tx.get("status", {}) or {}
    confirmed = bool(status.get("confirmed"))
    confirmations = 0
    if confirmed and status.get("block_height"):
        try:
            tip_height = int(fetch_text_url(f"{base}/blocks/tip/height"))
            confirmations = max(0, tip_height - int(status["block_height"]) + 1)
        except Exception:
            confirmations = 1

    return {
        "ok": True,
        "reason": "Оплата найдена.",
        "tx_hash": tx_hash,
        "address": address,
        "amount_sats": amount_sats,
        "amount_btc": amount_sats / 100_000_000,
        "confirmations": confirmations,
        "confirmed": confirmed,
    }


def tx_result_text(result: dict) -> str:
    if not result.get("ok"):
        return f"❌ hash не прошёл проверку: {result.get('reason', 'ошибка')}"
    req = btc_confirmations_required()
    conf = int(result.get("confirmations", 0))
    amount_btc = result.get("amount_btc", 0)
    if conf >= req:
        status = "✅ подтверждена"
    else:
        status = f"⏳ ждём подтверждения {conf}/{req}"
    return (
        f"⛓ TON / GRAM проверка: {status}\n"
        f"hash: {result.get('tx_hash')}\n"
        f"Получено: {amount_btc:.8f} BTC\n"
        f"Подтверждений: {conf}/{req}"
    )


# =========================
# KEYBOARDS
# =========================

def nav_keyboard(back_cb: str = "main_menu", admin: bool = False):
    rows = [[InlineKeyboardButton("⬅️ Назад", callback_data=back_cb)]]
    if admin:
        rows.append([InlineKeyboardButton("⚜️ Админ-меню", callback_data="admin_menu")])
    rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    return kb(rows)


def back_admin_keyboard():
    return kb([
        [InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ])


def setup_back_keyboard():
    return kb([
        [InlineKeyboardButton("⬅️ Setup", callback_data="admin_setup")],
        [InlineKeyboardButton("⚜️ Админ-меню", callback_data="admin_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ])


def kb(rows):
    return InlineKeyboardMarkup(rows)


def main_menu_keyboard(is_admin: bool = False):
    rows = [
        [InlineKeyboardButton("🛒 Витрина", callback_data="shop")],
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders"), InlineKeyboardButton("🏅 Мой статус", callback_data="my_vip")],
        [InlineKeyboardButton("📜 Правила", callback_data="rules"), InlineKeyboardButton("📜 Правила клиентов", callback_data="client_rules")],
        [InlineKeyboardButton("🚀 Как оплатить", callback_data="payment_help")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("⚜️ Админ-меню", callback_data="admin_menu")])
    return kb(rows)


def admin_menu_keyboard():
    orders_enabled = bool_setting("orders_enabled")
    pause_label = "🛑 СТОП ЗАКАЗЫ" if orders_enabled else "▶️ ВКЛЮЧИТЬ ЗАКАЗЫ"
    service_label = "🔧 Выкл. обслуживание" if bool_setting("service_mode") else "🔧 Режим обслуживания"
    return kb([
        [InlineKeyboardButton("🧰 Мастер настройки", callback_data="admin_setup"), InlineKeyboardButton("🩺 Проверка системы", callback_data="admin_ready_check")],
        [InlineKeyboardButton("🧾 Заказы", callback_data="admin_orders"), InlineKeyboardButton("📎 Чеки", callback_data="admin_receipts")],
        [InlineKeyboardButton("🛒 Витрина", callback_data="admin_shop"), InlineKeyboardButton("📦 Склад", callback_data="stock_menu")],
        [InlineKeyboardButton("🤖 Автооплата + выдача", callback_data="digital_menu")],
        [InlineKeyboardButton("📍 Районы", callback_data="admin_districts"), InlineKeyboardButton("👥 Клиенты", callback_data="admin_clients")],
        [InlineKeyboardButton("👑 Админы", callback_data="admins_menu"), InlineKeyboardButton("💳 Оплата", callback_data="admin_payment")],
        [InlineKeyboardButton("📜 Тексты", callback_data="texts_menu"), InlineKeyboardButton("🖼 Картинки", callback_data="pictures_menu")],
        [InlineKeyboardButton("📣 Рассылка", callback_data="broadcast_menu"), InlineKeyboardButton("📊 Отчёты", callback_data="reports_menu")],
        [InlineKeyboardButton("🛡 Безопасность", callback_data="security_menu"), InlineKeyboardButton("🧱 Backup / Restore", callback_data="backup_menu")],
        [InlineKeyboardButton(pause_label, callback_data="admin_toggle_orders"), InlineKeyboardButton(service_label, callback_data="toggle_service_mode")],
        [InlineKeyboardButton("🧪 Тестовый режим", callback_data="admin_toggle_test"), InlineKeyboardButton("🧾 Лог", callback_data="admin_logs")],
        [InlineKeyboardButton("⚙️ Система", callback_data="system_menu"), InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
    ])


def setup_keyboard():
    return kb([
        [InlineKeyboardButton("💳 Указать кошелёк", callback_data="setup_wallet"), InlineKeyboardButton("💰 Цена за 1 шт.", callback_data="setup_price")],
        [InlineKeyboardButton("📍 Добавить район", callback_data="district_add"), InlineKeyboardButton("🛒 Добавить позицию", callback_data="item_add")],
        [InlineKeyboardButton("👥 Назначить группу заявок", callback_data="setup_orders_chat_help")],
        [InlineKeyboardButton("✅ Проверить готовность", callback_data="admin_ready_check")],
        [InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")],
    ])


def order_admin_keyboard(order_id: int, user_id: int, status: str):
    rows = [
        [InlineKeyboardButton("👀 Принять", callback_data=f"order_accept:{order_id}"), InlineKeyboardButton("✅ Оплата получена", callback_data=f"order_payment_ok:{order_id}")],
        [InlineKeyboardButton("📦 В работу", callback_data=f"order_work:{order_id}"), InlineKeyboardButton("🚚 Передан", callback_data=f"order_sent:{order_id}")],
        [InlineKeyboardButton("✅ Закрыть + покупка", callback_data=f"order_close:{order_id}")],
        [InlineKeyboardButton("⛓ Данные оплаты", callback_data=f"tx_check:{order_id}"), InlineKeyboardButton("📎 Показать чек", callback_data=f"receipt_show:{order_id}")],
        [InlineKeyboardButton("✉️ Шаблоны", callback_data=f"order_templates:{order_id}"), InlineKeyboardButton("💰 Изменить сумму", callback_data=f"order_change_amount:{order_id}")],
        [InlineKeyboardButton("❌ Отменить", callback_data=f"order_cancel_admin:{order_id}"), InlineKeyboardButton("❌ Отклонить чек", callback_data=f"receipt_reject:{order_id}")],
        [InlineKeyboardButton("💬 Написать клиенту", url=f"tg://user?id={user_id}"), InlineKeyboardButton("📋 Карточка клиента", callback_data=f"client_card:{user_id}")],
    ]
    return kb(rows)


def payment_keyboard(order_id: int):
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    rows = []
    if order:
        url = ton_transfer_url(
            row_get(order, "wallet_used", "") or "",
            float(row_get(order, "expected_ton", 0) or 0),
            row_get(order, "payment_comment", "") or order["order_no"]
        )
        if url:
            rows.append([InlineKeyboardButton("🚀 ОПЛАТИТЬ TON / GRAM", url=url)])
    rows.extend([
        [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"client_check_payment:{order_id}")],
        [InlineKeyboardButton("✅ Я оплатил / отправить чек", callback_data=f"client_paid:{order_id}")],
        [InlineKeyboardButton("🚀 Как оплатить", callback_data="payment_help"), InlineKeyboardButton("📋 Кошелёк текстом", callback_data=f"wallet_text_show:{order_id}")],
        [InlineKeyboardButton("❌ Отменить заказ", callback_data=f"client_cancel_order:{order_id}")],
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
    ])
    return kb(rows)


def client_order_keyboard(order_id: int, status: str):
    rows = []
    if status in CLIENT_CANCEL_ALLOWED:
        rows.append([InlineKeyboardButton("❌ Отменить заказ", callback_data=f"client_cancel_order:{order_id}")])
    rows.append([InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")])
    rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    return kb(rows)


# =========================
# READINESS / LIMITS
# =========================

def readiness_report() -> tuple[bool, str]:
    missing = []
    if not get_setting("orders_chat_id"):
        missing.append("❌ группа заявок не назначена")
    if not ton_wallets_list():
        missing.append("❌ TON / GRAM кошелёк не указан")
    if seed_price() <= 0:
        missing.append("❌ цена за 1 шт. не указана")

    with db() as conn:
        districts = conn.execute("SELECT COUNT(*) c FROM districts WHERE enabled=1").fetchone()["c"]
        items = conn.execute("SELECT COUNT(*) c FROM items WHERE status IN ('in_stock','hot','recommended')").fetchone()["c"]

    if districts <= 0:
        missing.append("❌ нет активных районов")
    if items <= 0:
        missing.append("❌ нет активных позиций витрины")

    ready = not missing
    text = "✅ Бот готов принимать заказы." if ready else "⚙️ Бот ещё не готов.\n\nНе хватает:\n" + "\n".join(missing)
    return ready, text


def expire_orders():
    now = now_ts()
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE status='awaiting_payment' AND expires_at IS NOT NULL AND expires_at < ?",
            (now,)
        ).fetchall()
        for r in rows:
            conn.execute(
                "UPDATE orders SET status='expired', updated_at=?, cancelled_at=?, cancel_reason=? WHERE id=?",
                (now, now, "Автоотмена: истекло время оплаты", r["id"])
            )
            conn.execute(
                """INSERT INTO action_logs(ts, admin_id, admin_name, action, target_type, target_id, details)
                   VALUES(?, NULL, 'SYSTEM', 'auto_expire_order', 'order', ?, ?)""",
                (now, r["order_no"], "Истекло время оплаты")
            )
        conn.commit()
    return rows


def can_create_order(user_id: int) -> tuple[bool, str]:
    client = get_client(user_id)
    now = now_ts()
    if client and int(client["order_banned_until"] or 0) > now:
        return False, f"🚫 Заявки временно закрыты до {fmt_dt(client['order_banned_until'])}.\nПричина: {client['order_ban_reason'] or 'ограничение'}"

    with db() as conn:
        active = conn.execute(
            f"SELECT COUNT(*) c FROM orders WHERE user_id=? AND status NOT IN ({','.join(['?']*len(TERMINAL_STATUSES))})",
            (user_id, *TERMINAL_STATUSES)
        ).fetchone()["c"]
        if active >= ORDER_ACTIVE_LIMIT:
            return False, "⚠️ У тебя уже есть активный заказ. Закрой или отмени его перед новым."

        since_day = now - 86400
        daily = conn.execute(
            "SELECT COUNT(*) c FROM orders WHERE user_id=? AND created_at>=?",
            (user_id, since_day)
        ).fetchone()["c"]
        if daily >= ORDER_DAILY_LIMIT:
            return False, f"⚠️ Лимит заявок на сегодня исчерпан: {ORDER_DAILY_LIMIT} заявок в сутки."

        last = conn.execute(
            "SELECT created_at FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        if last and now - int(last["created_at"]) < ORDER_COOLDOWN_SECONDS:
            left = ORDER_COOLDOWN_SECONDS - (now - int(last["created_at"]))
            # spam hits
            if client:
                hits = int(client["spam_hits"] or 0) + 1
                banned_until = 0
                reason = client["order_ban_reason"] or ""
                if hits >= ORDER_SPAM_HITS_LIMIT:
                    banned_until = now + ORDER_SPAM_BLOCK_SECONDS
                    reason = "частые попытки создать заявку"
                    hits = 0
                conn.execute(
                    "UPDATE clients SET spam_hits=?, order_banned_until=?, order_ban_reason=? WHERE user_id=?",
                    (hits, banned_until, reason, user_id)
                )
                conn.commit()
            return False, f"⏳ Новую заявку можно создать позже. Осталось примерно {max(1, left // 60)} мин."

    return True, ""


def next_order_no() -> str:
    with db() as conn:
        n = int(get_setting("next_order_number", "1001"))
        order_no = f"VT-{n}"
        set_setting("next_order_number", str(n + 1))
        return order_no


# =========================
# COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    expire_orders()
    isadm = is_admin_id(update.effective_user.id)
    text = get_setting("welcome_text", PRETTY_WELCOME_TEXT)
    if not bool_setting("bot_ready"):
        text += "\n\n⚙️ Сейчас Дом в режиме настройки. Заказы могут быть недоступны."
    photo_id = get_setting("welcome_photo_file_id", "")
    if photo_id:
        try:
            await update.message.reply_photo(photo=photo_id, caption=text, reply_markup=main_menu_keyboard(isadm))
            return
        except Exception:
            logging.exception("Не смог отправить приветственную картинку")
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(isadm))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    await start(update, context)


async def pin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not ADMIN_PIN:
        await update.message.reply_text("⛔ ADMIN_PIN не задан в Railway Variables.")
        return
    if not context.args:
        await update.message.reply_text("Напиши так: /pin ТВОЙ_PIN")
        return
    if context.args[0].strip() != ADMIN_PIN:
        await update.message.reply_text("⛔ Неверный PIN.")
        return

    user = update.effective_user
    with db() as conn:
        role = "owner"
        conn.execute(
            """INSERT INTO admins(user_id, role, username, first_name, added_at)
               VALUES(?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, username=excluded.username, first_name=excluded.first_name""",
            (user.id, role, user.username or "", user.first_name or "", now_ts())
        )
        conn.commit()
    log_action(user, "admin_pin_login", "admin", user.id, "Получил роль владельца через PIN")
    await update.message.reply_text("👑 PIN принят. Ты назначен владельцем бота.", reply_markup=main_menu_keyboard(True))


async def setup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "admin"):
        await update.message.reply_text("⛔ Только админ.")
        return
    await update.message.reply_text("🧰 Мастер настройки MASTER HOUSE v3.0", reply_markup=setup_keyboard())


async def setorderschat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "admin"):
        await update.message.reply_text("⛔ Только админ.")
        return
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эту команду надо написать в закрытой группе заявок.")
        return
    set_setting("orders_chat_id", str(chat.id))
    log_action(update.effective_user, "set_orders_chat", "chat", chat.id, chat.title or "")
    await update.message.reply_text(f"✅ Эта группа назначена для заявок.\nID: {chat.id}\nНазвание: {chat.title}")


async def setwallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "admin"):
        await update.message.reply_text("⛔ Только админ.")
        return
    text = update.message.text.partition(" ")[2].strip()
    if not text:
        await update.message.reply_text("Напиши так: /setwallet TON: адрес_кошелька")
        return
    add_ton_wallet(text)
    log_action(update.effective_user, "add_ton_wallet", "settings", "wallet", "Кошелёк добавлен через /setwallet")
    await update.message.reply_text("✅ TON / GRAM кошелёк добавлен.")


async def setprice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "admin"):
        await update.message.reply_text("⛔ Только админ.")
        return
    if not context.args:
        await update.message.reply_text("Напиши так: /setprice 10")
        return
    try:
        price = float(context.args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text("Цена должна быть числом.")
        return
    set_setting("seed_price", str(price))
    log_action(update.effective_user, "set_price", "settings", "seed_price", str(price))
    await update.message.reply_text(f"✅ Цена за 1 шт.: {price:g} ₽")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "admin"):
        await update.message.reply_text("⛔ Только админ.")
        return
    ready, report = readiness_report()
    await update.message.reply_text(
        f"⚙️ Статус VELES BOT v5.3 MASTER HOUSE MULTI TYPES PER ITEM\n\n"
        f"{report}\n\n"
        f"Заказы: {'включены' if bool_setting('orders_enabled') else 'пауза'}\n"
        f"Тестовый режим: {'да' if bool_setting('test_mode') else 'нет'}\n"
        f"База: {DB_PATH}\n"
        f"TON / GRAM кошельки: {'указаны' if ton_wallets_list() else 'не указаны'}\n"
        f"Цена за 1 шт.: {seed_price():g} ₽"
    )


async def backup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "admin"):
        await update.message.reply_text("⛔ Только админ.")
        return
    await send_backup(update.effective_chat.id, context)
    log_action(update.effective_user, "backup", "db", "sqlite", "Скачан backup")

async def restore_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "owner"):
        await update.message.reply_text("⛔ Только владелец.")
        return
    context.user_data["awaiting"] = {"type": "restore_db"}
    await update.message.reply_text("♻️ Пришли backup-файл .sqlite3 документом.\n\n⚠️ Это восстановит базу. Текущая база будет сохранена рядом.")


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "operator"):
        await update.message.reply_text("⛔ Только админ.")
        return
    await update.message.reply_text(daily_report_text())


async def findorder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "operator"):
        await update.message.reply_text("⛔ Только админ.")
        return
    if not context.args:
        await update.message.reply_text("Напиши так: /findorder VT-1001")
        return
    order_no = context.args[0].strip().upper()
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE UPPER(order_no)=?", (order_no,)).fetchone()
    if not order:
        await update.message.reply_text("Заказ не найден.")
        return
    await update.message.reply_text(order_text(order), reply_markup=order_admin_keyboard(order["id"], order["user_id"], order["status"]))


async def findclient_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "operator"):
        await update.message.reply_text("⛔ Только админ.")
        return
    if not context.args:
        await update.message.reply_text("Напиши так: /findclient username или /findclient 123456789")
        return
    term = context.args[0].strip().lstrip("@")
    with db() as conn:
        if term.isdigit():
            client = conn.execute("SELECT * FROM clients WHERE user_id=?", (int(term),)).fetchone()
        else:
            client = conn.execute("SELECT * FROM clients WHERE LOWER(username)=LOWER(?)", (term,)).fetchone()
    if not client:
        await update.message.reply_text("Клиент не найден.")
        return
    await update.message.reply_text(client_card_text(client["user_id"]), reply_markup=client_card_keyboard(client["user_id"]))




async def textfix_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "admin"):
        await update.message.reply_text("⛔ Только админ.")
        return
    set_setting("rules_text", PRETTY_RULES_TEXT)
    set_setting("client_rules_text", PRETTY_CLIENT_RULES_TEXT)
    set_setting("welcome_text", PRETTY_WELCOME_TEXT)
    set_setting("payment_help_text", PRETTY_PAYMENT_HELP_TEXT)
    log_action(update.effective_user, "textfix", "settings", "texts", "Исправлены все основные тексты")
    await update.message.reply_text("✅ Все тексты поправлены. Проверь: /start → Правила → Правила клиентов → Как оплатить.", reply_markup=admin_menu_keyboard())


async def rulesfix_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "admin"):
        await update.message.reply_text("⛔ Только админ.")
        return
    set_setting("rules_text", PRETTY_RULES_TEXT)
    set_setting("client_rules_text", PRETTY_CLIENT_RULES_TEXT)
    set_setting("welcome_text", PRETTY_WELCOME_TEXT)
    log_action(update.effective_user, "rulesfix", "settings", "rules", "Обновлены правила и приветствие")
    await update.message.reply_text("✅ Правила и приветствие обновлены. Теперь красиво и без кривых \\\\n.", reply_markup=admin_menu_keyboard())


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "operator"):
        await update.message.reply_text("⛔ Только админ.")
        return
    await update.message.reply_text("⚜️ Админ-меню", reply_markup=admin_menu_keyboard())


async def setwelcomephoto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "admin"):
        await update.message.reply_text("⛔ Только админ.")
        return

    photo_id = None
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        photo_id = update.message.reply_to_message.photo[-1].file_id
    elif update.message.photo:
        photo_id = update.message.photo[-1].file_id

    if not photo_id:
        await update.message.reply_text(
            "🖼 Как поставить приветственную картинку:\\n\\n"
            "1. Отправь картинку в этот чат.\\n"
            "2. Ответь на неё командой:\\n"
            "/setwelcomephoto",
            reply_markup=admin_menu_keyboard()
        )
        return

    set_setting("welcome_photo_file_id", photo_id)
    log_action(update.effective_user, "set_welcome_photo", "settings", "welcome_photo", "Обновлена картинка приветствия")
    await update.message.reply_text("✅ Приветственная картинка сохранена. Проверь через /start.", reply_markup=admin_menu_keyboard())


async def clearwelcomephoto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "admin"):
        await update.message.reply_text("⛔ Только админ.")
        return
    set_setting("welcome_photo_file_id", "")
    log_action(update.effective_user, "clear_welcome_photo", "settings", "welcome_photo", "")
    await update.message.reply_text("✅ Приветственная картинка удалена.", reply_markup=admin_menu_keyboard())


TEXT_MENU_KEYS = {
    "welcome_text": "👋 Приветствие",
    "rules_text": "📜 Правила Дома",
    "client_rules_text": "📜 Правила клиентов",
    "payment_help_text": "🚀 Как оплатить",
    "order_created_text": "🧾 Заказ создан",
    "payment_confirmed_text": "✅ Оплата подтверждена",
    "payment_rejected_text": "❌ Чек отклонён",
}

PICTURE_MENU_KEYS = {
    "welcome_photo_file_id": "👋 Приветствие",
    "payment_photo_file_id": "💳 Оплата",
    "rules_photo_file_id": "📜 Правила",
    "shop_photo_file_id": "🛒 Витрина",
}

# =========================
# CALLBACK ROUTER
# =========================


async def safe_edit_query(query, text=None, reply_markup=None, **kwargs):
    """
    Безопасное редактирование сообщений.
    Ошибка была из-за того, что Telegram не даёт edit_message_text для сообщения с фото.
    """
    if text is None:
        text = kwargs.pop("text", "")
    if not isinstance(text, str):
        text = str(text)

    try:
        msg = query.message
        has_media = bool(
            msg and (
                getattr(msg, "photo", None)
                or getattr(msg, "document", None)
                or getattr(msg, "video", None)
                or getattr(msg, "animation", None)
            )
        )

        if has_media:
            try:
                caption = text if len(text) <= 1024 else text[:1000] + "\n\n…"
                return await query.edit_message_caption(caption=caption, reply_markup=reply_markup)
            except Exception as media_err:
                media_s = str(media_err).lower()
                if "message is not modified" in media_s:
                    return None
                return await query.message.reply_text(text, reply_markup=reply_markup)

        return await query.edit_message_text(text=text, reply_markup=reply_markup, **kwargs)

    except Exception as e:
        s = str(e).lower()
        if "message is not modified" in s:
            return None
        if "there is no text" in s or "no text in the message" in s or "message to edit" in s:
            return await query.message.reply_text(text, reply_markup=reply_markup)
        return await query.message.reply_text(text, reply_markup=reply_markup)


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    update_client(user)
    expire_orders()
    data = query.data

    try:
        if data == "noop":
            await query.answer("Позиция пока недоступна.", show_alert=True)
            return

        if data == "main_menu":
            await safe_edit_query(query, get_setting("welcome_text"), reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        elif data == "rules":
            await safe_edit_query(query, get_setting("rules_text"), reply_markup=nav_keyboard("main_menu"))
        elif data == "client_rules":
            await safe_edit_query(query, get_setting("client_rules_text"), reply_markup=nav_keyboard("main_menu"))
        elif data == "payment_help":
            await safe_edit_query(query, payment_help_text(), reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        elif data == "wallet_text_show" or data.startswith("wallet_text_show:"):
            wallet = ""
            order_no = ""
            if ":" in data:
                try:
                    oid = int(data.split(":")[1])
                    with db() as conn:
                        order = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
                    if order:
                        wallet = row_get(order, "wallet_used", "") or choose_ton_wallet(order["order_no"])
                        order_no = order["order_no"]
                except Exception:
                    wallet = ""
            if not wallet:
                wallet = choose_ton_wallet("") or "TON / GRAM кошелёк пока не указан."
            memo = f"\n\n📝 Memo / комментарий: {order_no}" if order_no else ""
            await query.message.reply_text(f"💼 TON / GRAM кошелёк для оплаты:\n{wallet}{memo}")
        elif data == "my_vip":
            await show_my_vip(query, user)
        elif data == "my_orders":
            await show_my_orders(query, user)
        elif data.startswith("pay_return:"):
            await show_payment_again(query, context, int(data.split(":")[1]))
        elif data == "shop":
            await show_shop(query, user)
        elif data == "shop_all":
            await show_shop_items(query, user, None)
        elif data.startswith("shop_type:"):
            await show_shop_items(query, user, int(data.split(":")[1]))
        elif data.startswith("shop_item:"):
            await choose_item(query, context, int(data.split(":")[1]))
        elif data.startswith("shop_qty:"):
            _, item_id, qty = data.split(":")
            await choose_qty(query, context, int(item_id), int(qty))
        elif data.startswith("shop_district:"):
            _, item_id, qty, district_id = data.split(":")
            await choose_district(query, context, int(item_id), int(qty), int(district_id))
        elif data.startswith("order_confirm:"):
            _, item_id, qty, district_id = data.split(":")
            await create_order_from_selection(query, context, int(item_id), int(qty), int(district_id))
        elif data.startswith("client_check_payment:"):
            await client_check_payment(query, context, int(data.split(":")[1]))
        elif data.startswith("client_paid:"):
            await client_paid(query, context, int(data.split(":")[1]))
        elif data.startswith("client_cancel_order:"):
            await client_cancel_order(query, context, int(data.split(":")[1]))

        elif data == "admin_menu":
            await require_admin_query(query, user, "operator")
            await safe_edit_query(query, "⚜️ Админ-меню MASTER HOUSE", reply_markup=admin_menu_keyboard())
        elif data == "digital_menu":
            await require_admin_query(query, user, "admin")
            await digital_menu(query)
        elif data == "digital_choose_upload":
            await require_admin_query(query, user, "admin")
            await digital_choose_item(query, "upload")
        elif data == "digital_stock":
            await require_admin_query(query, user, "operator")
            await digital_stock_menu(query)
        elif data == "digital_history":
            await require_admin_query(query, user, "operator")
            await digital_history_menu(query)
        elif data.startswith("digital_upload_item:"):
            await require_admin_query(query, user, "admin")
            item_id = int(data.split(":")[1])
            context.user_data["awaiting"] = {"type": "digital_upload", "item_id": item_id}
            with db() as conn:
                item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
            await safe_edit_query(
                query,
                (
                    f"📤 Загрузка для позиции #{item_id}\n"
                    f"{item['name'] if item else ''}\n\n"
                    "Отправляй фотографии подряд. Бот сам поставит их в очередь.\n"
                    "Когда закончишь — нажми «✅ Завершить загрузку»."
                ),
                reply_markup=kb([[InlineKeyboardButton("✅ Завершить загрузку", callback_data="digital_upload_finish")]])
            )
        elif data == "digital_upload_finish":
            await require_admin_query(query, user, "admin")
            context.user_data.pop("awaiting", None)
            await digital_stock_menu(query)
        elif data == "auto_payment_menu":
            await require_admin_query(query, user, "admin")
            await safe_edit_query(query, auto_payment_status_text(), reply_markup=auto_payment_keyboard())
        elif data == "auto_payment_toggle":
            await require_admin_query(query, user, "owner")
            new = "0" if bool_setting("auto_payment_enabled") else "1"
            if new == "1" and ton_rub_rate() <= 0:
                await query.answer("Сначала укажи курс TON/₽.", show_alert=True)
            else:
                set_setting("auto_payment_enabled", new)
            await safe_edit_query(query, auto_payment_status_text(), reply_markup=auto_payment_keyboard())
        elif data == "auto_payment_rate":
            await require_admin_query(query, user, "owner")
            context.user_data["awaiting"] = {"type": "ton_rub_rate"}
            await safe_edit_query(
                query,
                "💱 Пришли курс: сколько ₽ стоит 1 TON.\nНапример: 250",
                reply_markup=auto_payment_keyboard()
            )
        elif data == "auto_payment_check_now":
            await require_admin_query(query, user, "admin")
            count = await check_ton_payments_once(context)
            await query.answer(f"Обработано платежей: {count}", show_alert=True)
            await safe_edit_query(query, auto_payment_status_text(), reply_markup=auto_payment_keyboard())
        elif data == "admin_setup":
            await require_admin_query(query, user, "admin")
            await safe_edit_query(query, "🧰 Мастер настройки MASTER HOUSE", reply_markup=setup_keyboard())
        elif data == "admin_search_help":
            await require_admin_query(query, user, "operator")
            await safe_edit_query(query, "🔍 Поиск:\n\n/findorder VT-1001 — найти заказ\n/findclient @username — найти клиента\n/report — отчёт за 24 часа", reply_markup=admin_menu_keyboard())
        elif data == "admin_receipts":
            await require_admin_query(query, user, "operator")
            await admin_receipts(query)
        elif data == "admin_ready_check":
            await require_admin_query(query, user, "admin")
            ready, report = readiness_report()
            if ready:
                set_setting("bot_ready", "1")
            await safe_edit_query(query, report, reply_markup=setup_keyboard())
        elif data == "admin_toggle_orders":
            await require_admin_query(query, user, "admin")
            new = "0" if bool_setting("orders_enabled") else "1"
            set_setting("orders_enabled", new)
            log_action(user, "toggle_orders", "settings", "orders_enabled", new)
            await safe_edit_query(query, "⚜️ Админ-меню MASTER HOUSE", reply_markup=admin_menu_keyboard())
        elif data == "admin_toggle_test":
            await require_admin_query(query, user, "admin")
            new = "0" if bool_setting("test_mode") else "1"
            set_setting("test_mode", new)
            log_action(user, "toggle_test_mode", "settings", "test_mode", new)
            await safe_edit_query(query, f"🧪 Тестовый режим: {'включён' if new=='1' else 'выключен'}", reply_markup=admin_menu_keyboard())

        elif data == "setup_wallet":
            await require_admin_query(query, user, "admin")
            context.user_data["awaiting"] = {"type": "wallet"}
            await safe_edit_query(query, "💳 Пришли основной TON / GRAM кошелёк.\nОн станет первым в списке.\nНапример: TON: UQxxxxxxxx", reply_markup=setup_back_keyboard())
        elif data == "setup_price":
            await require_admin_query(query, user, "admin")
            context.user_data["awaiting"] = {"type": "seed_price"}
            await safe_edit_query(query, "💰 Пришли цену за 1 шт. в ₽ числом.\nНапример: 10", reply_markup=setup_back_keyboard())
        elif data == "setup_orders_chat_help":
            await require_admin_query(query, user, "admin")
            await safe_edit_query(query, "👥 Чтобы назначить группу заявок:\n\n1. Добавь бота в закрытую группу.\n2. В этой группе напиши /setorderschat.", reply_markup=setup_keyboard())

        elif data == "toggle_service_mode":
            await require_admin_query(query, user, "admin")
            new = "0" if bool_setting("service_mode") else "1"
            set_setting("service_mode", new)
            log_action(user, "toggle_service_mode", "settings", "service_mode", new)
            await safe_edit_query(query, "⚜️ Админ-меню MASTER HOUSE", reply_markup=admin_menu_keyboard())
        elif data == "stock_menu":
            await require_admin_query(query, user, "admin")
            await stock_menu(query)
        elif data == "texts_menu":
            await require_admin_query(query, user, "admin")
            await texts_menu(query)
        elif data.startswith("text_edit:"):
            await require_admin_query(query, user, "admin")
            key = data.split(":", 1)[1]
            context.user_data["awaiting"] = {"type": "text_edit", "key": key}
            await safe_edit_query(query, f"✏️ Пришли новый текст для:\n{TEXT_MENU_KEYS.get(key, key)}", reply_markup=nav_keyboard("texts_menu", admin=True))
        elif data.startswith("text_preview:"):
            await require_admin_query(query, user, "admin")
            key = data.split(":", 1)[1]
            await safe_edit_query(query, get_setting(key, "—"), reply_markup=nav_keyboard("texts_menu", admin=True))
        elif data == "texts_reset":
            await require_admin_query(query, user, "admin")
            for k, v in [("welcome_text", PRETTY_WELCOME_TEXT), ("rules_text", PRETTY_RULES_TEXT), ("client_rules_text", PRETTY_CLIENT_RULES_TEXT), ("payment_help_text", PRETTY_PAYMENT_HELP_TEXT)]:
                set_setting(k, v)
            await safe_edit_query(query, "✅ Основные тексты восстановлены.", reply_markup=nav_keyboard("texts_menu", admin=True))
        elif data == "pictures_menu":
            await require_admin_query(query, user, "admin")
            await pictures_menu(query)
        elif data.startswith("picture_set:"):
            await require_admin_query(query, user, "admin")
            key = data.split(":", 1)[1]
            context.user_data["awaiting"] = {"type": "picture_set", "key": key}
            await safe_edit_query(query, f"🖼 Пришли картинку для:\n{PICTURE_MENU_KEYS.get(key, key)}", reply_markup=nav_keyboard("pictures_menu", admin=True))
        elif data.startswith("picture_clear:"):
            await require_admin_query(query, user, "admin")
            key = data.split(":", 1)[1]
            set_setting(key, "")
            await safe_edit_query(query, "✅ Картинка удалена.", reply_markup=nav_keyboard("pictures_menu", admin=True))
        elif data == "admins_menu":
            await require_admin_query(query, user, "owner")
            await admins_menu(query)
        elif data == "admin_add_prompt":
            await require_admin_query(query, user, "owner")
            context.user_data["awaiting"] = {"type": "admin_add_id"}
            await safe_edit_query(query, "👑 Пришли Telegram ID нового админа числом.", reply_markup=nav_keyboard("admins_menu", admin=True))
        elif data.startswith("admin_set_role:"):
            await require_admin_query(query, user, "owner")
            _, uid, role = data.split(":")
            await set_admin_role_menu(query, user, int(uid), role)
        elif data.startswith("admin_remove:"):
            await require_admin_query(query, user, "owner")
            await remove_admin_menu(query, user, int(data.split(":")[1]))
        elif data == "broadcast_menu":
            await require_admin_query(query, user, "admin")
            await broadcast_menu(query)
        elif data == "broadcast_all":
            await require_admin_query(query, user, "admin")
            context.user_data["awaiting"] = {"type": "broadcast_all"}
            await safe_edit_query(query, "📣 Пришли текст рассылки всем клиентам. Потом будет предпросмотр.", reply_markup=nav_keyboard("broadcast_menu", admin=True))
        elif data == "broadcast_vip":
            await require_admin_query(query, user, "admin")
            context.user_data["awaiting"] = {"type": "broadcast_vip"}
            await safe_edit_query(query, "📣 Пришли текст рассылки клиентам с покупками. Потом будет предпросмотр.", reply_markup=nav_keyboard("broadcast_menu", admin=True))
        elif data == "broadcast_confirm":
            await require_admin_query(query, user, "admin")
            await do_broadcast(query, context)
        elif data == "broadcast_cancel":
            context.user_data.pop("broadcast_pending", None)
            await safe_edit_query(query, "❌ Рассылка отменена.", reply_markup=nav_keyboard("broadcast_menu", admin=True))
        elif data == "reports_menu":
            await require_admin_query(query, user, "operator")
            await safe_edit_query(query, daily_report_text(), reply_markup=admin_menu_keyboard())
        elif data == "security_menu":
            await require_admin_query(query, user, "admin")
            await security_menu(query)
        elif data.startswith("toggle_setting:"):
            await require_admin_query(query, user, "admin")
            key = data.split(":", 1)[1]
            set_setting(key, "0" if bool_setting(key) else "1")
            await security_menu(query)
        elif data == "backup_menu":
            await require_admin_query(query, user, "admin")
            await backup_menu(query)
        elif data == "backup_now":
            await require_admin_query(query, user, "admin")
            await send_backup(query.message.chat_id, context)
            await safe_edit_query(query, "🧱 Backup отправлен.", reply_markup=admin_menu_keyboard())
        elif data == "restore_start":
            await require_admin_query(query, user, "owner")
            context.user_data["awaiting"] = {"type": "restore_db"}
            await safe_edit_query(query, "♻️ Отправь файл backup базы .sqlite3 документом.\n\n⚠️ Только файл, который бот присылал через Backup.", reply_markup=nav_keyboard("backup_menu", admin=True))
        elif data == "system_menu":
            await require_admin_query(query, user, "admin")
            await system_menu(query)
        elif data == "admin_payment":
            await require_admin_query(query, user, "admin")
            await safe_edit_query(query, payment_wallets_text_admin(), reply_markup=payment_wallets_keyboard())
        elif data == "wallet_add":
            await require_admin_query(query, user, "admin")
            context.user_data["awaiting"] = {"type": "wallet_add"}
            await safe_edit_query(query, "➕ Пришли TON / GRAM кошелёк.\nМожно строкой вида:\nTON: UQxxxxxxxx", reply_markup=payment_wallets_keyboard())
        elif data == "wallets_list":
            await require_admin_query(query, user, "admin")
            await safe_edit_query(query, payment_wallets_text_admin(), reply_markup=payment_wallets_keyboard())
        elif data == "wallets_clear_prompt":
            await require_admin_query(query, user, "owner")
            await safe_edit_query(query, "⚠️ Точно очистить список TON / GRAM кошельков?", reply_markup=kb([
                [InlineKeyboardButton("Да, очистить", callback_data="wallets_clear_yes")],
                [InlineKeyboardButton("Нет", callback_data="admin_payment")]
            ]))
        elif data == "wallets_clear_yes":
            await require_admin_query(query, user, "owner")
            set_setting("wallet_text", "")
            set_setting("ton_wallets_text", "")
            log_action(user, "clear_ton_wallets", "settings", "wallets", "")
            await safe_edit_query(query, "✅ TON / GRAM кошельки очищены.", reply_markup=payment_wallets_keyboard())
        elif data == "btc_reserve_set":
            await require_admin_query(query, user, "admin")
            context.user_data["awaiting"] = {"type": "btc_reserve_wallet"}
            await safe_edit_query(query, "🪙 Пришли BTC-кошелёк для резерва.\nОн не будет показываться клиенту автоматически.", reply_markup=payment_wallets_keyboard())
        elif data == "btc_reserve_show":
            await require_admin_query(query, user, "admin")
            btc = get_setting("btc_reserve_wallet_text", "") or "BTC резерв не указан."
            await safe_edit_query(query, f"🪙 BTC резервный кошелёк:\n{btc}", reply_markup=payment_wallets_keyboard())

        elif data == "admin_shop":
            await require_admin_query(query, user, "admin")
            await admin_shop_menu(query)
        elif data == "item_add":
            await require_admin_query(query, user, "admin")
            context.user_data["awaiting"] = {"type": "item_name"}
            await safe_edit_query(query, "🛒 Пришли название позиции витрины.", reply_markup=kb([[InlineKeyboardButton("⬅️ Витрина", callback_data="admin_shop")]]))
        elif data == "types_menu":
            await require_admin_query(query, user, "admin")
            await types_menu(query)
        elif data == "type_add":
            await require_admin_query(query, user, "admin")
            context.user_data["awaiting"] = {"type": "type_emoji"}
            await safe_edit_query(query, "🏷 Пришли смайлик типа. Например: 🌰 или 🍯 или 🔥", reply_markup=kb([[InlineKeyboardButton("⬅️ Типы", callback_data="types_menu")]]))
        elif data.startswith("type_delete:"):
            await require_admin_query(query, user, "owner")
            await delete_type(query, user, int(data.split(":")[1]))
        elif data.startswith("item_type_menu:"):
            await require_admin_query(query, user, "admin")
            await item_type_menu(query, int(data.split(":")[1]))
        elif data.startswith("item_type_set:"):
            await require_admin_query(query, user, "admin")
            _, item_id, type_id = data.split(":")
            await set_item_type(query, user, int(item_id), int(type_id))
        elif data.startswith("item_type_clear:"):
            await require_admin_query(query, user, "admin")
            await clear_item_type(query, user, int(data.split(":")[1]))
        elif data.startswith("item_type_toggle:"):
            await require_admin_query(query, user, "admin")
            await toggle_item_type(query, user, int(data.split(":")[1]))
        elif data.startswith("item_manage:"):
            await require_admin_query(query, user, "admin")
            await item_manage(query, int(data.split(":")[1]))
        elif data.startswith("item_status:"):
            await require_admin_query(query, user, "admin")
            _, item_id, status = data.split(":")
            await set_item_status(query, user, int(item_id), status)
        elif data.startswith("item_stock:"):
            await require_admin_query(query, user, "admin")
            item_id = int(data.split(":")[1])
            context.user_data["awaiting"] = {"type": "item_stock", "item_id": item_id}
            await safe_edit_query(query, "📦 Пришли остаток, шт. числом. 0 = нет в наличии.", reply_markup=kb([[InlineKeyboardButton("⬅️ Назад", callback_data=f"item_manage:{item_id}")]]))
        elif data.startswith("item_delete:"):
            await require_admin_query(query, user, "owner")
            await delete_item(query, user, int(data.split(":")[1]))

        elif data == "admin_districts":
            await require_admin_query(query, user, "admin")
            await admin_districts(query)
        elif data == "district_add":
            await require_admin_query(query, user, "admin")
            context.user_data["awaiting"] = {"type": "district_name"}
            await safe_edit_query(query, "📍 Пришли название района.", reply_markup=kb([[InlineKeyboardButton("⬅️ Районы", callback_data="admin_districts")]]))
        elif data.startswith("district_toggle:"):
            await require_admin_query(query, user, "admin")
            await toggle_district(query, user, int(data.split(":")[1]))
        elif data.startswith("district_delete:"):
            await require_admin_query(query, user, "owner")
            await delete_district(query, user, int(data.split(":")[1]))

        elif data == "admin_orders":
            await require_admin_query(query, user, "operator")
            await admin_orders(query)
        elif data.startswith("order_view:"):
            await require_admin_query(query, user, "operator")
            await show_order_admin(query, int(data.split(":")[1]))
        elif data.startswith("order_change_amount:"):
            await require_admin_query(query, user, "operator")
            oid = int(data.split(":")[1])
            context.user_data["awaiting"] = {"type": "order_amount", "order_id": oid}
            await safe_edit_query(query, "💰 Пришли новую сумму заказа в ₽ числом.", reply_markup=kb([[InlineKeyboardButton("⬅️ Заказ", callback_data=f"order_view:{oid}")]]))
        elif data.startswith("order_templates:"):
            await require_admin_query(query, user, "operator")
            await order_templates(query, int(data.split(":")[1]))
        elif data.startswith("order_tpl:"):
            await require_admin_query(query, user, "operator")
            _, oid, tpl = data.split(":", 2)
            await send_order_template(query, context, int(oid), tpl)
        elif data.startswith("order_accept:"):
            await admin_order_status(query, context, int(data.split(":")[1]), "accepted")
        elif data.startswith("order_payment_ok:"):
            await admin_order_status(query, context, int(data.split(":")[1]), "work", paid=True)
        elif data.startswith("receipt_reject:"):
            await receipt_reject_prompt(query, context, int(data.split(":")[1]))
        elif data.startswith("receipt_show:"):
            await show_receipt_to_admin(query, context, int(data.split(":")[1]))
        elif data.startswith("tx_check:"):
            await verify_order_tx_hash_callback(query, context, int(data.split(":")[1]))
        elif data.startswith("order_work:"):
            await admin_order_status(query, context, int(data.split(":")[1]), "work")
        elif data.startswith("order_sent:"):
            await admin_order_status(query, context, int(data.split(":")[1]), "sent")
        elif data.startswith("order_close:"):
            await close_order(query, context, int(data.split(":")[1]))
        elif data.startswith("order_cancel_admin:"):
            await admin_cancel_order_prompt(query, context, int(data.split(":")[1]))
        elif data.startswith("client_card:"):
            await require_admin_query(query, user, "operator")
            uid = int(data.split(":")[1])
            await safe_edit_query(query, client_card_text(uid), reply_markup=client_card_keyboard(uid))
        elif data.startswith("client_note:"):
            await require_admin_query(query, user, "admin")
            uid = int(data.split(":")[1])
            context.user_data["awaiting"] = {"type": "client_note", "user_id": uid}
            await safe_edit_query(query, f"📝 Пришли заметку по клиенту ID {uid}.", reply_markup=client_card_keyboard(uid))
        elif data.startswith("client_ban:"):
            await require_admin_query(query, user, "admin")
            await ban_client_orders(query, user, int(data.split(":")[1]))
        elif data.startswith("client_unban:"):
            await require_admin_query(query, user, "admin")
            await unban_client_orders(query, user, int(data.split(":")[1]))

        elif data == "admin_clients":
            await require_admin_query(query, user, "operator")
            await admin_clients(query)
        elif data == "admin_report":
            await require_admin_query(query, user, "operator")
            await safe_edit_query(query, daily_report_text(), reply_markup=admin_menu_keyboard())
        elif data == "admin_logs":
            await require_admin_query(query, user, "admin")
            await safe_edit_query(query, logs_text(), reply_markup=admin_menu_keyboard())
        elif data == "admin_backup":
            await require_admin_query(query, user, "admin")
            await send_backup(query.message.chat_id, context)
            await safe_edit_query(query, "🧱 Backup отправлен.", reply_markup=admin_menu_keyboard())
        elif data == "admin_export":
            await require_admin_query(query, user, "admin")
            await send_exports(query.message.chat_id, context)
            await safe_edit_query(query, "📤 Экспорт клиентов и заказов отправлен.", reply_markup=admin_menu_keyboard())
        else:
            await safe_edit_query(query, "⚠️ Неизвестная кнопка.", reply_markup=main_menu_keyboard(is_admin_id(user.id)))

    except PermissionError:
        await safe_edit_query(query, "⛔ Недостаточно прав.")
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("Уже открыто.")
            return
        logging.exception("Callback error")
        try:
            await safe_edit_query(query, f"⚠️ Ошибка: {e}")
        except Exception:
            await query.message.reply_text(f"⚠️ Ошибка: {e}")


async def require_admin_query(query, user, level="operator"):
    if not has_perm(user.id, level):
        raise PermissionError()


# =========================
# CLIENT FLOWS
# =========================

async def show_my_vip(query, user):
    client = get_client(user.id)
    p = int(client["purchases"] if client else 0)
    await safe_edit_query(query, 
        f"🏅 Твой статус в Доме\n\n"
        f"📦 Покупок: {p}\n"
        f"⚜️ Статус: {vip_status(p)}\n"
        f"{next_vip_text(p)}",
        reply_markup=main_menu_keyboard(is_admin_id(user.id))
    )


async def show_my_orders(query, user):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (user.id,)
        ).fetchall()
    if not rows:
        await safe_edit_query(query, "📦 У тебя пока нет заказов.", reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        return

    text = "📦 Мои заказы\n\n"
    buttons = []
    for o in rows:
        emoji = row_get(o, "item_type_emoji", "") or ""
        item_name = f"{emoji} {o['item_name']}".strip()
        text += f"{o['order_no']} — {status_name(o['status'])} — {item_name} x{o['qty']}\n"
        if o["status"] == "awaiting_payment":
            buttons.append([InlineKeyboardButton(f"💳 Вернуться к оплате {o['order_no']}", callback_data=f"pay_return:{o['id']}")])
        if o["status"] in CLIENT_CANCEL_ALLOWED:
            buttons.append([InlineKeyboardButton(f"❌ Отменить {o['order_no']}", callback_data=f"client_cancel_order:{o['id']}")])
    buttons.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")])
    await safe_edit_query(query, text, reply_markup=kb(buttons))


async def show_payment_again(query, context, order_id: int):
    user = query.from_user
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, user.id)).fetchone()
    if not order:
        await safe_edit_query(query, "Заказ не найден.", reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        return
    if order["status"] != "awaiting_payment":
        await safe_edit_query(query, f"Этот заказ уже не на этапе оплаты.\nСтатус: {status_name(order['status'])}", reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        return

    wallet = row_get(order, "wallet_used", "") or choose_ton_wallet(order["order_no"])
    text = (
        f"💳 Оплата заказа {order['order_no']}\n\n"
        f"💰 Сумма: {order['amount']:g} ₽\n"
        f"💼 TON / GRAM кошелёк:\n{wallet or '—'}\n\n"
        f"📝 Комментарий / memo:\n{order['order_no']}\n\n"
        f"После оплаты нажми “✅ Я оплатил” и отправь чек / скрин."
    )
    await safe_edit_query(query, text, reply_markup=payment_keyboard(order_id))
    if wallet:
        await send_payment_qr_to_client(context, user.id, wallet)


async def show_shop(query, user):
    """
    Клиентская витрина:
    сначала клиент выбирает ТИП товара (смайлик), если типы добавлены и назначены позициям.
    Потом видит позиции внутри выбранного типа.
    """
    if bool_setting("service_mode"):
        await safe_edit_query(query, "🔧 Дом в режиме обслуживания. Заказы временно недоступны.", reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        return
    ready, report = readiness_report()
    if not bool_setting("bot_ready") or not ready:
        await safe_edit_query(query, "⚙️ Дом на настройке. Заказы временно недоступны.", reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        return
    if not bool_setting("orders_enabled"):
        await safe_edit_query(query, "⏸ Заказы временно приостановлены.", reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        return

    ok, msg = can_create_order(user.id)
    if not ok:
        await safe_edit_query(query, msg, reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        return

    with db() as conn:
        active_types = conn.execute(
            """
            SELECT DISTINCT t.id, t.emoji
            FROM item_types t
            JOIN item_type_links l ON l.type_id = t.id
            JOIN items i ON i.id = l.item_id
            WHERE i.status IN ('in_stock','soon','hot','recommended')
              AND l.enabled=1
            ORDER BY t.id DESC
            """
        ).fetchall()
        item_count = conn.execute(
            "SELECT COUNT(*) c FROM items WHERE status IN ('in_stock','soon','hot','recommended')"
        ).fetchone()["c"]

    if item_count == 0:
        await safe_edit_query(query, "🛒 Витрина пока пустая.", reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        return

    # Если типов нет или они не назначены позициям — показываем обычный список.
    if not active_types:
        await show_shop_items(query, user, None)
        return

    rows = []
    for t in active_types:
        rows.append([InlineKeyboardButton(f"🏷 {t['emoji']}", callback_data=f"shop_type:{t['id']}")])
    rows.append([InlineKeyboardButton("🛒 Все позиции", callback_data="shop_all")])
    rows.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")])

    await safe_edit_query(
        query,
        "🛒 Витрина VELES TRADE\n\nВыбери тип товара:",
        reply_markup=kb(rows)
    )


async def show_shop_items(query, user, type_id: int | None = None):
    """
    Список позиций после выбора типа.
    """
    with db() as conn:
        type_row = None
        if type_id is not None:
            type_row = conn.execute("SELECT * FROM item_types WHERE id=?", (type_id,)).fetchone()
            items = conn.execute(
                """
                SELECT i.*
                FROM items i
                JOIN item_type_links l ON l.item_id = i.id
                WHERE l.type_id=? AND l.enabled=1
                  AND i.status IN ('in_stock','soon','hot','recommended')
                ORDER BY i.id DESC
                """,
                (type_id,)
            ).fetchall()
        else:
            items = conn.execute(
                "SELECT * FROM items WHERE status IN ('in_stock','soon','hot','recommended') ORDER BY id DESC"
            ).fetchall()

        active_types_count = conn.execute(
            """
            SELECT COUNT(DISTINCT t.id) c
            FROM item_types t
            JOIN item_type_links l ON l.type_id = t.id
            JOIN items i ON i.id = l.item_id
            WHERE i.status IN ('in_stock','soon','hot','recommended')
              AND l.enabled=1
            """
        ).fetchone()["c"]

    if not items:
        await safe_edit_query(
            query,
            "🛒 В этом типе пока нет позиций.",
            reply_markup=kb([[InlineKeyboardButton("⬅️ Типы", callback_data="shop")], [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]])
        )
        return

    rows = []
    if type_row:
        text = f"🛒 Витрина VELES TRADE\n\nТип: {type_row['emoji']}\nВыбери позицию:"
    else:
        text = "🛒 Витрина VELES TRADE\n\nВыбери позицию:"

    for item in items:
        label = f"{store_status_label(item['status'])} {item_display_name(item)}"
        if item["status"] == "soon":
            rows.append([InlineKeyboardButton(label, callback_data="noop")])
        else:
            rows.append([InlineKeyboardButton(label, callback_data=f"shop_item:{item['id']}")])

    if active_types_count:
        rows.append([InlineKeyboardButton("⬅️ Типы", callback_data="shop")])
    rows.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")])
    await safe_edit_query(query, text, reply_markup=kb(rows))

async def choose_item(query, context, item_id: int):
    with db() as conn:
        item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not item:
        await safe_edit_query(query, "Позиция не найдена.", reply_markup=kb([[InlineKeyboardButton("⬅️ Витрина", callback_data="shop")]]))
        return

    rows = []
    stock = item["stock"]
    for q in SEED_OPTIONS:
        if stock is not None and int(stock) < q:
            continue
        rows.append([InlineKeyboardButton(f"{q} {seed_word(q)}", callback_data=f"shop_qty:{item_id}:{q}")])
    if not rows:
        rows = [[InlineKeyboardButton("❌ Нет доступного количества", callback_data="shop")]]
    rows.append([InlineKeyboardButton("⬅️ Витрина", callback_data="shop")])

    desc = item["description"] or "—"
    stock_text = "не указан" if stock is None else str(stock)
    await safe_edit_query(query, 
        f"{item_display_name(item)}\n\n"
        f"{desc}\n\n"
        f"📦 Остаток: {stock_text}\n"
        f"💰 Цена за 1 шт.: {seed_price():g} ₽\n\n"
        f"Выбери количество:",
        reply_markup=kb(rows)
    )


async def choose_qty(query, context, item_id: int, qty: int):
    with db() as conn:
        districts = conn.execute("SELECT * FROM districts WHERE enabled=1 ORDER BY name").fetchall()
    if not districts:
        await safe_edit_query(query, "📍 Нет активных районов.", reply_markup=kb([[InlineKeyboardButton("⬅️ Витрина", callback_data="shop")]]))
        return
    rows = [[InlineKeyboardButton(f"📍 {d['name']}", callback_data=f"shop_district:{item_id}:{qty}:{d['id']}")] for d in districts]
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"shop_item:{item_id}")])
    await safe_edit_query(query, "📍 Выбери район / способ получения:", reply_markup=kb(rows))


async def choose_district(query, context, item_id: int, qty: int, district_id: int):
    with db() as conn:
        item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        district = conn.execute("SELECT * FROM districts WHERE id=?", (district_id,)).fetchone()
    if not item or not district:
        await safe_edit_query(query, "Ошибка выбора.", reply_markup=main_menu_keyboard(is_admin_id(query.from_user.id)))
        return
    amount = qty * seed_price()
    await safe_edit_query(query, 
        f"✅ Подтверждение заказа\n\n"
        f"🌰 Позиция: {item_display_name(item)}\n"
        f"🔢 Количество: {qty} {seed_word(qty)}\n"
        f"📍 Район: {district['name']}\n"
        f"💰 Сумма: {amount:g} ₽\n\n"
        f"Создать заказ?",
        reply_markup=kb([
            [InlineKeyboardButton("✅ Подтвердить заказ", callback_data=f"order_confirm:{item_id}:{qty}:{district_id}")],
            [InlineKeyboardButton("⬅️ Витрина", callback_data="shop")]
        ])
    )


async def create_order_from_selection(query, context, item_id: int, qty: int, district_id: int):
    user = query.from_user
    ok, msg = can_create_order(user.id)
    if not ok:
        await safe_edit_query(query, msg, reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        return

    with db() as conn:
        item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        district = conn.execute("SELECT * FROM districts WHERE id=?", (district_id,)).fetchone()
        if not item or not district:
            await safe_edit_query(query, "Ошибка: позиция или район не найдены.")
            return
        stock = item["stock"]
        if stock is not None and int(stock) < qty:
            await safe_edit_query(query, "⚠️ Недостаточно остатка по этой позиции.", reply_markup=kb([[InlineKeyboardButton("⬅️ Витрина", callback_data="shop")]]))
            return

        order_no = next_order_no()
        amount = qty * seed_price()
        expected_ton = expected_ton_for_rub(amount)
        created = now_ts()
        expires = created + PAYMENT_TTL_SECONDS
        wallet = choose_ton_wallet(order_no)
        payment_comment = order_no

        digital_counts = digital_stock_counts(item_id)
        if bool_setting("digital_delivery_enabled") and digital_counts["available"] <= 0:
            await safe_edit_query(
                query,
                "⛔ Цифровой товар по этой позиции закончился. Администрация уже уведомлена.",
                reply_markup=kb([[InlineKeyboardButton("⬅️ Витрина", callback_data="shop")]])
            )
            return

        conn.execute(
            """INSERT INTO orders(order_no, user_id, username, item_id, item_name, qty, district_id, district_name,
                                  amount, status, test_mode, created_at, updated_at, expires_at, wallet_used,
                                  item_type_emoji, expected_ton, payment_comment)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'awaiting_payment', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (order_no, user.id, user.username or "", item_id, item["name"], qty, district_id, district["name"],
             amount, 1 if bool_setting("test_mode") else 0, created, created, expires, wallet,
             item_type_emoji(item), expected_ton, payment_comment)
        )
        order_id = conn.execute("SELECT last_insert_rowid() id").fetchone()["id"]
        conn.execute("UPDATE clients SET spam_hits=0 WHERE user_id=?", (user.id,))
        conn.commit()
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()

    wallet = row_get(order, "wallet_used", "") or choose_ton_wallet(order_no)
    text = (
        f"🧾 Заказ {order_no} создан.\n\n"
        f"🌰 {item_display_name(item)}\n"
        f"🔢 {qty} {seed_word(qty)}\n"
        f"📍 {district['name']}\n"
        f"💰 Сумма заказа: {amount:g} ₽\n"
        f"💎 К оплате: {expected_ton:g} TON / GRAM\n\n"
        f"💼 Кошелёк:\n{wallet}\n\n"
        f"📝 ОБЯЗАТЕЛЬНЫЙ комментарий / memo:\n{order_no}\n\n"
        f"⏳ Оплата действительна до {fmt_dt(expires)}.\n"
        f"Нажми «🚀 ОПЛАТИТЬ TON / GRAM». Бот сам найдёт платёж и выдаст фото."
    )
    await safe_edit_query(query, text, reply_markup=payment_keyboard(order_id))
    if wallet:
        await send_payment_qr_to_client(context, user.id, wallet)
    await send_order_to_admins(context, order, "🧾 Новый заказ ожидает оплаты")
    log_action(user, "create_order", "order", order_no, f"{item['name']} x{qty}")


async def client_paid(query, context, order_id: int):
    user = query.from_user
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, user.id)).fetchone()
    if not order:
        await safe_edit_query(query, "Заказ не найден.", reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        return
    if order["status"] not in {"awaiting_payment"}:
        await safe_edit_query(query, f"Заказ уже в статусе: {status_name(order['status'])}", reply_markup=client_order_keyboard(order_id, order["status"]))
        return
    if order["expires_at"] and int(order["expires_at"]) < now_ts():
        with db() as conn:
            conn.execute("UPDATE orders SET status='expired', updated_at=?, cancelled_at=?, cancel_reason=? WHERE id=?",
                         (now_ts(), now_ts(), "истекло время оплаты", order_id))
            conn.commit()
        await safe_edit_query(query, "⌛ Время оплаты истекло. Создай новый заказ.", reply_markup=main_menu_keyboard(is_admin_id(user.id)))
        return

    context.user_data["awaiting"] = {"type": "payment_proof", "order_id": order_id}
    await safe_edit_query(query, 
        f"✅ Заказ {order['order_no']}\n\n"
        f"Отправь чек / скрин оплаты фото или документом.\n\n"
        f"hash / ссылка транзакции можно прислать текстом дополнительно, если он есть.\n"
        f"Если hash нет — ничего страшного, админ проверит оплату вручную.",
        reply_markup=kb([
            [InlineKeyboardButton("🚀 Как оплатить", callback_data="payment_help")],
            [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ])
    )


async def client_cancel_order(query, context, order_id: int):
    user = query.from_user
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, user.id)).fetchone()
        if not order:
            await safe_edit_query(query, "Заказ не найден.", reply_markup=main_menu_keyboard(is_admin_id(user.id)))
            return
        if order["status"] not in CLIENT_CANCEL_ALLOWED:
            await safe_edit_query(query, "❌ Этот заказ уже нельзя отменить самостоятельно. Свяжись с администрацией.", reply_markup=client_order_keyboard(order_id, order["status"]))
            return
        conn.execute(
            "UPDATE orders SET status='cancelled', updated_at=?, cancelled_at=?, cancel_reason=? WHERE id=?",
            (now_ts(), now_ts(), "Клиент отменил заказ", order_id)
        )
        conn.commit()
        order2 = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()

    await safe_edit_query(query, f"❌ Заказ {order['order_no']} отменён.", reply_markup=main_menu_keyboard(is_admin_id(user.id)))
    await send_order_to_admins(context, order2, "❌ Клиент отменил заказ")
    log_action(user, "client_cancel_order", "order", order["order_no"], "")


# =========================
# ADMIN STORE / DISTRICTS
# =========================

async def admin_shop_menu(query):
    with db() as conn:
        items = conn.execute("SELECT * FROM items ORDER BY id DESC LIMIT 20").fetchall()
    text = "🛒 Управление витриной\n\n"
    rows = [
        [InlineKeyboardButton("➕ Добавить позицию", callback_data="item_add")],
        [InlineKeyboardButton("🏷 Типы", callback_data="types_menu")]
    ]
    if not items:
        text += "Позиции пока не добавлены."
    else:
        for i in items:
            stock = "∞" if i["stock"] is None else str(i["stock"])
            rows.append([InlineKeyboardButton(f"{store_status_label(i['status'])} {item_display_name(i)} | остаток {stock}", callback_data=f"item_manage:{i['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")])
    await safe_edit_query(query, text, reply_markup=kb(rows))


async def types_menu(query):
    with db() as conn:
        rows_db = conn.execute("SELECT * FROM item_types ORDER BY id DESC").fetchall()
    text = "🏷 Типы витрины\n\nТип — это смайлик-категория. Клиент сначала выбирает тип, потом позицию внутри типа.\n\n"
    rows = [[InlineKeyboardButton("➕ Добавить тип", callback_data="type_add")]]
    if not rows_db:
        text += "Типы пока не добавлены."
    else:
        for t in rows_db:
            text += f"{t['id']}. {t['emoji']}\n"
            rows.append([InlineKeyboardButton(f"🗑 Удалить {t['emoji']}", callback_data=f"type_delete:{t['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Витрина", callback_data="admin_shop")])
    await safe_edit_query(query, text, reply_markup=kb(rows))


async def delete_type(query, user, type_id: int):
    with db() as conn:
        t = conn.execute("SELECT * FROM item_types WHERE id=?", (type_id,)).fetchone()
        conn.execute("DELETE FROM item_type_links WHERE type_id=?", (type_id,))
        conn.execute("DELETE FROM item_types WHERE id=?", (type_id,))
        conn.execute("UPDATE items SET type_id=NULL, type_emoji='', type_enabled=0 WHERE type_id=?", (type_id,))
        conn.commit()
    log_action(user, "delete_type", "type", type_id, row_get(t, "emoji", "") if t else "")
    await types_menu(query)


async def item_type_menu(query, item_id: int):
    with db() as conn:
        item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        types = conn.execute("SELECT * FROM item_types ORDER BY id DESC").fetchall()
        linked = {
            r["type_id"]: int(r["enabled"])
            for r in conn.execute("SELECT type_id, enabled FROM item_type_links WHERE item_id=?", (item_id,)).fetchall()
        }
    if not item:
        await safe_edit_query(query, "Позиция не найдена.", reply_markup=kb([[InlineKeyboardButton("⬅️ Витрина", callback_data="admin_shop")]]))
        return

    rows = []
    if not types:
        text = "🏷 Типы ещё не добавлены.\nСначала добавь типы в витрине."
    else:
        text = (
            f"🏷 Типы позиции:\n{item['name']}\n\n"
            f"Можно включить несколько типов одновременно.\n"
            f"✅ = тип включён у этой позиции\n"
            f"◻️ = тип есть, но выключен\n"
            f"➕ = тип ещё не привязан\n"
        )
        for t in types:
            state = linked.get(t["id"])
            if state == 1:
                label = f"✅ {t['emoji']} — выключить"
            elif state == 0:
                label = f"◻️ {t['emoji']} — включить"
            else:
                label = f"➕ {t['emoji']} — добавить"
            rows.append([InlineKeyboardButton(label, callback_data=f"item_type_set:{item_id}:{t['id']}")])

    rows.append([InlineKeyboardButton("➖ Убрать все типы", callback_data=f"item_type_clear:{item_id}")])
    rows.append([InlineKeyboardButton("⬅️ Позиция", callback_data=f"item_manage:{item_id}")])
    await safe_edit_query(query, text, reply_markup=kb(rows))


async def set_item_type(query, user, item_id: int, type_id: int):
    """
    Не один тип, а несколько.
    Нажатие по типу:
    - если не привязан: добавляет и включает;
    - если включён: выключает;
    - если выключен: включает.
    """
    with db() as conn:
        item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        t = conn.execute("SELECT * FROM item_types WHERE id=?", (type_id,)).fetchone()
        if not item or not t:
            await safe_edit_query(query, "Позиция или тип не найдены.", reply_markup=kb([[InlineKeyboardButton("⬅️ Позиция", callback_data=f"item_manage:{item_id}")]]))
            return

        link = conn.execute("SELECT * FROM item_type_links WHERE item_id=? AND type_id=?", (item_id, type_id)).fetchone()
        if not link:
            conn.execute(
                "INSERT OR REPLACE INTO item_type_links(item_id, type_id, enabled, created_at) VALUES(?, ?, 1, ?)",
                (item_id, type_id, now_ts())
            )
            action = "add_item_type"
        else:
            new_state = 0 if int(link["enabled"]) == 1 else 1
            conn.execute(
                "UPDATE item_type_links SET enabled=? WHERE item_id=? AND type_id=?",
                (new_state, item_id, type_id)
            )
            action = "enable_item_type" if new_state else "disable_item_type"

        # Старые поля оставляем как совместимость: туда пишем первый включённый тип, если он есть.
        enabled = conn.execute(
            """
            SELECT t.id, t.emoji
            FROM item_type_links l
            JOIN item_types t ON t.id=l.type_id
            WHERE l.item_id=? AND l.enabled=1
            ORDER BY t.id DESC
            LIMIT 1
            """,
            (item_id,)
        ).fetchone()
        if enabled:
            conn.execute(
                "UPDATE items SET type_id=?, type_emoji=?, type_enabled=1, updated_at=? WHERE id=?",
                (enabled["id"], enabled["emoji"], now_ts(), item_id)
            )
        else:
            conn.execute(
                "UPDATE items SET type_enabled=0, updated_at=? WHERE id=?",
                (now_ts(), item_id)
            )
        conn.commit()

    log_action(user, action, "item", item_id, t["emoji"])
    await item_type_menu(query, item_id)


async def clear_item_type(query, user, item_id: int):
    with db() as conn:
        conn.execute("DELETE FROM item_type_links WHERE item_id=?", (item_id,))
        conn.execute("UPDATE items SET type_id=NULL, type_emoji='', type_enabled=0, updated_at=? WHERE id=?", (now_ts(), item_id))
        conn.commit()
    log_action(user, "clear_all_item_types", "item", item_id, "")
    await item_manage(query, item_id)


async def toggle_item_type(query, user, item_id: int):
    # Старую кнопку больше не используем как общий тумблер.
    # Показываем экран со всеми типами позиции.
    await item_type_menu(query, item_id)




async def item_manage(query, item_id: int):
    with db() as conn:
        item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not item:
        await safe_edit_query(query, "Позиция не найдена.", reply_markup=kb([[InlineKeyboardButton("⬅️ Витрина", callback_data="admin_shop")]]))
        return

    stock = "не указан" if item["stock"] is None else str(item["stock"])
    type_line = item_type_status_line(item_id)

    await safe_edit_query(query,
        f"🛒 Позиция #{item['id']}\n\n"
        f"Название: {item['name']}\n"
        f"Типы позиции: {type_line}\n"
        f"Описание: {item['description'] or '—'}\n"
        f"Статус: {store_status_label(item['status'])}\n"
        f"Остаток: {stock}",
        reply_markup=kb([
            [InlineKeyboardButton("✅ В наличии", callback_data=f"item_status:{item_id}:in_stock"), InlineKeyboardButton("⏳ Скоро", callback_data=f"item_status:{item_id}:soon")],
            [InlineKeyboardButton("🔥 Горячее", callback_data=f"item_status:{item_id}:hot"), InlineKeyboardButton("⭐ Рекомендуем", callback_data=f"item_status:{item_id}:recommended")],
            [InlineKeyboardButton("❌ Скрыто", callback_data=f"item_status:{item_id}:hidden")],
            [InlineKeyboardButton("🏷 Типы позиции", callback_data=f"item_type_menu:{item_id}"), InlineKeyboardButton("📦 Изменить остаток", callback_data=f"item_stock:{item_id}")],
            [InlineKeyboardButton("🗑 Удалить", callback_data=f"item_delete:{item_id}")],
            [InlineKeyboardButton("⬅️ Витрина", callback_data="admin_shop")]
        ])
    )

async def set_item_status(query, user, item_id: int, status: str):
    with db() as conn:
        conn.execute("UPDATE items SET status=?, updated_at=? WHERE id=?", (status, now_ts(), item_id))
        conn.commit()
    log_action(user, "set_item_status", "item", item_id, status)
    await item_manage(query, item_id)


async def delete_item(query, user, item_id: int):
    with db() as conn:
        conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        conn.commit()
    log_action(user, "delete_item", "item", item_id, "")
    await admin_shop_menu(query)


async def admin_districts(query):
    with db() as conn:
        rows_db = conn.execute("SELECT * FROM districts ORDER BY name").fetchall()
    rows = [[InlineKeyboardButton("➕ Добавить район", callback_data="district_add")]]
    text = "📍 Районы\n\n"
    if not rows_db:
        text += "Районы пока не добавлены."
    for d in rows_db:
        text += f"{'✅' if d['enabled'] else '❌'} {d['name']}\n"
        rows.append([InlineKeyboardButton(f"{'❌ Отключить' if d['enabled'] else '✅ Включить'} {d['name']}", callback_data=f"district_toggle:{d['id']}")])
        rows.append([InlineKeyboardButton(f"🗑 Удалить {d['name']}", callback_data=f"district_delete:{d['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")])
    await safe_edit_query(query, text, reply_markup=kb(rows))


async def toggle_district(query, user, district_id: int):
    with db() as conn:
        d = conn.execute("SELECT * FROM districts WHERE id=?", (district_id,)).fetchone()
        if d:
            conn.execute("UPDATE districts SET enabled=? WHERE id=?", (0 if d["enabled"] else 1, district_id))
            conn.commit()
    log_action(user, "toggle_district", "district", district_id, "")
    await admin_districts(query)


async def delete_district(query, user, district_id: int):
    with db() as conn:
        conn.execute("DELETE FROM districts WHERE id=?", (district_id,))
        conn.commit()
    log_action(user, "delete_district", "district", district_id, "")
    await admin_districts(query)




async def process_order_tx_hash(context, order_id: int, user, tx_hash: str):
    """
    TON: автоматическую BTC-проверку убрали.
    hash / ссылка сохраняется как данные для ручной проверки админом.
    """
    tx_hash = (tx_hash or "").strip()
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            return None, "Заказ не найден."
        if tx_hash:
            dupe = conn.execute(
                "SELECT order_no FROM orders WHERE tx_hash=? AND id<>?",
                (tx_hash, order_id)
            ).fetchone()
            if dupe:
                return None, f"❌ Этот hash / ссылка уже указаны в заказе {dupe['order_no']}."
            conn.execute(
                "UPDATE orders SET tx_hash=?, tx_check_result=?, updated_at=? WHERE id=?",
                (tx_hash, "TON: ручная проверка админом", now_ts(), order_id)
            )
            conn.commit()
        new = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()

    log_action(user, "ton_payment_data_saved", "order", new["order_no"], tx_hash)
    return new, "⛓ Данные оплаты сохранены. TON / GRAM проверяется админом вручную по чеку / hash / ссылке."


async def verify_order_tx_hash_callback(query, context, order_id: int):
    await require_admin_query(query, query.from_user, "operator")
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        await safe_edit_query(query, "Заказ не найден.")
        return

    tx_hash = row_get(order, "tx_hash", "") or ""
    receipt = "есть" if row_get(order, "receipt_file_id", "") else "нет"

    text = (
        f"⛓ Данные оплаты TON\n\n"
        f"🧾 Заказ: {order['order_no']}\n"
        f"💰 Сумма: {order['amount']:g} ₽\n"
        f"💼 TON / GRAM кошелёк:\n{row_get(order, 'wallet_used', '') or choose_ton_wallet(order['order_no']) or '—'}\n\n"
        f"📎 Чек: {receipt}\n"
        f"⛓ hash / ссылка:\n{tx_hash or '—'}\n\n"
        f"Автопроверки TON здесь нет. Проверяй вручную в кошельке / обозревателе, затем жми “✅ Оплата получена”."
    )
    await safe_edit_query(query, text, reply_markup=order_admin_keyboard(order_id, order["user_id"], order["status"]))


async def checktx_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_client(update.effective_user)
    if not has_perm(update.effective_user.id, "operator"):
        await update.message.reply_text("⛔ Только админ.")
        return
    if not context.args:
        await update.message.reply_text("Напиши так: /checktx VT-1001")
        return
    order_no = context.args[0].strip().upper()
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE UPPER(order_no)=?", (order_no,)).fetchone()
    if not order:
        await update.message.reply_text("Заказ не найден.")
        return
    tx_hash = row_get(order, "tx_hash", "") or ""
    receipt = "есть" if row_get(order, "receipt_file_id", "") else "нет"
    await update.message.reply_text(
        f"⛓ Данные оплаты TON\n\n"
        f"🧾 Заказ: {order['order_no']}\n"
        f"💰 Сумма: {order['amount']:g} ₽\n"
        f"📎 Чек: {receipt}\n"
        f"⛓ hash / ссылка:\n{tx_hash or '—'}\n\n"
        f"Проверяй вручную, затем жми “✅ Оплата получена”.",
        reply_markup=order_admin_keyboard(order["id"], order["user_id"], order["status"])
    )


# =========================
# ADMIN ORDERS / CLIENTS
# =========================

async def send_order_to_admins(context, order, title: str):
    chat_id = get_setting("orders_chat_id")
    if not chat_id:
        return
    try:
        await context.bot.send_message(
            chat_id=int(chat_id),
            text=f"{title}\n\n{order_text(order)}",
            reply_markup=order_admin_keyboard(order["id"], order["user_id"], order["status"])
        )
    except Exception:
        logging.exception("Не смог отправить заявку в админ-группу")


async def admin_orders(query):
    with db() as conn:
        rows = conn.execute(
            f"SELECT * FROM orders WHERE status NOT IN ({','.join(['?']*len(TERMINAL_STATUSES))}) ORDER BY id DESC LIMIT 15",
            tuple(TERMINAL_STATUSES)
        ).fetchall()
    text = "🧾 Активные заказы\n\n"
    buttons = []
    if not rows:
        text += "Активных заказов нет."
    else:
        for o in rows:
            text += f"{o['order_no']} — {status_name(o['status'])} — {o['item_name']} x{o['qty']}\n"
            buttons.append([InlineKeyboardButton(f"{o['order_no']} {status_name(o['status'])}", callback_data=f"order_view:{o['id']}")])
    buttons.append([InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")])
    await safe_edit_query(query, text, reply_markup=kb(buttons))


async def show_order_admin(query, order_id: int):
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        await safe_edit_query(query, "Заказ не найден.", reply_markup=admin_menu_keyboard())
        return
    await safe_edit_query(query, order_text(order), reply_markup=order_admin_keyboard(order["id"], order["user_id"], order["status"]))


async def admin_receipts(query):
    with db() as conn:
        rows = conn.execute("SELECT * FROM orders WHERE status IN ('receipt_sent','tx_wait','paid') ORDER BY updated_at DESC LIMIT 20").fetchall()
    text = "📎 Чеки / hash на проверке\n\n"
    buttons = []
    if not rows:
        text += "Чеков и hash на проверке нет."
    else:
        for o in rows:
            text += f"{o['order_no']} — {o['item_name']} x{o['qty']} — {o['amount']:g}\n"
            buttons.append([InlineKeyboardButton(f"📎 {o['order_no']} | {o['amount']:g}", callback_data=f"order_view:{o['id']}")])
    buttons.append([InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")])
    await safe_edit_query(query, text, reply_markup=kb(buttons))


async def order_templates(query, order_id: int):
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        await safe_edit_query(query, "Заказ не найден.")
        return
    await safe_edit_query(query, 
        f"✉️ Быстрые сообщения клиенту по заказу {order['order_no']}",
        reply_markup=kb([
            [InlineKeyboardButton("💳 Пополните баланс", callback_data=f"order_tpl:{order_id}:topup")],
            [InlineKeyboardButton("📎 Пришлите чек", callback_data=f"order_tpl:{order_id}:receipt")],
            [InlineKeyboardButton("✅ Оплата подтверждена", callback_data=f"order_tpl:{order_id}:paid")],
            [InlineKeyboardButton("🚚 Заказ передан", callback_data=f"order_tpl:{order_id}:sent")],
            [InlineKeyboardButton("⬅️ Заказ", callback_data=f"order_view:{order_id}")],
        ])
    )


async def send_order_template(query, context, order_id: int, tpl: str):
    templates = {
        "topup": "💳 Перед оплатой пополните баланс и проверьте сумму. После перевода нажмите “Я оплатил” и отправьте чек.",
        "receipt": "📎 Пришлите чек / скрин оплаты по заказу. Без чека заказ не берётся в работу.",
        "paid": "✅ Оплата подтверждена. Заказ передан в работу.",
        "sent": "🚚 Заказ передан. Спасибо за обращение.",
    }
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        await safe_edit_query(query, "Заказ не найден.")
        return
    text = templates.get(tpl, "Сообщение по заказу.")
    await context.bot.send_message(chat_id=order["user_id"], text=f"🧾 Заказ {order['order_no']}\n\n{text}")
    log_action(query.from_user, "send_template", "order", order["order_no"], tpl)
    await query.answer("Отправлено клиенту.", show_alert=True)
    await show_order_admin(query, order_id)


async def send_payment_qr_to_client(context, chat_id: int, wallet_text: str):
    qr = make_wallet_qr_bytes(wallet_text)
    if not qr:
        return
    try:
        await context.bot.send_photo(chat_id=chat_id, photo=qr, caption="📲 QR-код кошелька для оплаты")
    except Exception:
        logging.exception("Не смог отправить QR клиенту")


async def admin_order_status(query, context, order_id: int, status: str, paid: bool = False):
    user = query.from_user
    await require_admin_query(query, user, "operator")
    with db() as conn:
        old = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not old:
            await safe_edit_query(query, "Заказ не найден.")
            return
        if old["status"] == status or (paid and old["status"] == "work"):
            await query.answer("Статус уже установлен.")
            return
        extra = ""
        params = [status, now_ts(), order_id]
        if status == "accepted":
            conn.execute(
                "UPDATE orders SET status=?, updated_at=?, accepted_by=?, accepted_by_name=? WHERE id=?",
                (status, now_ts(), user.id, admin_name(user), order_id)
            )
        elif paid:
            conn.execute(
                "UPDATE orders SET status='work', updated_at=?, paid_at=? WHERE id=?",
                (now_ts(), now_ts(), order_id)
            )
        elif status == "sent":
            conn.execute(
                "UPDATE orders SET status=?, updated_at=?, sent_at=? WHERE id=?",
                (status, now_ts(), now_ts(), order_id)
            )
        else:
            conn.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?", params)
        conn.commit()
        new = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()

    action = "payment_confirmed" if paid else f"set_order_{status}"
    log_action(user, action, "order", new["order_no"], "")
    await notify_client_status(context, new)
    if paid and bool_setting("digital_delivery_enabled"):
        ok, delivery_msg = await fulfill_digital_order(context, order_id, source="admin manual")
        if ok:
            with db() as conn:
                delivered_order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            await safe_edit_query(
                query,
                order_text(delivered_order) + f"\n\n🤖 {delivery_msg}",
                reply_markup=order_admin_keyboard(delivered_order["id"], delivered_order["user_id"], delivered_order["status"])
            )
            return
        await query.message.reply_text(f"⚠️ Оплата подтверждена, но автовыдача не выполнена: {delivery_msg}")
    await safe_edit_query(query, order_text(new), reply_markup=order_admin_keyboard(new["id"], new["user_id"], new["status"]))


async def close_order(query, context, order_id: int):
    user = query.from_user
    await require_admin_query(query, user, "operator")
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            await safe_edit_query(query, "Заказ не найден.")
            return
        if order["status"] == "closed":
            await query.answer("Заказ уже закрыт.")
            return
        now = now_ts()
        conn.execute("UPDATE orders SET status='closed', updated_at=?, closed_at=? WHERE id=?", (now, now, order_id))
        conn.execute("UPDATE clients SET purchases=purchases+1 WHERE user_id=?", (order["user_id"],))
        item = conn.execute("SELECT * FROM items WHERE id=?", (order["item_id"],)).fetchone()
        if item and item["stock"] is not None:
            new_stock = max(0, int(item["stock"]) - int(order["qty"]))
            new_status = item["status"]
            if new_stock <= 0:
                new_status = "hidden"
            conn.execute("UPDATE items SET stock=?, status=?, updated_at=? WHERE id=?", (new_stock, new_status, now, item["id"]))
        conn.commit()
        new = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()

    log_action(user, "close_order_add_purchase", "order", new["order_no"], "+1 purchase")
    await notify_client_status(context, new, extra="📦 Покупка засчитана в твой VIP-статус.")
    await safe_edit_query(query, order_text(new), reply_markup=order_admin_keyboard(new["id"], new["user_id"], new["status"]))


async def receipt_reject_prompt(query, context, order_id: int):
    user = query.from_user
    await require_admin_query(query, user, "operator")
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        await safe_edit_query(query, "Заказ не найден.")
        return
    context.user_data["awaiting"] = {"type": "receipt_reject_reason", "order_id": order_id}
    await safe_edit_query(query, 
        f"❌ Укажи причину отклонения чека по заказу {order['order_no']}.\n\n"
        "Например: сумма не совпадает / чек не читается / перевод не найден.",
        reply_markup=kb([[InlineKeyboardButton("⬅️ Заказ", callback_data=f"order_view:{order_id}")]])
    )


async def admin_cancel_order_prompt(query, context, order_id: int):
    await require_admin_query(query, query.from_user, "operator")
    context.user_data["awaiting"] = {"type": "cancel_reason", "order_id": order_id}
    await safe_edit_query(query, "❌ Напиши причину отмены заказа.", reply_markup=kb([[InlineKeyboardButton("⬅️ Заказы", callback_data="admin_orders")]]))


async def notify_client_status(context, order, extra: str = ""):
    try:
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=f"🧾 Заказ {order['order_no']}\nСтатус изменён: {status_name(order['status'])}\n{extra}",
            reply_markup=client_order_keyboard(order["id"], order["status"])
        )
    except Exception:
        logging.exception("Не смог уведомить клиента")


def client_card_keyboard(user_id: int):
    return kb([
        [InlineKeyboardButton("📝 Заметка", callback_data=f"client_note:{user_id}")],
        [InlineKeyboardButton("🚫 Стоп заявки", callback_data=f"client_ban:{user_id}"), InlineKeyboardButton("✅ Снять стоп", callback_data=f"client_unban:{user_id}")],
        [InlineKeyboardButton("💬 Написать", url=f"tg://user?id={user_id}")],
        [InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")]
    ])


async def ban_client_orders(query, user, user_id: int):
    with db() as conn:
        conn.execute("UPDATE clients SET order_banned_until=?, order_ban_reason=? WHERE user_id=?", (now_ts()+ORDER_SPAM_BLOCK_SECONDS, "админский стоп", user_id))
        conn.commit()
    log_action(user, "orderban_client", "client", user_id, "")
    await safe_edit_query(query, client_card_text(user_id), reply_markup=client_card_keyboard(user_id))


async def unban_client_orders(query, user, user_id: int):
    with db() as conn:
        conn.execute("UPDATE clients SET order_banned_until=0, order_ban_reason='' WHERE user_id=?", (user_id,))
        conn.commit()
    log_action(user, "orderunban_client", "client", user_id, "")
    await safe_edit_query(query, client_card_text(user_id), reply_markup=client_card_keyboard(user_id))


async def admin_clients(query):
    with db() as conn:
        rows = conn.execute("SELECT * FROM clients ORDER BY last_seen DESC LIMIT 15").fetchall()
    text = "👥 Последние клиенты\n\n"
    buttons = []
    for c in rows:
        name = mention_text(c["user_id"], c["username"], c["first_name"])
        text += f"{name} — {c['purchases']} покупок\n"
        buttons.append([InlineKeyboardButton(name, callback_data=f"client_card:{c['user_id']}")])
    buttons.append([InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")])
    await safe_edit_query(query, text, reply_markup=kb(buttons))


async def digital_menu(query):
    await safe_edit_query(
        query,
        "🤖 Автоматическая оплата и цифровая выдача\n\n"
        "Каждая позиция витрины имеет собственную очередь фотографий. "
        "Фото выдаются строго по порядку и не повторяются.",
        reply_markup=digital_delivery_menu_keyboard()
    )


async def digital_choose_item(query, action: str):
    with db() as conn:
        items = conn.execute("SELECT * FROM items ORDER BY id DESC").fetchall()
    rows = []
    text = "📦 Выбери конкретную позицию витрины:\n\n"
    for item in items:
        counts = digital_stock_counts(item["id"])
        rows.append([
            InlineKeyboardButton(
                f"#{item['id']} {item['name']} | осталось {counts['available']}",
                callback_data=f"digital_{action}_item:{item['id']}"
            )
        ])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="digital_menu")])
    await safe_edit_query(query, text, reply_markup=kb(rows))


async def digital_stock_menu(query):
    with db() as conn:
        items = conn.execute("SELECT * FROM items ORDER BY id DESC").fetchall()
    text = "📊 Цифровой склад по позициям\n\n"
    rows = []
    for item in items:
        c = digital_stock_counts(item["id"])
        text += (
            f"#{item['id']} {item['name']}\n"
            f"Всего: {c['total']} | Выдано: {c['delivered']} | Осталось: {c['available']}\n\n"
        )
        rows.append([InlineKeyboardButton(f"📤 Пополнить #{item['id']}", callback_data=f"digital_upload_item:{item['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="digital_menu")])
    await safe_edit_query(query, text or "Склад пуст.", reply_markup=kb(rows))


async def digital_history_menu(query):
    with db() as conn:
        rows_db = conn.execute(
            """
            SELECT a.seq_no, a.delivered_at, o.order_no, o.item_name, o.username, o.user_id
            FROM digital_assets a
            JOIN orders o ON o.id=a.delivered_order_id
            WHERE a.status='delivered'
            ORDER BY a.delivered_at DESC
            LIMIT 20
            """
        ).fetchall()
    text = "📋 Последние выдачи\n\n"
    if not rows_db:
        text += "Выдач пока нет."
    for row in rows_db:
        who = f"@{row['username']}" if row["username"] else str(row["user_id"])
        text += f"{row['order_no']} | {row['item_name']} | фото #{row['seq_no']} | {who}\n"
    await safe_edit_query(query, text, reply_markup=kb([[InlineKeyboardButton("⬅️ Назад", callback_data="digital_menu")]]))


async def client_check_payment(query, context, order_id: int):
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, query.from_user.id)).fetchone()
    if not order:
        await query.answer("Заказ не найден.", show_alert=True)
        return
    if order["status"] == "closed" and row_get(order, "delivery_asset_id"):
        await query.answer("Оплата подтверждена, товар уже выдан.", show_alert=True)
        return
    await query.answer("Проверяю блокчейн…", show_alert=False)
    found = await check_ton_payments_once(context)
    with db() as conn:
        current = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if current["status"] == "closed":
        await safe_edit_query(query, "✅ Оплата найдена. Фото уже отправлено тебе.", reply_markup=main_menu_keyboard(False))
    else:
        await safe_edit_query(
            query,
            f"⏳ Оплата заказа {order['order_no']} пока не найдена.\n\n"
            "Проверь:\n"
            "• сеть TON;\n"
            "• точную сумму;\n"
            "• комментарий / memo с номером заказа.",
            reply_markup=payment_keyboard(order_id)
        )




# =========================
# MESSAGE INPUTS
# =========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    update_client(user)
    expire_orders()

    awaiting = context.user_data.get("awaiting")
    if not awaiting:
        return

    typ = awaiting.get("type")
    msg = update.message

    if typ in ("receipt", "payment_proof"):
        order_id = awaiting["order_id"]

        if typ == "payment_proof" and msg.text:
            tx_hash = msg.text.strip()
            with db() as conn:
                order = conn.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, user.id)).fetchone()
                if not order:
                    await msg.reply_text("Заказ не найден.")
                    context.user_data.pop("awaiting", None)
                    return
                conn.execute(
                    "UPDATE orders SET status='receipt_sent', tx_hash=?, receipt_at=?, updated_at=? WHERE id=?",
                    (tx_hash, now_ts(), now_ts(), order_id)
                )
                conn.commit()
                new = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            context.user_data.pop("awaiting", None)
            await msg.reply_text(f"⛓ hash / ссылка по заказу {new['order_no']} отправлены на проверку.")
            await send_order_to_admins(context, new, "⛓ Клиент отправил TON hash / ссылку")
            log_action(user, "send_ton_hash", "order", new["order_no"], tx_hash)
            return
        file_id = None
        file_type = None
        if msg.photo:
            file_id = msg.photo[-1].file_id
            file_type = "photo"
        elif msg.document:
            file_id = msg.document.file_id
            file_type = "document"
        else:
            if typ == "payment_proof" and msg.text:
                await msg.reply_text("📎 Это не похоже на hash. Лучше отправь чек / скрин оплаты фото или документом. Если hash нет — админ проверит вручную.")
            else:
                await msg.reply_text("📎 Отправь чек фото или документом.")
            return

        with db() as conn:
            order = conn.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, user.id)).fetchone()
            if not order:
                await msg.reply_text("Заказ не найден.")
                context.user_data.pop("awaiting", None)
                return
            conn.execute(
                "UPDATE orders SET status='receipt_sent', receipt_file_id=?, receipt_file_type=?, receipt_at=?, updated_at=? WHERE id=?",
                (file_id, file_type, now_ts(), now_ts(), order_id)
            )
            conn.commit()
            new = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()

        await msg.reply_text(f"📎 Чек по заказу {new['order_no']} отправлен на проверку.")
        await send_order_to_admins(context, new, "📎 Клиент отправил чек")
        await forward_receipt_to_admins(context, new)
        log_action(user, "send_receipt", "order", new["order_no"], file_type)
        context.user_data.pop("awaiting", None)
        return

    if typ == "picture_set":
        if not msg.photo:
            await msg.reply_text("🖼 Пришли картинку как фото.")
            return
        key = awaiting["key"]
        set_setting(key, msg.photo[-1].file_id)
        context.user_data.pop("awaiting", None)
        log_action(user, "set_picture", "settings", key, "")
        await msg.reply_text("✅ Картинка сохранена.", reply_markup=admin_menu_keyboard())
        return

    if typ == "restore_db":
        if not msg.document:
            await msg.reply_text("♻️ Пришли backup-файл .sqlite3 как документ.")
            return
        backup_before = DATA_DIR / f"before_restore_{now_ts()}.sqlite3"
        if DB_PATH.exists():
            shutil.copy(DB_PATH, backup_before)
        file = await context.bot.get_file(msg.document.file_id)
        tmp = DATA_DIR / f"restore_{now_ts()}.sqlite3"
        await file.download_to_drive(tmp)
        shutil.copy(tmp, DB_PATH)
        init_db()
        context.user_data.pop("awaiting", None)
        await msg.reply_text("♻️ База восстановлена. Старая база сохранена рядом как before_restore.", reply_markup=admin_menu_keyboard())
        return

    if typ == "digital_upload":
        item_id = int(awaiting["item_id"])
        if not msg.photo:
            await msg.reply_text("📷 Отправь фотографию. Для завершения нажми кнопку.")
            return
        photo = msg.photo[-1]
        with db() as conn:
            next_seq = conn.execute(
                "SELECT COALESCE(MAX(seq_no), 0) + 1 n FROM digital_assets WHERE item_id=?",
                (item_id,)
            ).fetchone()["n"]
            try:
                conn.execute(
                    """
                    INSERT INTO digital_assets(
                      item_id, seq_no, file_id, file_unique_id, status,
                      uploaded_by, created_at
                    ) VALUES(?, ?, ?, ?, 'available', ?, ?)
                    """,
                    (item_id, next_seq, photo.file_id, photo.file_unique_id, user.id, now_ts())
                )
                conn.commit()
            except sqlite3.IntegrityError:
                await msg.reply_text("⚠️ Это фото уже загружено.")
                return
        counts = digital_stock_counts(item_id)
        await msg.reply_text(
            f"✅ Фото #{next_seq} добавлено.\nОсталось на складе: {counts['available']}",
            reply_markup=kb([[InlineKeyboardButton("✅ Завершить загрузку", callback_data="digital_upload_finish")]])
        )
        return

    if not msg.text:
        await msg.reply_text("Нужен текст.")
        return

    text = msg.text.strip()

    if typ == "wallet":
        wallets = ton_wallets_list()
        text_clean = normalize_wallet_line(text)
        if text_clean:
            wallets = [text_clean] + [w for w in wallets if w != text_clean]
            save_ton_wallets(wallets)
        log_action(user, "set_primary_ton_wallet", "settings", "wallet", "через кнопку")
        context.user_data.pop("awaiting", None)
        await msg.reply_text("✅ Основной TON / GRAM кошелёк сохранён первым в списке.", reply_markup=admin_menu_keyboard())
    elif typ == "wallet_add":
        wallets = add_ton_wallet(text)
        log_action(user, "add_ton_wallet", "settings", "wallets", f"count={len(wallets)}")
        context.user_data.pop("awaiting", None)
        await msg.reply_text(f"✅ TON / GRAM кошелёк добавлен. Всего кошельков: {len(wallets)}", reply_markup=admin_menu_keyboard())
    elif typ == "btc_reserve_wallet":
        set_setting("btc_reserve_wallet_text", text)
        log_action(user, "set_btc_reserve_wallet", "settings", "btc_reserve", "через кнопку")
        context.user_data.pop("awaiting", None)
        await msg.reply_text("✅ BTC резервный кошелёк сохранён. Клиентам автоматически не показывается.", reply_markup=admin_menu_keyboard())
    elif typ == "ton_rub_rate":
        try:
            rate = float(text.replace(",", "."))
            if rate <= 0:
                raise ValueError
        except ValueError:
            await msg.reply_text("Курс должен быть положительным числом.")
            return
        set_setting("ton_rub_rate", str(rate))
        context.user_data.pop("awaiting", None)
        await msg.reply_text(
            f"✅ Курс сохранён: 1 TON = {rate:g} ₽",
            reply_markup=admin_menu_keyboard()
        )
    elif typ == "seed_price":
        try:
            price = float(text.replace(",", "."))
        except ValueError:
            await msg.reply_text("Цена должна быть числом.")
            return
        set_setting("seed_price", str(price))
        log_action(user, "set_price", "settings", "seed_price", str(price))
        context.user_data.pop("awaiting", None)
        await msg.reply_text(f"✅ Цена за 1 шт. сохранена: {price:g}", reply_markup=admin_menu_keyboard())
    elif typ == "district_name":
        with db() as conn:
            conn.execute("INSERT INTO districts(name, enabled, created_at) VALUES(?, 1, ?)", (text, now_ts()))
            conn.commit()
        log_action(user, "add_district", "district", text, "")
        context.user_data.pop("awaiting", None)
        await msg.reply_text(f"✅ Район добавлен: {text}", reply_markup=admin_menu_keyboard())
    elif typ == "type_emoji":
        emoji = text.strip()
        if len(emoji) > 20:
            await msg.reply_text("Слишком длинно. Пришли просто смайлик или короткий знак.")
            return
        with db() as conn:
            conn.execute("INSERT INTO item_types(emoji, enabled, created_at) VALUES(?, 1, ?)", (emoji, now_ts()))
            conn.commit()
        log_action(user, "add_type", "type", emoji, "")
        context.user_data.pop("awaiting", None)
        await msg.reply_text(f"✅ Тип добавлен: {emoji}", reply_markup=admin_menu_keyboard())
    elif typ == "item_name":
        context.user_data["awaiting"] = {"type": "item_desc", "name": text}
        await msg.reply_text("📝 Пришли описание позиции. Можно написать “-”, если описание не нужно.")
    elif typ == "item_desc":
        name = awaiting["name"]
        desc = "" if text == "-" else text
        context.user_data["awaiting"] = {"type": "item_stock_new", "name": name, "desc": desc}
        await msg.reply_text("📦 Пришли остаток, шт. числом. Если остаток не хочешь учитывать — напиши -")
    elif typ == "item_stock_new":
        name = awaiting["name"]
        desc = awaiting["desc"]
        stock = None
        if text != "-":
            try:
                stock = int(text)
            except ValueError:
                await msg.reply_text("Остаток должен быть числом или -")
                return
        with db() as conn:
            conn.execute(
                "INSERT INTO items(name, description, status, stock, created_at, updated_at) VALUES(?, ?, 'in_stock', ?, ?, ?)",
                (name, desc, stock, now_ts(), now_ts())
            )
            conn.commit()
        log_action(user, "add_item", "item", name, f"stock={stock}")
        context.user_data.pop("awaiting", None)
        await msg.reply_text(f"✅ Позиция добавлена: {name}", reply_markup=admin_menu_keyboard())
    elif typ == "item_stock":
        item_id = awaiting["item_id"]
        try:
            stock = int(text)
        except ValueError:
            await msg.reply_text("Остаток должен быть числом.")
            return
        with db() as conn:
            conn.execute("UPDATE items SET stock=?, updated_at=? WHERE id=?", (stock, now_ts(), item_id))
            conn.commit()
        log_action(user, "set_item_stock", "item", item_id, str(stock))
        context.user_data.pop("awaiting", None)
        await msg.reply_text(f"✅ Остаток обновлён: {stock}", reply_markup=admin_menu_keyboard())
    elif typ == "client_note":
        uid = awaiting["user_id"]
        with db() as conn:
            conn.execute("UPDATE clients SET notes=? WHERE user_id=?", (text, uid))
            conn.commit()
        log_action(user, "set_client_note", "client", uid, text)
        context.user_data.pop("awaiting", None)
        await msg.reply_text("✅ Заметка сохранена.", reply_markup=client_card_keyboard(uid))
    elif typ == "order_amount":
        order_id = awaiting["order_id"]
        try:
            amount = float(text.replace(",", "."))
        except ValueError:
            await msg.reply_text("Сумма должна быть числом.")
            return
        with db() as conn:
            order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not order:
                await msg.reply_text("Заказ не найден.")
                context.user_data.pop("awaiting", None)
                return
            conn.execute("UPDATE orders SET amount=?, updated_at=? WHERE id=?", (amount, now_ts(), order_id))
            conn.commit()
            new = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        log_action(user, "change_order_amount", "order", new["order_no"], str(amount))
        context.user_data.pop("awaiting", None)
        await msg.reply_text(f"✅ Сумма заказа {new['order_no']} изменена: {amount:g}", reply_markup=order_admin_keyboard(order_id, new["user_id"], new["status"]))
    elif typ == "receipt_reject_reason":
        order_id = awaiting["order_id"]
        with db() as conn:
            order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not order:
                await msg.reply_text("Заказ не найден.")
                context.user_data.pop("awaiting", None)
                return
            new_expires = now_ts() + PAYMENT_TTL_SECONDS
            conn.execute(
                "UPDATE orders SET status='awaiting_payment', receipt_file_id='', receipt_file_type='', expires_at=?, updated_at=? WHERE id=?",
                (new_expires, now_ts(), order_id)
            )
            conn.commit()
            new = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        log_action(user, "receipt_rejected", "order", new["order_no"], text)
        try:
            await context.bot.send_message(
                chat_id=new["user_id"],
                text=f"❌ Чек по заказу {new['order_no']} отклонён.\nПричина: {text}\n\nПроверь оплату и отправь чек заново.",
                reply_markup=payment_keyboard(order_id)
            )
        except Exception:
            logging.exception("Не смог уведомить клиента об отклонении чека")
        context.user_data.pop("awaiting", None)
        await msg.reply_text(f"❌ Чек по заказу {new['order_no']} отклонён. Причина отправлена клиенту.", reply_markup=order_admin_keyboard(order_id, new["user_id"], new["status"]))
    elif typ == "text_edit":
        key = awaiting["key"]
        set_setting(key, text)
        log_action(user, "edit_text", "settings", key, "")
        context.user_data.pop("awaiting", None)
        await msg.reply_text(f"✅ Текст сохранён: {TEXT_MENU_KEYS.get(key, key)}", reply_markup=admin_menu_keyboard())
    elif typ == "admin_add_id":
        try:
            uid = int(text)
        except ValueError:
            await msg.reply_text("Нужен Telegram ID числом.")
            return
        context.user_data.pop("awaiting", None)
        await msg.reply_text("Выбери роль:", reply_markup=kb([
            [InlineKeyboardButton("🛡 Старший админ", callback_data=f"admin_set_role:{uid}:admin")],
            [InlineKeyboardButton("📦 Оператор", callback_data=f"admin_set_role:{uid}:operator")],
            [InlineKeyboardButton("👀 Наблюдатель", callback_data=f"admin_set_role:{uid}:viewer")],
            [InlineKeyboardButton("⬅️ Админы", callback_data="admins_menu")],
        ]))
    elif typ in ("broadcast_all", "broadcast_vip"):
        target = "vip" if typ == "broadcast_vip" else "all"
        context.user_data["broadcast_pending"] = {"target": target, "text": text}
        context.user_data.pop("awaiting", None)
        await msg.reply_text(f"📣 Предпросмотр рассылки:\n\n{text}\n\nОтправить?", reply_markup=kb([
            [InlineKeyboardButton("✅ Отправить", callback_data="broadcast_confirm")],
            [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel")],
        ]))
    elif typ == "cancel_reason":
        order_id = awaiting["order_id"]
        with db() as conn:
            order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not order:
                await msg.reply_text("Заказ не найден.")
                context.user_data.pop("awaiting", None)
                return
            conn.execute(
                "UPDATE orders SET status='cancelled', updated_at=?, cancelled_at=?, cancel_reason=? WHERE id=?",
                (now_ts(), now_ts(), text, order_id)
            )
            conn.commit()
            new = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        log_action(user, "admin_cancel_order", "order", new["order_no"], text)
        await notify_client_status(context, new, extra=f"Причина: {text}")
        context.user_data.pop("awaiting", None)
        await msg.reply_text(f"❌ Заказ {new['order_no']} отменён.", reply_markup=admin_menu_keyboard())



async def forward_receipt_to_admins(context, order):
    """
    Чек больше не летит картинкой в админ-группу автоматически.
    В группу приходит только короткое уведомление и кнопки.
    Фото/документ можно показать вручную кнопкой “📎 Показать чек”.
    """
    chat_id = get_setting("orders_chat_id")
    if not chat_id:
        return
    caption = (
        f"📎 Чек получен по заказу {order['order_no']}\n"
        f"💰 Сумма: {order['amount']:g} ₽\n\n"
        f"Фото скрыто, чтобы не засорять группу.\n"
        f"Нажми “📎 Показать чек”, если нужно открыть файл."
    )
    try:
        await context.bot.send_message(
            chat_id=int(chat_id),
            text=caption,
            reply_markup=order_admin_keyboard(order["id"], order["user_id"], order["status"])
        )
    except Exception:
        logging.exception("Не смог отправить уведомление о чеке админам")


async def show_receipt_to_admin(query, context, order_id: int):
    await require_admin_query(query, query.from_user, "operator")
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        await safe_edit_query(query, "Заказ не найден.")
        return
    file_id = row_get(order, "receipt_file_id", "") or ""
    file_type = row_get(order, "receipt_file_type", "") or ""
    if not file_id:
        await query.answer("Чек ещё не прикреплён.", show_alert=True)
        return

    caption = f"📎 Чек по заказу {order['order_no']}\n💰 Сумма: {order['amount']:g}"
    try:
        if file_type == "photo":
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=file_id,
                caption=caption,
                reply_markup=order_admin_keyboard(order["id"], order["user_id"], order["status"])
            )
        else:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=file_id,
                caption=caption,
                reply_markup=order_admin_keyboard(order["id"], order["user_id"], order["status"])
            )
    except Exception:
        logging.exception("Не смог показать чек")
        await query.message.reply_text("⚠️ Не смог показать чек.")




async def stock_menu(query):
    with db() as conn:
        items = conn.execute("SELECT * FROM items ORDER BY id DESC LIMIT 30").fetchall()
    text = "📦 Склад / остатки\n\n"
    rows = []
    if not items:
        text += "Позиции пока не добавлены."
    for it in items:
        stock = "∞" if it["stock"] is None else str(it["stock"])
        text += f"{it['name']} — остаток: {stock}\n"
        rows.append([InlineKeyboardButton(f"📦 {it['name']} | {stock}", callback_data=f"item_manage:{it['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")])
    await safe_edit_query(query, text, reply_markup=kb(rows))


async def texts_menu(query):
    rows = []
    for key, label in TEXT_MENU_KEYS.items():
        rows.append([InlineKeyboardButton(f"✏️ {label}", callback_data=f"text_edit:{key}"), InlineKeyboardButton("👁", callback_data=f"text_preview:{key}")])
    rows.append([InlineKeyboardButton("♻️ Сбросить основные", callback_data="texts_reset")])
    rows.append([InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")])
    await safe_edit_query(query, "📜 Тексты\n\nМожно менять тексты без GitHub и Railway.", reply_markup=kb(rows))


async def pictures_menu(query):
    rows = []
    for key, label in PICTURE_MENU_KEYS.items():
        mark = "✅" if get_setting(key) else "❌"
        rows.append([InlineKeyboardButton(f"{mark} {label}", callback_data=f"picture_set:{key}"), InlineKeyboardButton("🗑", callback_data=f"picture_clear:{key}")])
    rows.append([InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")])
    await safe_edit_query(query, "🖼 Картинки\n\nВыбери раздел и пришли фото боту.", reply_markup=kb(rows))


async def admins_menu(query):
    with db() as conn:
        rows_db = conn.execute("SELECT * FROM admins ORDER BY added_at DESC").fetchall()
    text = "👑 Админы\n\n"
    rows = [[InlineKeyboardButton("➕ Добавить админа", callback_data="admin_add_prompt")]]
    if not rows_db:
        text += "Админов в базе нет."
    for a in rows_db:
        text += f"{a['role']} — {a['user_id']} {('@'+a['username']) if a['username'] else ''}\n"
        if a['role'] != 'owner':
            rows.append([InlineKeyboardButton(f"🗑 Убрать {a['user_id']}", callback_data=f"admin_remove:{a['user_id']}")])
    rows.append([InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")])
    await safe_edit_query(query, text, reply_markup=kb(rows))


async def set_admin_role_menu(query, user, uid: int, role: str):
    with db() as conn:
        conn.execute("""INSERT INTO admins(user_id, role, username, first_name, added_at)
                        VALUES(?, ?, '', '', ?)
                        ON CONFLICT(user_id) DO UPDATE SET role=excluded.role""", (uid, role, now_ts()))
        conn.commit()
    log_action(user, "set_admin_role", "admin", uid, role)
    await admins_menu(query)


async def remove_admin_menu(query, user, uid: int):
    with db() as conn:
        conn.execute("DELETE FROM admins WHERE user_id=? AND role!='owner'", (uid,))
        conn.commit()
    log_action(user, "remove_admin", "admin", uid, "")
    await admins_menu(query)


async def broadcast_menu(query):
    await safe_edit_query(query, "📣 Рассылка\n\nСначала будет предпросмотр, потом подтверждение.", reply_markup=kb([
        [InlineKeyboardButton("📣 Всем клиентам", callback_data="broadcast_all")],
        [InlineKeyboardButton("👑 Только с покупками", callback_data="broadcast_vip")],
        [InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")],
    ]))


async def do_broadcast(query, context):
    pending = context.user_data.get("broadcast_pending")
    if not pending:
        await safe_edit_query(query, "Нет рассылки на подтверждение.", reply_markup=admin_menu_keyboard())
        return
    target, text = pending["target"], pending["text"]
    with db() as conn:
        if target == "vip":
            rows = conn.execute("SELECT user_id FROM clients WHERE purchases>0").fetchall()
        else:
            rows = conn.execute("SELECT user_id FROM clients").fetchall()
    sent = 0
    for r in rows:
        try:
            await context.bot.send_message(chat_id=r["user_id"], text=text)
            sent += 1
        except Exception:
            pass
    context.user_data.pop("broadcast_pending", None)
    log_action(query.from_user, "broadcast", "clients", target, f"sent={sent}")
    await safe_edit_query(query, f"📣 Рассылка отправлена. Получателей: {sent}", reply_markup=admin_menu_keyboard())


async def security_menu(query):
    await safe_edit_query(query, "🛡 Безопасность", reply_markup=kb([
        [InlineKeyboardButton(f"{'✅' if bool_setting('service_mode') else '❌'} Режим обслуживания", callback_data="toggle_setting:service_mode")],
        [InlineKeyboardButton(f"{'✅' if bool_setting('verified_only') else '❌'} Только проверенные", callback_data="toggle_setting:verified_only")],
        [InlineKeyboardButton(f"{'✅' if bool_setting('test_mode') else '❌'} Тестовый режим", callback_data="toggle_setting:test_mode")],
        [InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")],
    ]))


async def backup_menu(query):
    await safe_edit_query(query, "🧱 Backup / Restore\n\nBackup — скачать базу.\nRestore — восстановить из backup-файла.", reply_markup=kb([
        [InlineKeyboardButton("🧱 Backup сейчас", callback_data="backup_now")],
        [InlineKeyboardButton("📤 Экспорт CSV", callback_data="admin_export")],
        [InlineKeyboardButton("♻️ Restore из файла", callback_data="restore_start")],
        [InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")],
    ]))


async def system_menu(query):
    text = (
        f"⚙️ Система MASTER HOUSE\n\n"
        f"Версия: v7.0\n"
        f"База: {DB_PATH}\n"
        f"Заказы: {'включены' if bool_setting('orders_enabled') else 'пауза'}\n"
        f"Обслуживание: {'да' if bool_setting('service_mode') else 'нет'}\n"
        f"Группа заявок: {get_setting('orders_chat_id') or '—'}\n"
        f"Последний backup: {fmt_dt(get_setting('last_backup_ts','0'))}\n"
    )
    await safe_edit_query(query, text, reply_markup=kb([
        [InlineKeyboardButton("🩺 Проверка", callback_data="admin_ready_check")],
        [InlineKeyboardButton("🧱 Backup", callback_data="backup_now")],
        [InlineKeyboardButton("⬅️ Админ-меню", callback_data="admin_menu")],
    ]))

# =========================
# REPORT / EXPORT / BACKUP
# =========================

def daily_report_text() -> str:
    since = now_ts() - 86400
    with db() as conn:
        new_orders = conn.execute("SELECT COUNT(*) c FROM orders WHERE created_at>=?", (since,)).fetchone()["c"]
        closed = conn.execute("SELECT COUNT(*) c FROM orders WHERE closed_at>=?", (since,)).fetchone()["c"]
        cancelled = conn.execute("SELECT COUNT(*) c FROM orders WHERE cancelled_at>=?", (since,)).fetchone()["c"]
        paid = conn.execute("SELECT COUNT(*) c FROM orders WHERE paid_at>=?", (since,)).fetchone()["c"]
        revenue = conn.execute("SELECT COALESCE(SUM(amount),0) s FROM orders WHERE closed_at>=?", (since,)).fetchone()["s"]
        clients = conn.execute("SELECT COUNT(*) c FROM clients WHERE first_seen>=?", (since,)).fetchone()["c"]
    return (
        "📊 Отчёт за 24 часа\n\n"
        f"🧾 Новых заказов: {new_orders}\n"
        f"💰 Подтверждено оплат: {paid}\n"
        f"✅ Закрыто: {closed}\n"
        f"❌ Отменено/просрочено: {cancelled}\n"
        f"👥 Новых клиентов: {clients}\n"
        f"💵 Сумма закрытых: {revenue:g} ₽"
    )


def logs_text() -> str:
    with db() as conn:
        rows = conn.execute("SELECT * FROM action_logs ORDER BY id DESC LIMIT 20").fetchall()
    if not rows:
        return "🧾 Лог пуст."
    lines = ["🧾 Последние действия:\n"]
    for r in rows:
        lines.append(f"{fmt_dt(r['ts'])} — {r['admin_name']} — {r['action']} — {r['target_type']} {r['target_id']}")
    return "\n".join(lines)


async def send_backup(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    with open(DB_PATH, "rb") as f:
        await context.bot.send_document(chat_id=chat_id, document=f, filename="veles_master_house_backup.sqlite3", caption="🧱 Backup базы VELES MASTER HOUSE")
    set_setting("last_backup_ts", str(now_ts()))


async def send_exports(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clients_csv = tmp / "clients_export.csv"
        orders_csv = tmp / "orders_export.csv"

        with db() as conn:
            clients = conn.execute("SELECT * FROM clients ORDER BY last_seen DESC").fetchall()
            orders = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()

        with clients_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["user_id", "username", "first_name", "purchases", "notes", "last_seen"])
            for c in clients:
                writer.writerow([c["user_id"], c["username"], c["first_name"], c["purchases"], c["notes"], fmt_dt(c["last_seen"])])

        with orders_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["order_no", "user_id", "username", "item", "qty", "district", "amount", "status", "created_at"])
            for o in orders:
                writer.writerow([o["order_no"], o["user_id"], o["username"], o["item_name"], o["qty"], o["district_name"], o["amount"], o["status"], fmt_dt(o["created_at"])])

        with clients_csv.open("rb") as f:
            await context.bot.send_document(chat_id=chat_id, document=f, filename="clients_export.csv", caption="📤 Экспорт клиентов")
        with orders_csv.open("rb") as f:
            await context.bot.send_document(chat_id=chat_id, document=f, filename="orders_export.csv", caption="📤 Экспорт заказов")


# =========================
# MAIN
# =========================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN. Добавь BOT_TOKEN в Railway Variables.")
    init_db()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init_v7).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("setup", setup_cmd))
    app.add_handler(CommandHandler("pin", pin_cmd))
    app.add_handler(CommandHandler("setorderschat", setorderschat_cmd))
    app.add_handler(CommandHandler("setwallet", setwallet_cmd))
    app.add_handler(CommandHandler("setprice", setprice_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("restore", restore_cmd))
    app.add_handler(CommandHandler("rulesfix", rulesfix_cmd))
    app.add_handler(CommandHandler("textfix", textfix_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("setwelcomephoto", setwelcomephoto_cmd))
    app.add_handler(CommandHandler("clearwelcomephoto", clearwelcomephoto_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("findorder", findorder_cmd))
    app.add_handler(CommandHandler("findclient", findclient_cmd))
    app.add_handler(CommandHandler("checktx", checktx_cmd))

    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    logging.warning("VELES BOT v7.2 PUBLIC TONCENTER NO KEY запущен.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
