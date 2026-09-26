import os
import secrets
import logging
from datetime import datetime, timedelta, timezone

import aiosqlite
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Update,
)

from dotenv import load_dotenv


# =========================
# الإعدادات
# =========================

load_dotenv()

TOKEN = os.getenv("6697835631:AAE-isBrECs3BY3zUgKfifqoPM6nu6NBe6s", "").strip()
ADMIN_ID = int(os.getenv("1792685788", "0"))

BASE_URL = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")

PORT = int(os.getenv("PORT", "10000"))
DB_PATH = os.getenv("DB_PATH", "bot.db")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or secrets.token_urlsafe(32)

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not BASE_URL:
    raise RuntimeError("WEBHOOK_BASE_URL is missing")


logging.basicConfig(level=logging.INFO)

bot = Bot(
    TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


# =========================
# الكيبوردات
# =========================

def make_keyboard(rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=data
                )
                for text, data in row
            ]
            for row in rows
        ]
    )


def home_keyboard(admin=False):

    rows = [
        [
            ("🎯 كسب النقاط", "earn"),
            ("💰 رصيدي", "balance")
        ],
        [
            ("📢 تمويل قناتي", "fund"),
            ("📊 حملاتي", "campaigns")
        ],
        [
            ("📋 المهام", "tasks"),
            ("🎁 الهدية اليومية", "gift")
        ],
        [
            ("👥 دعواتي", "ref"),
            ("🧾 السجل", "history")
        ],
        [
            ("ℹ️ المساعدة", "help")
        ]
    ]

    if admin:
        rows.append([
            ("🛠 لوحة الإدارة", "admin")
        ])

    return make_keyboard(rows)


def back_keyboard():

    return make_keyboard([
        [
            ("⬅️ الرئيسية", "home")
        ]
    ])


# =========================
# قاعدة البيانات
# =========================

def current_time():

    return datetime.now(timezone.utc).isoformat()


async def database():

    return await aiosqlite.connect(DB_PATH)


async def initialize_database():

    async with await database() as db:

        await db.executescript("""

        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS users(

            id INTEGER PRIMARY KEY,

            username TEXT,

            first_name TEXT,

            points INTEGER DEFAULT 0,

            referred_by INTEGER,

            referrals INTEGER DEFAULT 0,

            last_gift TEXT,

            blocked INTEGER DEFAULT 0,

            created_at TEXT

        );


        CREATE TABLE IF NOT EXISTS channels(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            chat_id INTEGER UNIQUE,

            username TEXT,

            title TEXT,

            active INTEGER DEFAULT 1

        );


        CREATE TABLE IF NOT EXISTS tasks(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            kind TEXT,

            title TEXT,

            target TEXT,

            reward INTEGER,

            active INTEGER DEFAULT 1

        );


        CREATE TABLE IF NOT EXISTS task_done(

            user_id INTEGER,

            task_id INTEGER,

            done_at TEXT,

            PRIMARY KEY(user_id, task_id)

        );


        CREATE TABLE IF NOT EXISTS transactions(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            amount INTEGER,

            kind TEXT,

            note TEXT,

            created_at TEXT

        );


        CREATE TABLE IF NOT EXISTS campaigns(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            owner_id INTEGER,

            chat_id INTEGER,

            target INTEGER,

            completed INTEGER DEFAULT 0,

            cost INTEGER,

            status TEXT DEFAULT 'active',

            created_at TEXT

        );


        CREATE TABLE IF NOT EXISTS settings(

            key TEXT PRIMARY KEY,

            value TEXT

        );

        """)

        defaults = {

            "ref_reward": "20",

            "daily_gift": "10",

            "min_fund": "100",

            "join_reward": "3"

        }

        for key, value in defaults.items():

            await db.execute(
                """
                INSERT OR IGNORE INTO settings(key,value)
                VALUES(?,?)
                """,
                (key, value)
            )

        await db.commit()


# =========================
# الإعدادات
# =========================

async def get_setting(key, default="0"):

    async with await database() as db:

        row = await (
            await db.execute(
                "SELECT value FROM settings WHERE key=?",
                (key,)
            )
        ).fetchone()

        return row[0] if row else default


# =========================
# النقاط
# =========================

async def add_points(
    user_id,
    amount,
    kind,
    note=""
):

    async with await database() as db:

        await db.execute(
            """
            UPDATE users
            SET points = points + ?
            WHERE id=?
            """,
            (amount, user_id)
        )

        await db.execute(
            """
            INSERT INTO transactions
            (
                user_id,
                amount,
                kind,
                note,
                created_at
            )
            VALUES(?,?,?,?,?)
            """,
            (
                user_id,
                amount,
                kind,
                note,
                current_time()
            )
        )

        await db.commit()


async def get_points(user_id):

    async with await database() as db:

        row = await (
            await db.execute(
                "SELECT points FROM users WHERE id=?",
                (user_id,)
            )
        ).fetchone()

        return row[0] if row else 0


# =========================
# تسجيل المستخدم
# =========================

async def ensure_user(user, referral=None):

    async with await database() as db:

        row = await (
            await db.execute(
                "SELECT id FROM users WHERE id=?",
                (user.id,)
            )
        ).fetchone()

        if not row:

            await db.execute(
                """
                INSERT INTO users
                (
                    id,
                    username,
                    first_name,
                    referred_by,
                    created_at
                )
                VALUES(?,?,?,?,?)
                """,
                (
                    user.id,
                    user.username or "",
                    user.first_name or "",
                    referral if referral != user.id else None,
                    current_time()
                )
            )

            if referral and referral != user.id:

                reward = int(
                    await get_setting(
                        "ref_reward",
                        "20"
                    )
                )

                await db.execute(
                    """
                    UPDATE users
                    SET
                        points=points+?,
                        referrals=referrals+1
                    WHERE id=?
                    """,
                    (
                        reward,
                        referral
                    )
                )

                await db.execute(
                    """
                    INSERT INTO transactions
                    (
                        user_id,
                        amount,
                        kind,
                        note,
                        created_at
                    )
                    VALUES(?,?,?,?,?)
                    """,
                    (
                        referral,
                        reward,
                        "referral",
                        str(user.id),
                        current_time()
                    )
                )

        else:

            await db.execute(
                """
                UPDATE users
                SET username=?, first_name=?
                WHERE id=?
                """,
                (
                    user.username or "",
                    user.first_name or "",
                    user.id
                )
            )

        await db.commit()


# =========================
# التحقق من الاشتراك
# =========================

async def is_member(chat_id, user_id):

    try:

        member = await bot.get_chat_member(
            chat_id,
            user_id
        )

        return member.status in {

            ChatMemberStatus.MEMBER,

            ChatMemberStatus.ADMINISTRATOR,

            ChatMemberStatus.CREATOR

        }

    except Exception:

        return False


# =========================
# START
# =========================

@dp.message(CommandStart())
async def start_handler(message: Message):

    referral = None

    parts = message.text.split(
        maxsplit=1
    )

    if len(parts) == 2:

        if parts[1].startswith("ref_"):

            try:

                referral = int(
                    parts[1][4:]
                )

            except Exception:

                referral = None

    await ensure_user(
        message.from_user,
        referral
    )

    points = await get_points(
        message.from_user.id
    )

    await message.answer(

        "<b>🚀 بوت التمويل الاحترافي</b>\n\n"

        f"💰 رصيدك: <b>{points:,}</b> نقطة\n\n"

        "اختر من القائمة:",

        reply_markup=home_keyboard(
            message.from_user.id == ADMIN_ID
        )
    )


# =========================
# الرصيد
# =========================

@dp.message(F.text == "💰 رصيدي")
async def balance_message(message: Message):

    points = await get_points(
        message.from_user.id
    )

    await message.answer(

        f"💰 رصيدك الحالي:\n\n"
        f"<b>{points:,}</b> نقطة",

        reply_markup=back_keyboard()
    )


# =========================
# الدعوات
# =========================

@dp.message(F.text == "👥 دعواتي")
async def referral_message(message: Message):

    async with await database() as db:

        row = await (
            await db.execute(
                """
                SELECT referrals
                FROM users
                WHERE id=?
                """,
                (message.from_user.id,)
            )
        ).fetchone()

    referrals = row[0] if row else 0

    me = await bot.get_me()

    link = (
        f"https://t.me/"
        f"{me.username}"
        f"?start=ref_"
        f"{message.from_user.id}"
    )

    reward = await get_setting(
        "ref_reward",
        "20"
    )

    await message.answer(

        "<b>👥 نظام الدعوات</b>\n\n"

        f"🔗 رابط الدعوة:\n"
        f"<code>{link}</code>\n\n"

        f"🎁 مكافأة الدعوة: "
        f"<b>{reward}</b> نقطة\n\n"

        f"👤 عدد المدعوين: "
        f"<b>{referrals}</b>",

        reply_markup=back_keyboard()
    )


# =========================
# الهدية اليومية
# =========================

@dp.message(F.text == "🎁 الهدية اليومية")
async def daily_gift(message: Message):

    user_id = message.from_user.id

    async with await database() as db:

        row = await (
            await db.execute(
                """
                SELECT last_gift
                FROM users
                WHERE id=?
                """,
                (user_id,)
            )
        ).fetchone()

        if row and row[0]:

            try:

                last = datetime.fromisoformat(
                    row[0]
                )

                if (
                    datetime.now(timezone.utc)
                    - last
                ) < timedelta(hours=24):

                    return await message.answer(
                        "⏳ الهدية اليومية متاحة مرة كل 24 ساعة.",
                        reply_markup=back_keyboard()
                    )

            except Exception:
                pass

        reward = int(
            await get_setting(
                "daily_gift",
                "10"
            )
        )

        await db.execute(
            """
            UPDATE users
            SET points=points+?,
                last_gift=?
            WHERE id=?
            """,
            (
                reward,
                current_time(),
                user_id
            )
        )

        await db.execute(
            """
            INSERT INTO transactions
            (
                user_id,
                amount,
                kind,
                note,
                created_at
            )
            VALUES(?,?,?,?,?)
            """,
            (
                user_id,
                reward,
                "daily_gift",
                "الهدية اليومية",
                current_time()
            )
        )

        await db.commit()

    await message.answer(

        f"🎁 مبروك!\n\n"
        f"تمت إضافة <b>{reward}</b> نقطة.",

        reply_markup=back_keyboard()
    )


# =========================
# كسب النقاط
# =========================

@dp.message(F.text == "🎯 كسب النقاط")
async def earn_points(message: Message):

    async with await database() as db:

        channels = await (
            await db.execute(
                """
                SELECT
                    id,
                    chat_id,
                    username,
                    title
                FROM channels
                WHERE active=1
                ORDER BY id DESC
                """
            )
        ).fetchall()

    if not channels:

        return await message.answer(
            "📭 لا توجد قنوات تمويل حالياً.",
            reply_markup=back_keyboard()
        )

    rows = []

    for channel_id, chat_id, username, title in channels[:30]:

        rows.append([
            (
                f"📢 {title or username or chat_id}",
                f"channel:{channel_id}"
            )
        ])

    rows.append([
        ("⬅️ الرئيسية", "home")
    ])

    await message.answer(

        "🎯 <b>كسب النقاط</b>\n\n"
        "اختر قناة واشترك بها ثم اضغط تحقق.",

        reply_markup=make_keyboard(rows)
    )


# =========================
# فتح القناة
# =========================

@dp.callback_query(F.data.startswith("channel:"))
async def channel_handler(
    callback: CallbackQuery
):

    channel_id = int(
        callback.data.split(":")[1]
    )

    async with await database() as db:

        channel = await (
            await db.execute(
                """
                SELECT
                    chat_id,
                    username,
                    title
                FROM channels
                WHERE id=?
                AND active=1
                """,
                (channel_id,)
            )
        ).fetchone()

    if not channel:

        return await callback.answer(
            "القناة غير موجودة.",
            show_alert=True
        )

    chat_id, username, title = channel

    buttons = []

    if username:

        buttons.append([
            InlineKeyboardButton(
                text="📢 فتح القناة",
                url=(
                    "https://t.me/"
                    + username.lstrip("@")
                )
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="✅ تحقق من الاشتراك",
            callback_data=(
                f"verify:{channel_id}"
            )
        )
    ])

    await callback.message.edit_text(

        f"📢 <b>{title or username}</b>\n\n"
        "اشترك بالقناة ثم اضغط تحقق.",

        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================
# التحقق وإضافة النقاط
# =========================

@dp.callback_query(F.data.startswith("verify:"))
async def verify_subscription(
    callback: CallbackQuery
):

    channel_id = int(
        callback.data.split(":")[1]
    )

    async with await database() as db:

        row = await (
            await db.execute(
                """
                SELECT chat_id
                FROM channels
                WHERE id=?
                AND active=1
                """,
                (channel_id,)
            )
        ).fetchone()

    if not row:

        return await callback.answer(
            "القناة غير موجودة.",
            show_alert=True
        )

    chat_id = row[0]

    if not await is_member(
        chat_id,
        callback.from_user.id
    ):

        return await callback.answer(
            "❌ لم يتم العثور على اشتراكك.",
            show_alert=True
        )

    marker = f"channel:{channel_id}"

    async with await database() as db:

        done = await (
            await db.execute(
                """
                SELECT 1
                FROM transactions
                WHERE user_id=?
                AND kind='channel_join'
                AND note=?
                LIMIT 1
                """,
                (
                    callback.from_user.id,
                    marker
                )
            )
        ).fetchone()

    if done:

        return await callback.answer(
            "✅ حصلت على مكافأة هذه القناة مسبقاً.",
            show_alert=True
        )

    reward = int(
        await get_setting(
            "join_reward",
            "3"
        )
    )

    await add_points(
        callback.from_user.id,
        reward,
        "channel_join",
        marker
    )

    await callback.message.answer(

        f"✅ تم التحقق بنجاح!\n\n"
        f"🎁 +{reward} نقطة"

    )

    await callback.answer(
        "تمت إضافة النقاط ✅"
    )


# =========================
# المهام
# =========================

@dp.message(F.text == "📋 المهام")
async def tasks_message(message: Message):

    async with await database() as db:

        tasks = await (
            await db.execute(
                """
                SELECT
                    id,
                    title,
                    reward
                FROM tasks
                WHERE active=1
                ORDER BY id DESC
                """
            )
        ).fetchall()

    if not tasks:

        return await message.answer(
            "📭 لا توجد مهام حالياً.",
            reply_markup=back_keyboard()
        )

    rows = []

    for task_id, title, reward in tasks:

        rows.append([
            (
                f"🎯 {title} (+{reward})",
                f"task:{task_id}"
            )
        ])

    rows.append([
        ("⬅️ الرئيسية", "home")
    ])

    await message.answer(
        "📋 <b>المهام</b>",
        reply_markup=make_keyboard(rows)
    )


@dp.callback_query(F.data.startswith("task:"))
async def task_handler(
    callback: CallbackQuery
):

    task_id = int(
        callback.data.split(":")[1]
    )

    async with await database() as db:

        task = await (
            await db.execute(
                """
                SELECT
                    title,
                    target,
                    reward,
                    kind
                FROM tasks
                WHERE id=?
                AND active=1
                """,
                (task_id,)
            )
        ).fetchone()

        done = await (
            await db.execute(
                """
                SELECT 1
                FROM task_done
                WHERE user_id=?
                AND task_id=?
                """,
                (
                    callback.from_user.id,
                    task_id
                )
            )
        ).fetchone()

    if not task:

        return await callback.answer(
            "المهمة غير موجودة.",
            show_alert=True
        )

    if done:

        return await callback.answer(
            "سبق احتساب هذه المهمة.",
            show_alert=True
        )

    title, target, reward, kind = task

    if kind in ("channel", "group") and target:

        chat = (
            int(target)
            if str(target).lstrip("-").isdigit()
            else target
        )

        if not await is_member(
            chat,
            callback.from_user.id
        ):

            return await callback.answer(
                "❌ نفّذ المهمة أولاً.",
                show_alert=True
            )

    async with await database() as db:

        await db.execute(
            """
            INSERT INTO task_done
            VALUES(?,?,?)
            """,
            (
                callback.from_user.id,
                task_id,
                current_time()
            )
        )

        await db.commit()

    await add_points(
        callback.from_user.id,
        reward,
        "task",
        str(task_id)
    )

    await callback.message.answer(

        f"🎉 تمت المهمة:\n"
        f"<b>{title}</b>\n\n"
        f"💰 +{reward} نقطة"

    )

    await callback.answer(
        "تمت إضافة النقاط."
    )


# =========================
# تمويل القناة
# =========================

@dp.message(F.text == "📢 تمويل قناتي")
async def funding(message: Message):

    minimum = await get_setting(
        "min_fund",
        "100"
    )

    cost = await get_setting(
        "join_reward",
        "3"
    )

    await message.answer(

        "<b>📢 تمويل قناتك</b>\n\n"

        f"👥 الحد الأدنى: "
        f"<b>{minimum}</b> عضو\n\n"

        f"💰 السعر الافتراضي: "
        f"<b>{cost}</b> نقطة لكل عضو\n\n"

        "لإنشاء حملة من الإدارة:\n"
        "<code>/campaign @channel 500 3</code>",

        reply_markup=back_keyboard()
    )


# =========================
# الحملات
# =========================

@dp.message(F.text == "📊 حملاتي")
async def campaigns_message(
    message: Message
):

    async with await database() as db:

        campaigns = await (
            await db.execute(
                """
                SELECT
                    id,
                    target,
                    completed,
                    cost,
                    status
                FROM campaigns
                WHERE owner_id=?
                ORDER BY id DESC
                """,
                (message.from_user.id,)
            )
        ).fetchall()

    if not campaigns:

        return await message.answer(
            "📭 لا توجد حملات.",
            reply_markup=back_keyboard()
        )

    text = ["📊 <b>حملاتك</b>\n"]

    for campaign in campaigns:

        campaign_id, target, completed, cost, status = campaign

        text.append(

            f"#{campaign_id} — "
            f"{completed}/{target} عضو — "
            f"{cost} نقطة/عضو — "
            f"{status}"

        )

    await message.answer(
        "\n".join(text),
        reply_markup=back_keyboard()
    )


# =========================
# السجل
# =========================

@dp.message(F.text == "🧾 السجل")
async def history(message: Message):

    async with await database() as db:

        rows = await (
            await db.execute(
                """
                SELECT
                    amount,
                    kind,
                    note
                FROM transactions
                WHERE user_id=?
                ORDER BY id DESC
                LIMIT 20
                """,
                (message.from_user.id,)
            )
        ).fetchall()

    if not rows:

        text = "لا يوجد سجل حتى الآن."

    else:

        text = "\n".join(

            f"{'+' if amount >= 0 else ''}"
            f"{amount} نقطة | "
            f"{kind} | "
            f"{note or ''}"

            for amount, kind, note in rows

        )

    await message.answer(
        "🧾 <b>آخر العمليات</b>\n\n"
        + text,
        reply_markup=back_keyboard()
    )


# =========================
# المساعدة
# =========================

@dp.message(F.text == "ℹ️ المساعدة")
async def help_message(message: Message):

    await message.answer(

        "<b>ℹ️ المساعدة</b>\n\n"

        "🎯 اكسب النقاط من القنوات والمهام.\n"
        "👥 ادعُ أصدقاءك.\n"
        "🎁 خذ الهدية اليومية.\n"
        "📢 استخدم نقاطك للتمويل.\n\n"

        "⚠️ يجب أن يكون البوت مشرفاً "
        "في القنوات التي يتحقق من عضويتها.",

        reply_markup=back_keyboard()
    )


# =========================
# إضافة قناة - أدمن
# =========================

@dp.message(Command("addchannel"))
async def add_channel(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split(
        maxsplit=1
    )

    if len(parts) != 2:

        return await message.answer(
            "/addchannel @channel"
        )

    username = parts[1].strip()

    try:

        chat = await bot.get_chat(
            username
        )

        async with await database() as db:

            await db.execute(
                """
                INSERT OR REPLACE INTO channels
                (
                    chat_id,
                    username,
                    title,
                    active
                )
                VALUES(?,?,?,1)
                """,
                (
                    chat.id,
                    username,
                    chat.title or ""
                )
            )

            await db.commit()

        await message.answer(
            "✅ تمت إضافة القناة."
        )

    except Exception:

        await message.answer(
            "❌ تعذر الوصول للقناة.\n"
            "تأكد أن البوت مشرف في القناة."
        )


# =========================
# إضافة مهمة - أدمن
# =========================

@dp.message(Command("task"))
async def create_task(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split(
        "|",
        3
    )

    if len(parts) != 4:

        return await message.answer(
            "/task channel|@channel|50|عنوان المهمة"
        )

    kind, target, reward, title = parts

    async with await database() as db:

        await db.execute(
            """
            INSERT INTO tasks
            (
                kind,
                title,
                target,
                reward
            )
            VALUES(?,?,?,?)
            """,
            (
                kind,
                title,
                target,
                int(reward)
            )
        )

        await db.commit()

    await message.answer(
        "✅ تمت إضافة المهمة."
    )


# =========================
# إنشاء حملة - أدمن
# =========================

@dp.message(Command("campaign"))
async def create_campaign(message: Message):

    if message.from_user.id != ADMIN_ID:

        return await message.answer(
            "⚠️ هذا الأمر للإدارة حالياً."
        )

    parts = message.text.split()

    if len(parts) != 4:

        return await message.answer(
            "/campaign @channel target cost"
        )

    username = parts[1]
    target = int(parts[2])
    cost = int(parts[3])

    async with await database() as db:

        channel = await (
            await db.execute(
                """
                SELECT chat_id
                FROM channels
                WHERE username=?
                AND active=1
                """,
                (username,)
            )
        ).fetchone()

        if not channel:

            return await message.answer(
                "❌ القناة غير مضافة."
            )

        await db.execute(
            """
            INSERT INTO campaigns
            (
                owner_id,
                chat_id,
                target,
                cost,
                created_at
            )
            VALUES(?,?,?,?,?)
            """,
            (
                message.from_user.id,
                channel[0],
                target,
                cost,
                current_time()
            )
        )

        await db.commit()

    await message.answer(
        "✅ تم إنشاء الحملة."
    )


# =========================
# إضافة نقاط - أدمن
# =========================

@dp.message(Command("addpoints"))
async def add_points_admin(
    message: Message
):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 3:

        return await message.answer(
            "/addpoints USER_ID AMOUNT"
        )

    user_id = int(parts[1])
    amount = int(parts[2])

    await add_points(
        user_id,
        amount,
        "admin_add",
        "إضافة من الإدارة"
    )

    await message.answer(
        "✅ تمت إضافة النقاط."
    )


# =========================
# حذف نقاط - أدمن
# =========================

@dp.message(Command("delpoints"))
async def delete_points_admin(
    message: Message
):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 3:

        return await message.answer(
            "/delpoints USER_ID AMOUNT"
        )

    user_id = int(parts[1])
    amount = abs(int(parts[2]))

    await add_points(
        user_id,
        -amount,
        "admin_delete",
        "خصم من الإدارة"
    )

    await message.answer(
        "✅ تم خصم النقاط."
    )


# =========================
# لوحة الإدارة
# =========================

@dp.message(Command("admin"))
async def admin_command(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(

        "<b>🛠 لوحة الإدارة</b>\n\n"
        "اختر العملية:",

        reply_markup=make_keyboard([
            [
                ("📈 الإحصائيات", "admin_stats")
            ],
            [
                ("⬅️ الرئيسية", "home")
            ]
        ])
    )


# =========================
# الرئيسية
# =========================

@dp.callback_query(F.data == "home")
async def home_callback(
    callback: CallbackQuery
):

    points = await get_points(
        callback.from_user.id
    )

    await callback.message.edit_text(

        "<b>🚀 بوت التمويل الاحترافي</b>\n\n"
        f"💰 رصيدك: <b>{points:,}</b> نقطة\n\n"
        "اختر من القائمة:",

        reply_markup=home_keyboard(
            callback.from_user.id == ADMIN_ID
        )
    )

    await callback.answer()


# =========================
# لوحة الأدمن
# =========================

@dp.callback_query(F.data == "admin")
async def admin_callback(
    callback: CallbackQuery
):

    if callback.from_user.id != ADMIN_ID:
        return await callback.answer(
            "⛔ غير مسموح.",
            show_alert=True
        )

    await callback.message.edit_text(

        "<b>🛠 لوحة الإدارة</b>",

        reply_markup=make_keyboard([
            [
                ("📈 الإحصائيات", "admin_stats")
            ],
            [
                ("⬅️ الرئيسية", "home")
            ]
        ])
    )

    await callback.answer()


# =========================
# إحصائيات الأدمن
# =========================

@dp.callback_query(F.data == "admin_stats")
async def admin_statistics(
    callback: CallbackQuery
):

    if callback.from_user.id != ADMIN_ID:
        return

    async with await database() as db:

        users = (
            await (
                await db.execute(
                    "SELECT COUNT(*) FROM users"
                )
            ).fetchone()
        )[0]

        points = (
            await (
                await db.execute(
                    "SELECT COALESCE(SUM(points),0) FROM users"
                )
            ).fetchone()
        )[0]

        channels = (
            await (
                await db.execute(
                    "SELECT COUNT(*) FROM channels WHERE active=1"
                )
            ).fetchone()
        )[0]

    await callback.message.edit_text(

        "<b>📈 الإحصائيات</b>\n\n"

        f"👤 المستخدمون: <b>{users:,}</b>\n"
        f"💰 مجموع النقاط: <b>{points:,}</b>\n"
        f"📢 القنوات: <b>{channels:,}</b>",

        reply_markup=make_keyboard([
            [
                ("⬅️ لوحة الإدارة", "admin")
            ]
        ])
    )

    await callback.answer()


# =========================
# Webhook
# =========================

async def webhook_handler(request):

    received_secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token",
        ""
    )

    if not secrets.compare_digest(
        received_secret,
        WEBHOOK_SECRET
    ):

        return web.Response(
            status=403
        )

    data = await request.json()

    update = Update.model_validate(
        data
    )

    await dp.feed_update(
        bot,
        update
    )

    return web.Response(
        text="ok"
    )


async def health(request):

    return web.Response(
        text="Funding Bot is running"
    )


async def startup(app):

    await initialize_database()

    webhook_url = (
        f"{BASE_URL}"
        f"{WEBHOOK_PATH}"
    )

    await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True
    )

    logging.info(
        "Webhook set: %s",
        webhook_url
    )


async def cleanup(app):

    try:

        await bot.delete_webhook()

    except Exception:

        pass

    await bot.session.close()


# =========================
# تشغيل السيرفر
# =========================

app = web.Application()

app.router.add_get(
    "/",
    health
)

app.router.add_post(
    WEBHOOK_PATH,
    webhook_handler
)

app.on_startup.append(
    startup
)

app.on_cleanup.append(
    cleanup
)


if __name__ == "__main__":

    web.run_app(
        app,
        host="0.0.0.0",
        port=PORT
            )
