require("dotenv").config();

const express = require("express");
const session = require("express-session");
const { Telegraf, Markup } = require("telegraf");
const { Pool } = require("pg");
const multer = require("multer");
const cron = require("node-cron");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const app = express();

const PORT = process.env.PORT || 10000;
const BASE_URL = (process.env.BASE_URL || "1792685788").replace(/\/$/, "");
const BOT_TOKEN = process.env.BOT_TOKEN || "6697835631:AAE-isBrECs3BY3zUgKfifqoPM6nu6NBe6s";

const ADMIN_USERNAME = process.env.ADMIN_USERNAME || "1792685788";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "change-me";

const OPENAI_API_KEY = process.env.OPENAI_API_KEY || "";
const OPENAI_MODEL = process.env.OPENAI_MODEL || "gpt-5-mini";

const ADMIN_IDS = (process.env.ADMIN_IDS || "")
  .split(",")
  .map(x => x.trim())
  .filter(Boolean);

const TRIAL_DAYS = Number(process.env.TRIAL_DAYS || 30);
const TZ = process.env.TZ || "Asia/Baghdad";

process.env.TZ = TZ;


// ===============================
// DATABASE
// ===============================

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,

  ssl:
    process.env.DATABASE_URL &&
    !process.env.DATABASE_URL.includes("localhost")
      ? { rejectUnauthorized: false }
      : false
});


async function q(sql, params = []) {
  const result = await pool.query(sql, params);
  return result.rows;
}


async function one(sql, params = []) {
  const result = await pool.query(sql, params);
  return result.rows[0] || null;
}


// ===============================
// FILE UPLOAD
// ===============================

const uploadDir = path.join(__dirname, "uploads");

fs.mkdirSync(uploadDir, {
  recursive: true
});


const upload = multer({
  dest: uploadDir,

  limits: {
    fileSize: 250 * 1024 * 1024
  }
});


// ===============================
// EXPRESS
// ===============================

app.use(
  express.json({
    limit: "10mb"
  })
);

app.use(
  express.urlencoded({
    extended: true,
    limit: "10mb"
  })
);


// ===============================
// SESSION
// ===============================

app.use(
  session({
    secret:
      process.env.SESSION_SECRET ||
      "change-this-session-secret",

    resave: false,

    saveUninitialized: false,

    cookie: {
      httpOnly: true,
      sameSite: "lax",

      secure:
        process.env.NODE_ENV === "production",

      maxAge: 7 * 86400000
    }
  })
);


// ===============================
// HELPERS
// ===============================

function esc(value = "") {
  return String(value).replace(
    /[&<>"']/g,
    c =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[c])
  );
}


function fmtDate(date) {
  if (!date) {
    return "غير محدد";
  }

  return new Date(date).toLocaleString(
    "ar-IQ",
    {
      timeZone: TZ
    }
  );
}


function isActive(user) {
  return (
    user &&
    user.subscription_expires_at &&
    new Date(
      user.subscription_expires_at
    ).getTime() > Date.now()
  );
}


// ===============================
// SECURITY TOKEN
// ===============================

function createToken(
  data,
  secret =
    process.env.SESSION_SECRET ||
    "secret"
) {
  const body = Buffer
    .from(JSON.stringify(data))
    .toString("base64url");

  const signature = crypto
    .createHmac(
      "sha256",
      secret
    )
    .update(body)
    .digest("base64url");

  return body + "." + signature;
}


function verifyToken(
  token,
  secret =
    process.env.SESSION_SECRET ||
    "secret"
) {
  try {
    const parts = String(token || "").split(".");

    if (parts.length !== 2) {
      return null;
    }

    const body = parts[0];
    const signature = parts[1];

    const expected = crypto
      .createHmac(
        "sha256",
        secret
      )
      .update(body)
      .digest("base64url");

    if (
      !crypto.timingSafeEqual(
        Buffer.from(signature),
        Buffer.from(expected)
      )
    ) {
      return null;
    }

    const data = JSON.parse(
      Buffer
        .from(body, "base64url")
        .toString()
    );

    if (
      data.exp &&
      Date.now() > data.exp
    ) {
      return null;
    }

    return data;

  } catch {
    return null;
  }
}


// ===============================
// DATABASE INITIALIZATION
// ===============================

async function initDB() {

  await q(`

    CREATE TABLE IF NOT EXISTS users (

      id BIGSERIAL PRIMARY KEY,

      telegram_id BIGINT UNIQUE NOT NULL,

      username TEXT,

      first_name TEXT,

      last_name TEXT,

      subscription_expires_at TIMESTAMPTZ,

      trial_claimed BOOLEAN DEFAULT FALSE,

      is_blocked BOOLEAN DEFAULT FALSE,

      created_at TIMESTAMPTZ DEFAULT NOW()

    );


    CREATE TABLE IF NOT EXISTS subscription_codes (

      id BIGSERIAL PRIMARY KEY,

      code TEXT UNIQUE NOT NULL,

      plan TEXT NOT NULL,

      days INT NOT NULL,

      used_by BIGINT REFERENCES users(id),

      used_at TIMESTAMPTZ,

      created_at TIMESTAMPTZ DEFAULT NOW()

    );


    CREATE TABLE IF NOT EXISTS lectures (

      id BIGSERIAL PRIMARY KEY,

      title TEXT NOT NULL,

      description TEXT,

      subject TEXT,

      grade TEXT,

      media_type TEXT DEFAULT 'video',

      file_url TEXT,

      original_name TEXT,

      is_active BOOLEAN DEFAULT TRUE,

      created_at TIMESTAMPTZ DEFAULT NOW()

    );


    CREATE TABLE IF NOT EXISTS materials (

      id BIGSERIAL PRIMARY KEY,

      title TEXT NOT NULL,

      description TEXT,

      subject TEXT,

      grade TEXT,

      file_url TEXT,

      original_name TEXT,

      created_at TIMESTAMPTZ DEFAULT NOW()

    );


    CREATE TABLE IF NOT EXISTS exams (

      id BIGSERIAL PRIMARY KEY,

      title TEXT NOT NULL,

      description TEXT,

      duration_minutes INT DEFAULT 30,

      is_active BOOLEAN DEFAULT TRUE,

      created_at TIMESTAMPTZ DEFAULT NOW()

    );


    CREATE TABLE IF NOT EXISTS questions (

      id BIGSERIAL PRIMARY KEY,

      exam_id BIGINT
        REFERENCES exams(id)
        ON DELETE CASCADE,

      question_text TEXT NOT NULL,

      image_url TEXT,

      type TEXT DEFAULT 'mcq',

      options JSONB DEFAULT '[]',

      correct_answer TEXT,

      points INT DEFAULT 1

    );


    CREATE TABLE IF NOT EXISTS exam_attempts (

      id BIGSERIAL PRIMARY KEY,

      exam_id BIGINT
        REFERENCES exams(id)
        ON DELETE CASCADE,

      user_id BIGINT
        REFERENCES users(id)
        ON DELETE CASCADE,

      started_at TIMESTAMPTZ DEFAULT NOW(),

      expires_at TIMESTAMPTZ NOT NULL,

      submitted_at TIMESTAMPTZ,

      score NUMERIC DEFAULT 0,

      max_score NUMERIC DEFAULT 0,

      percentage NUMERIC DEFAULT 0,

      answers JSONB DEFAULT '{}',

      ai_feedback TEXT

    );


    CREATE TABLE IF NOT EXISTS attendance (

      id BIGSERIAL PRIMARY KEY,

      user_id BIGINT
        REFERENCES users(id)
        ON DELETE CASCADE,

      day DATE NOT NULL,

      created_at TIMESTAMPTZ DEFAULT NOW(),

      UNIQUE(user_id, day)

    );


    CREATE TABLE IF NOT EXISTS lecture_views (

      id BIGSERIAL PRIMARY KEY,

      user_id BIGINT
        REFERENCES users(id)
        ON DELETE CASCADE,

      lecture_id BIGINT
        REFERENCES lectures(id)
        ON DELETE CASCADE,

      viewed_at TIMESTAMPTZ DEFAULT NOW()

    );


    CREATE TABLE IF NOT EXISTS challenges (

      id BIGSERIAL PRIMARY KEY,

      title TEXT NOT NULL,

      description TEXT,

      reward TEXT,

      start_at TIMESTAMPTZ,

      end_at TIMESTAMPTZ,

      is_active BOOLEAN DEFAULT TRUE,

      created_at TIMESTAMPTZ DEFAULT NOW()

    );


    CREATE TABLE IF NOT EXISTS weekly_winners (

      id BIGSERIAL PRIMARY KEY,

      period_start TIMESTAMPTZ,

      period_end TIMESTAMPTZ,

      user_id BIGINT
        REFERENCES users(id),

      views_count INT DEFAULT 0,

      created_at TIMESTAMPTZ DEFAULT NOW()

    );


    CREATE TABLE IF NOT EXISTS settings (

      key TEXT PRIMARY KEY,

      value TEXT

    );

  `);


  const defaults = {

    site_name:
      "منصة العراق التعليمية",

    primary_color:
      "#2563eb",

    secondary_color:
      "#7c3aed",

    welcome:
      "أهلاً بك في منصة العراق التعليمية"

  };


  for (
    const [key, value]
    of Object.entries(defaults)
  ) {

    await q(
      `
      INSERT INTO settings(key,value)

      VALUES($1,$2)

      ON CONFLICT(key)
      DO NOTHING
      `,
      [key, value]
    );

  }

}


// ===============================
// SETTINGS
// ===============================

async function getSettings() {

  const rows = await q(
    "SELECT key,value FROM settings"
  );

  return Object.fromEntries(
    rows.map(row => [
      row.key,
      row.value
    ])
  );
}


async function setting(
  key,
  fallback = ""
) {

  const row = await one(
    "SELECT value FROM settings WHERE key=$1",
    [key]
  );

  return row?.value ?? fallback;
}


// ===============================
// TELEGRAM USER
// ===============================

async function getOrCreateUser(ctx) {

  const from = ctx.from;

  let user = await one(
    `
    SELECT *
    FROM users
    WHERE telegram_id=$1
    `,
    [from.id]
  );


  if (!user) {

    const expires =
      new Date(
        Date.now() +
        TRIAL_DAYS *
        86400000
      );


    user = await one(
      `
      INSERT INTO users(

        telegram_id,

        username,

        first_name,

        last_name,

        subscription_expires_at,

        trial_claimed

      )

      VALUES(

        $1,$2,$3,$4,$5,true

      )

      RETURNING *
      `,
      [
        from.id,

        from.username || "",

        from.first_name || "",

        from.last_name || "",

        expires
      ]
    );


    try {

      await ctx.reply(
        `🎁 تم تفعيل هدية التسجيل المجانية لمدة ${TRIAL_DAYS} يوم.\n\n` +
        `ينتهي اشتراكك:\n${fmtDate(expires)}`
      );

    } catch {}

  } else {

    await q(
      `
      UPDATE users

      SET

        username=$1,

        first_name=$2,

        last_name=$3

      WHERE id=$4
      `,
      [
        from.username || "",

        from.first_name || "",

        from.last_name || "",

        user.id
      ]
    );

  }


  return await one(
    "SELECT * FROM users WHERE id=$1",
    [user.id]
  );

}


// ===============================
// MAIN TELEGRAM MENU
// ===============================

function mainKeyboard() {

  return Markup.inlineKeyboard([

    [

      Markup.button.callback(
        "📚 المحاضرات",
        "lectures"
      ),

      Markup.button.callback(
        "📖 الملازم",
        "materials"
      )

    ],

    [

      Markup.button.callback(
        "📝 الامتحانات",
        "exams"
      ),

      Markup.button.callback(
        "🏆 التحديات",
        "challenges"
      )

    ],

    [

      Markup.button.callback(
        "🟢 الحضور اليومي",
        "attendance"
      ),

      Markup.button.callback(
        "💳 الاشتراك",
        "subscription"
      )

    ],

    [

      Markup.button.callback(
        "👤 حسابي",
        "account"
      ),

      Markup.button.callback(
        "📞 الدعم",
        "support"
      )

    ]

  ]);

}


// ===============================
// LECTURE LINK
// ===============================

async function lectureLink(
  userId,
  lectureId
) {

  if (!BASE_URL) {
    return null;
  }


  const t = createToken({

    uid: userId,

    lid: lectureId,

    exp:
      Date.now() +
      86400000

  });


  return (
    `${BASE_URL}/view/lecture/` +
    `${lectureId}?token=` +
    encodeURIComponent(t)
  );

}


// ===============================
// EXAM LINK
// ===============================

async function examLink(
  userId,
  examId
) {

  if (!BASE_URL) {
    return null;
  }


  const t = createToken({

    uid: userId,

    eid: examId,

    exp:
      Date.now() +
      86400000

  });


  return (
    `${BASE_URL}/app/exam/` +
    `${examId}?token=` +
    encodeURIComponent(t)
  );

}


// ===============================
// TELEGRAM BOT
// ===============================

let bot = null;


if (BOT_TOKEN) {

  bot = new Telegraf(
    BOT_TOKEN
  );


  bot.start(
    async ctx => {

      const user =
        await getOrCreateUser(ctx);


      if (user.is_blocked) {

        return ctx.reply(
          "🚫 حسابك محظور."
        );

      }


      const settings =
        await getSettings();


      await ctx.reply(

        `${settings.welcome}\n\n` +
        `اختر من القائمة:`,
        
        mainKeyboard()

      );

    }
  );


  bot.command(
    "admin",
    async ctx => {

      if (
        !ADMIN_IDS.includes(
          String(ctx.from.id)
        )
      ) {

        return ctx.reply(
          "❌ غير مصرح."
        );

      }


      if (!BASE_URL) {

        return ctx.reply(
          "ضع BASE_URL أولاً."
        );

      }


      ctx.reply(
        `🔐 لوحة الإدارة:\n\n${BASE_URL}/admin`
      );

    }
  );


  bot.on(
    "callback_query",
    async ctx => {

      const user =
        await getOrCreateUser(ctx);


      if (user.is_blocked) {

        return ctx.answerCbQuery(
          "الحساب محظور"
        );

      }


      const action =
        ctx.callbackQuery.data;


      await ctx.answerCbQuery()
        .catch(() => {});


      // القائمة الرئيسية

      if (action === "menu") {

        return ctx
          .editMessageText(
            "📋 القائمة الرئيسية:",
            mainKeyboard()
          )
          .catch(() =>
            ctx.reply(
              "📋 القائمة الرئيسية:",
              mainKeyboard()
            )
          );

      }


      // الحضور

      if (
        action === "attendance"
      ) {

        const inserted =
          await one(
            `
            INSERT INTO attendance(
              user_id,
              day
            )

            VALUES(
              $1,
              CURRENT_DATE
            )

            ON CONFLICT(
              user_id,
              day
            )

            DO NOTHING

            RETURNING id
            `,
            [user.id]
          );


        const count =
          await one(
            `
            SELECT COUNT(*)::int AS n

            FROM attendance

            WHERE user_id=$1
            `,
            [user.id]
          );


        if (inserted) {

          return ctx.reply(
            `✅ تم تسجيل حضورك اليوم.\n\n` +
            `🔥 مجموع أيام حضورك: ${count.n}`
          );

        }


        return ctx.reply(
          `ℹ️ أنت مسجل حضور اليوم مسبقاً.\n\n` +
          `🔥 مجموع أيام حضورك: ${count.n}`
        );

      }


      // الحساب

      if (action === "account") {

        return ctx.reply(

          `👤 حسابي\n\n` +

          `الاسم: ${
            user.first_name || ""
          }\n` +

          `المعرف: @` +
          `${user.username || "بدون"}\n\n` +

          `الاشتراك: ` +
          `${
            isActive(user)
              ? "فعال ✅"
              : "منتهي ❌"
          }\n` +

          `ينتهي: ` +
          `${fmtDate(
            user.subscription_expires_at
          )}`

        );

      }


      // الاشتراك

      if (
        action === "subscription"
      ) {

        return ctx.reply(

          `💳 نظام الاشتراك\n\n` +

          `📅 الشهري: 30 يوم\n` +

          `📅 السنوي: 365 يوم\n\n` +

          `حالة اشتراكك: ` +
          `${
            isActive(user)
              ? "فعال ✅"
              : "منتهي ❌"
          }\n\n` +

          `ينتهي بتاريخ:\n` +
          `${fmtDate(
            user.subscription_expires_at
          )}\n\n` +

          `أرسل كود الاشتراك هنا لتفعيله.`

        );

      }


      // الدعم

      if (
        action === "support"
      ) {

        return ctx.reply(
          "📞 للدعم والاستفسارات تواصل مع الإدارة."
        );

      }


      // المحاضرات

      if (
        action === "lectures"
      ) {

        if (!isActive(user)) {

          return ctx.reply(
            "🔒 تحتاج إلى اشتراك فعال لمشاهدة المحاضرات."
          );

        }


        const lectures =
          await q(
            `
            SELECT *

            FROM lectures

            WHERE is_active=true

            ORDER BY id DESC

            LIMIT 50
            `
          );


        if (!lectures.length) {

          return ctx.reply(
            "📚 لا توجد محاضرات حالياً."
          );

        }


        const buttons =
          lectures.map(
            lecture => [

              Markup.button.callback(

                `🎥 ${lecture.title}`,

                `lecture:${lecture.id}`

              )

            ]
          );


        buttons.push([

          Markup.button.callback(
            "⬅️ رجوع",
            "menu"
          )

        ]);


        return ctx.reply(

          "📚 اختر المحاضرة:",

          Markup.inlineKeyboard(
            buttons
          )

        );

      }


      // فتح المحاضرة

      if (
        action.startsWith(
          "lecture:"
        )
      ) {

        if (!isActive(user)) {

          return ctx.reply(
            "🔒 الاشتراك غير فعال."
          );

        }


        const lectureId =
          Number(
            action.split(":")[1]
          );


        const lecture =
          await one(
            `
            SELECT *

            FROM lectures

            WHERE id=$1

            AND is_active=true
            `,
            [lectureId]
          );


        if (!lecture) {

          return ctx.reply(
            "❌ المحاضرة غير موجودة."
          );

        }


        await q(
          `
          INSERT INTO lecture_views(
            user_id,
            lecture_id
          )

          VALUES(
            $1,
            $2
          )
          `,
          [
            user.id,
            lectureId
          ]
        );


        const link =
          await lectureLink(
            user.id,
            lectureId
          );


        if (link) {

          return ctx.reply(

            `🎥 ${lecture.title}\n\n` +
            `${lecture.description || ""}`,

            Markup.inlineKeyboard([

              [

                Markup.button.url(
                  "▶️ مشاهدة المحاضرة",
                  link
                )

              ],

              [

                Markup.button.callback(
                  "⬅️ المحاضرات",
                  "lectures"
                )

              ]

            ])

          );

        }


        return ctx.reply(
          `🎥 ${lecture.title}\n\n` +
          `${lecture.file_url || "الرابط غير متوفر"}`
        );

      }


      // الملازم

      if (
        action === "materials"
      ) {

        if (!isActive(user)) {

          return ctx.reply(
            "🔒 تحتاج إلى اشتراك فعال."
          );

        }


        const materials =
          await q(
            `
            SELECT *

            FROM materials

            ORDER BY id DESC

            LIMIT 50
            `
          );


        if (!materials.length) {

          return ctx.reply(
            "📖 لا توجد ملازم حالياً."
          );

        }


        const text =
          materials
            .map(
              (m, i) =>
                `${i + 1}. ${m.title}\n` +
                `${m.file_url || ""}`
            )
            .join("\n\n");


        return ctx.reply(
          `📖 الملازم:\n\n${text}`
        );

      }


      // الامتحانات

      if (
        action === "exams"
      ) {

        if (!isActive(user)) {

          return ctx.reply(
            "🔒 تحتاج إلى اشتراك فعال."
          );

        }


        const exams =
          await q(
            `
            SELECT *

            FROM exams

            WHERE is_active=true

            ORDER BY id DESC
            `
          );


        if (!exams.length) {

          return ctx.reply(
            "📝 لا توجد امتحانات حالياً."
          );

        }


        const buttons =
          exams.map(
            exam => [

              Markup.button.callback(

                `📝 ${exam.title} ` +
                `(${exam.duration_minutes} دقيقة)`,

                `exam:${exam.id}`

              )

            ]
          );


        buttons.push([

          Markup.button.callback(
            "⬅️ رجوع",
            "menu"
          )

        ]);


        return ctx.reply(

          "📝 اختر الامتحان:",

          Markup.inlineKeyboard(
            buttons
          )

        );

      }


      // فتح الامتحان

      if (
        action.startsWith(
          "exam:"
        )
      ) {

        if (!isActive(user)) {

          return ctx.reply(
            "🔒 الاشتراك غير فعال."
          );

        }


        const examId =
          Number(
            action.split(":")[1]
          );


        const exam =
          await one(
            `
            SELECT *

            FROM exams

            WHERE id=$1

            AND is_active=true
            `,
            [examId]
          );


        if (!exam) {

          return ctx.reply(
            "❌ الامتحان غير موجود."
          );

        }


        const link =
          await examLink(
            user.id,
            examId
          );


        if (!link) {

          return ctx.reply(
            "ضع BASE_URL حتى يعمل الامتحان."
          );

        }


        return ctx.reply(

          `📝 ${exam.title}\n\n` +

          `${exam.description || ""}\n\n` +

          `⏱ الوقت: ` +
          `${exam.duration_minutes} دقيقة`,

          Markup.inlineKeyboard([

            [

              Markup.button.url(
                "🚀 بدء الامتحان",
                link
              )

            ]

          ])

        );

      }


      // التحديات

      if (
        action === "challenges"
      ) {

        const challenges =
          await q(
            `
            SELECT *

            FROM challenges

            WHERE is_active=true

            AND (
              start_at IS NULL
              OR start_at <= NOW()
            )

            AND (
              end_at IS NULL
              OR end_at >= NOW()
            )

            ORDER BY id DESC
            `
          );


        if (!challenges.length) {

          return ctx.reply(
            "🏆 لا توجد تحديات فعالة حالياً."
          );

        }


        const text =
          challenges
            .map(
              c =>
                `🏆 ${c.title}\n` +
                `${c.description || ""}\n` +
                `🎁 الجائزة: ${
                  c.reward || "غير محددة"
                }`
            )
            .join("\n\n");


        return ctx.reply(
          text
        );

      }

    }
  );


  // ===============================
  // REDEEM SUBSCRIPTION CODE
  // ===============================

  bot.on(
    "text",
    async ctx => {

      const user =
        await getOrCreateUser(ctx);


      const text =
        (
          ctx.message.text ||
          ""
        ).trim();


      if (
        !text ||
        text.startsWith("/")
      ) {
        return;
      }


      if (
        text
          .toUpperCase()
          .startsWith("EDU-")
      ) {

        const code =
          text.toUpperCase();


        const subscription =
          await one(
            `
            SELECT *

            FROM subscription_codes

            WHERE code=$1

            AND used_by IS NULL
            `,
            [code]
          );


        if (!subscription) {

          return ctx.reply(
            "❌ الكود غير صحيح أو مستخدم."
          );

        }


        await q(
          `
          UPDATE subscription_codes

          SET

            used_by=$1,

            used_at=NOW()

          WHERE id=$2
          `,
          [
            user.id,
            subscription.id
          ]
        );


        const current =
          isActive(user)
            ? new Date(
                user.subscription_expires_at
              )
            : new Date();


        const expiry =
          new Date(
            Math.max(
              current.getTime(),
              Date.now()
            ) +
            subscription.days *
            86400000
          );


        await q(
          `
          UPDATE users

          SET subscription_expires_at=$1

          WHERE id=$2
          `,
          [
            expiry,
            user.id
          ]
        );


        return ctx.reply(

          `✅ تم تفعيل الاشتراك بنجاح.\n\n` +

          `الخطة: ${subscription.plan}\n` +

          `المدة: ${subscription.days} يوم\n\n` +

          `تاريخ الانتهاء:\n` +

          `${fmtDate(expiry)}`

        );

      }


      await ctx.reply(
        "اختر من القائمة:",
        mainKeyboard()
      );

    }
  );

}


// ===============================
// ADMIN AUTH
// ===============================

function requireAdmin(
  req,
  res,
  next
) {

  if (req.session.admin) {
    return next();
  }


  return res
    .status(401)
    .json({
      error: "غير مصرح"
    });

}


// ===============================
// HOME
// ===============================

app.get(
  "/",
  async (req, res) => {

    const settings =
      await getSettings();


    res.send(`

<!doctype html>

<html lang="ar" dir="rtl">

<head>

<meta charset="utf-8">

<meta
  name="viewport"
  content="width=device-width,initial-scale=1"
>

<title>
${esc(settings.site_name)}
</title>

<style>

body{

  font-family:Arial;

  background:#f5f7fb;

  margin:0;

  color:#111827;

}

.box{

  max-width:700px;

  margin:70px auto;

  background:white;

  padding:35px;

  border-radius:22px;

  box-shadow:
    0 10px 35px #0001;

  text-align:center;

}

a,button{

  background:
    ${esc(settings.primary_color)};

  color:white;

  border:0;

  padding:13px 20px;

  border-radius:12px;

  text-decoration:none;

  display:inline-block;

}

</style>

</head>

<body>

<div class="box">

<h1>
🎓 ${esc(settings.site_name)}
</h1>

<p>
${esc(settings.welcome)}
</p>

<a href="/admin">
🔐 لوحة الإدارة
</a>

</div>

</body>

</html>

`);

  }
);


// ===============================
// ADMIN LOGIN
// ===============================

app.get(
  "/admin",
  (req, res) => {

    if (
      !req.session.admin
    ) {

      return res.send(
        loginHTML()
      );

    }


    res.send(
      adminHTML()
    );

  }
);


app.post(
  "/admin/login",
  (req, res) => {

    const {
      username,
      password
    } = req.body;


    if (
      username ===
        ADMIN_USERNAME &&

      password ===
        ADMIN_PASSWORD
    ) {

      req.session.admin = true;

      return res.redirect(
        "/admin"
      );

    }


    res
      .status(401)
      .send(
        loginHTML(
          "بيانات الدخول غير صحيحة"
        )
      );

  }
);


app.post(
  "/admin/logout",
  (req, res) => {

    req.session.destroy(
      () => res.redirect("/admin")
    );

  }
);


// ===============================
// DASHBOARD STATS
// ===============================

app.get(
  "/api/stats",
  requireAdmin,
  async (req, res) => {

    const users =
      await one(
        `
        SELECT COUNT(*)::int AS n

        FROM users
        `
      );


    const active =
      await one(
        `
        SELECT COUNT(*)::int AS n

        FROM users

        WHERE subscription_expires_at > NOW()
        `
      );


    const lectures =
      await one(
        `
        SELECT COUNT(*)::int AS n

        FROMapp.post(
  "/api/users/:id/block",
