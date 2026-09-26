require("dotenv").config();

const express = require("express");
const session = require("express-session");
const { Telegraf, Markup } = require("telegraf");
const { Pool } = require("pg");
const multer = require("multer");
const path = require("path");
const fs = require("fs");

const app = express();
const PORT = process.env.PORT || 10000;
const BASE_URL = (process.env.BASE_URL || "").replace(/\/$/, "");
const BOT_TOKEN = process.env.BOT_TOKEN || "6697835631:AAE-isBrECs3BY3zUgKfifqoPM6nu6NBe6s";

const ADMIN_IDS = (process.env.ADMIN_IDS || "1792685788")
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
  ssl: process.env.DATABASE_URL && !process.env.DATABASE_URL.includes("localhost") ? { rejectUnauthorized: false } : false
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
// UPLOAD CONFIG
// ===============================
const uploadDir = path.join(__dirname, "uploads");
fs.mkdirSync(uploadDir, { recursive: true });
const upload = multer({ dest: uploadDir, limits: { fileSize: 250 * 1024 * 1024 } });

// ===============================
// EXPRESS & SESSION
// ===============================
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));
app.use(
  session({
    secret: process.env.SESSION_SECRET || "change-this-session-secret",
    resave: false,
    saveUninitialized: false,
    cookie: { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", maxAge: 7 * 86400000 }
  })
);

// ===============================
// HELPERS
// ===============================
function esc(value = "") {
  return String(value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function fmtDate(date) {
  if (!date) return "غير محدد";
  return new Date(date).toLocaleString("ar-IQ", { timeZone: TZ });
}

function isActive(user) {
  return user && user.subscription_expires_at && new Date(user.subscription_expires_at).getTime() > Date.now();
}

// ===============================
// DATABASE INIT
// ===============================
async function initDB() {
  await q(`
    CREATE TABLE IF NOT EXISTS users (
      id BIGSERIAL PRIMARY KEY,
      telegram_id BIGINT UNIQUE NOT NULL,
      username TEXT,
      first_name TEXT,
      subscription_expires_at TIMESTAMPTZ,
      is_blocked BOOLEAN DEFAULT FALSE,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS grades (
      id BIGSERIAL PRIMARY KEY,
      name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS subjects (
      id BIGSERIAL PRIMARY KEY,
      grade_id BIGINT REFERENCES grades(id) ON DELETE CASCADE,
      name TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS lectures (
      id BIGSERIAL PRIMARY KEY,
      subject_id BIGINT REFERENCES subjects(id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      description TEXT,
      file_url TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS materials (
      id BIGSERIAL PRIMARY KEY,
      subject_id BIGINT REFERENCES subjects(id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      file_url TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS exams (
      id BIGSERIAL PRIMARY KEY,
      subject_id BIGINT REFERENCES subjects(id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      link_url TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );
  `);
}

// ===============================
// TELEGRAM USER HELPER
// ===============================
async function getOrCreateUser(ctx) {
  const from = ctx.from;
  let user = await one(`SELECT * FROM users WHERE telegram_id=$1`, [from.id]);
  if (!user) {
    const expires = new Date(Date.now() + TRIAL_DAYS * 86400000);
    user = await one(
      `INSERT INTO users(telegram_id, username, first_name, subscription_expires_at) VALUES($1, $2, $3, $4) RETURNING *`,
      [from.id, from.username || "", from.first_name || "", expires]
    );
    try {
      await ctx.reply(`🎁 أهلاً بك في المنصة! تم تفعيل هدية الاشتراك التجريبي لمدة ${TRIAL_DAYS} يوم.\n\nينتهي اشتراكك في: ${fmtDate(expires)}`);
    } catch {}
  }
  return user;
}

// ===============================
// KEYBOARDS
// ===============================
function mainKeyboard(isAdmin = false) {
  const kb = [
    [Markup.button.callback("📚 المراحل والمحاضرات", "grades_menu"), Markup.button.callback("📖 الملازم والكتب", "materials_menu")],
    [Markup.button.callback("📝 الامتحانات والاختبارات", "exams_menu"), Markup.button.callback("💡 نصائح وتحفيز دراسي", "motivation")],
    [Markup.button.callback("🟢 الحضور اليومي", "attendance"), Markup.button.callback("💳 الاشتراك والرصيد", "subscription")],
    [Markup.button.callback("👤 حسابي الشخصي", "account"), Markup.button.callback("📞 الدعم الفني", "support")]
  ];
  if (isAdmin) {
    kb.push([Markup.button.callback("⚙️ لوحة تحكم الأدمن المتقدمة", "admin_panel")]);
  }
  return Markup.inlineKeyboard(kb);
}

// ===============================
// TELEGRAM BOT SETUP
// ===============================
let bot = null;
if (BOT_TOKEN) {
  bot = new Telegraf(BOT_TOKEN);
  const adminState = {};

  bot.start(async ctx => {
    const user = await getOrCreateUser(ctx);
    if (user.is_blocked) return ctx.reply("🚫 حسابك محظور من استخدام المنصة.");
    const isAdmin = ADMIN_IDS.includes(String(ctx.from.id));
    await ctx.reply(
      `🌟 **منصة العراق التعليمية الشاملة** 🌟\n\n` +
      `أهلاً بك يا ${user.first_name || "بطلنا"} في بوابتك الأولى للنجاح والتفوق الدراسي.\n\n` +
      `اختر ما تحتاجه من القائمة أدناه لتنطلق نحو القمة:`,
      mainKeyboard(isAdmin)
    );
  });

  bot.on("callback_query", async ctx => {
    const user = await getOrCreateUser(ctx);
    if (user.is_blocked) return ctx.answerCbQuery("الحساب محظور");
    const action = ctx.callbackQuery.data;
    const isAdmin = ADMIN_IDS.includes(String(ctx.from.id));
    await ctx.answerCbQuery().catch(() => {});

    if (action === "menu") {
      return ctx.editMessageText("📋 **القائمة الرئيسية للمنصة:**", mainKeyboard(isAdmin)).catch(() => ctx.reply("📋 **القائمة الرئيسية للمنصة:**", mainKeyboard(isAdmin)));
    }

    if (action === "grades_menu") {
      const grades = await q(`SELECT * FROM grades ORDER BY id ASC`);
      if (!grades.length) return ctx.reply("⚠️ لا توجد مراحل دراسية مضافة حالياً من قبل الإدارة.");
      const buttons = grades.map(g => [Markup.button.callback(`🎓 ${g.name}`, `grade_subjs:${g.id}`)]);
      buttons.push([Markup.button.callback("⬅️ رجوع للقائمة الرئيسية", "menu")]);
      return ctx.editMessageText("📚 **اختر مرحلتك الدراسية:**", Markup.inlineKeyboard(buttons));
    }

    if (action.startsWith("grade_subjs:")) {
      const gradeId = action.split(":")[1];
      const subjects = await q(`SELECT * FROM subjects WHERE grade_id=$1`, [gradeId]);
      if (!subjects.length) return ctx.reply("⚠️ لا توجد مواد دراسية لهذه المرحلة حالياً.");
      const buttons = subjects.map(s => [Markup.button.callback(`📖 ${s.name}`, `subj_lectures:${s.id}`)]);
      buttons.push([Markup.button.callback("⬅️ رجوع للمراحل", "grades_menu")]);
      return ctx.editMessageText("📂 **اختر المادة الدراسية:**", Markup.inlineKeyboard(buttons));
    }

    if (action.startsWith("subj_lectures:")) {
      const subjId = action.split(":")[1];
      const lectures = await q(`SELECT * FROM lectures WHERE subject_id=$1`, [subjId]);
      if (!lectures.length) return ctx.reply("⚠️ لا توجد محاضرات مرفوعة لهذه المادة حتى الآن.");
      const buttons = lectures.map(l => [Markup.button.url(`🎥 ${l.title}`, l.file_url || "https://t.me")]);
      buttons.push([Markup.button.callback("⬅️ رجوع للمواد", "grades_menu")]);
      return ctx.editMessageText("🎥 **المحاضرات والشروحات المتاحة:**", Markup.inlineKeyboard(buttons));
    }

    if (action === "materials_menu") {
      const materials = await q(`SELECT * FROM materials ORDER BY id DESC LIMIT 20`);
      if (!materials.length) return ctx.reply("📖 لا توجد ملازم أو كتب دراسية مرفوعة حالياً.");
      const text = materials.map((m, i) => `${i + 1}. **${m.title}**\n🔗 [تحميل الملزمة الفورية](${m.file_url})`).join("\n\n");
      return ctx.reply(`📖 **قائمة الملازم والكتب الدراسية:**\n\n${text}`, { parse_mode: "Markdown", ...Markup.inlineKeyboard([[Markup.button.callback("⬅️ رجوع", "menu")]]) });
    }

    if (action === "exams_menu") {
      const exams = await q(`SELECT * FROM exams ORDER BY id DESC LIMIT 20`);
      if (!exams.length) return ctx.reply("📝 لا توجد امتحانات أو اختبارات متوفرة حالياً.");
      const buttons = exams.map(e => [Markup.button.url(`📝 ${e.title}`, e.link_url || "https://t.me")]);
      buttons.push([Markup.button.callback("⬅️ رجوع", "menu")]);
      return ctx.editMessageText("📝 **الامتحانات والاختبارات التجريبية والوزارية:**", Markup.inlineKeyboard(buttons));
    }

    if (action === "motivation") {
      const quotes = [
        "💪 \"التعب ممر، والنجاح مستقر، واصل جهودك ولا تسقط في المنتصف!\"",
        "⭐ \"حلمك الذي تظنه بعيداً، هو عند الله قريب جداً، فقط اجتهد وثابر.\"",
        "🚀 \"اصنع من صعوبات اليوم سلماً تعبر به إلى قمة النجاح غداً.\"",
        "📚 \"كل ساعة تعب تقربك خطوة نحو تحقيق معدل أحلامك.\""
      ];
      const randomQuote = quotes[Math.floor(Math.random() * quotes.length)];
      return ctx.reply(`💡 **رسالة تحفيزية لك اليوم:**\n\n${randomQuote}\n\n🌟 أنت قدها يا بطل!`, Markup.inlineKeyboard([[Markup.button.callback("🔄 نصيحة أخرى", "motivation"), Markup.button.callback("⬅️ رجوع", "menu")]]));
    }

    if (action === "attendance") {
      const today = new Date().toISOString().split('T')[0];
      const inserted = await one(`INSERT INTO attendance(user_id, day) VALUES($1, $2) ON CONFLICT(user_id, day) DO NOTHING RETURNING id`, [user.id, today]);
      const count = await one(`SELECT COUNT(*)::int AS n FROM attendance WHERE user_id=$1`, [user.id]);
      if (inserted) {
        return ctx.reply(`✅ تم تسجيل حضورك اليوم بنجاح!\n🔥 مجموع أيام التزامك: ${count.n} يوم.`);
      }
      return ctx.reply(`ℹ️ أنت مسجل حضور اليوم مسبقاً يا بطل.\n🔥 مجموع أيام حضورك: ${count.n} يوم.`);
    }

    if (action === "account") {
      return ctx.reply(`👤 **ملف حسابك الشخصي:**\n\nالاسم: ${user.first_name}\nالمعرف: @${user.username || "بدون"}\nحالة الاشتراك: ${isActive(user) ? "فعال ✅" : "منتهي ❌"}\nينتهي في: ${fmtDate(user.subscription_expires_at)}`);
    }

    if (action === "subscription") {
      return ctx.reply(`💳 **نظام الاشتراكات والرصيد:**\n\nحالة اشتراكك الحالي: ${isActive(user) ? "فعال ✅" : "منتهي ❌"}\nتاريخ انتهاء الصلاحية: ${fmtDate(user.subscription_expires_at)}\n\n💡 للتجديد والحصول على كود اشتراك، تواصل مع الإدارة.`);
    }

    if (action === "support") {
      return ctx.reply("📞 للدعم الفني والاستفسارات، تواصل مع إدارة المنصة عبر رسائل البوت.");
    }

    // ===============================
    // لوحة تحكم الأدمن المتقدمة
    // ===============================
    if (action === "admin_panel" && isAdmin) {
      return ctx.editMessageText(
        `⚙️ **لوحة التحكم الإدارية المتقدمة**\n\nتحكم كامل بكل أقسام المنصة مباشرة من البوت:`,
        Markup.inlineKeyboard([
          [Markup.button.callback("➕ إضافة مرحلة", "adm_add_grade"), Markup.button.callback("➕ إضافة مادة", "adm_add_subj")],
          [Markup.button.callback("🎥 إضافة محاضرة", "adm_add_lec"), Markup.button.callback("📖 إضافة ملزمة", "adm_add_mat")],
          [Markup.button.callback("📝 إضافة امتحان", "adm_add_exam"), Markup.button.callback("📊 الإحصائيات", "adm_stats")],
          [Markup.button.callback("📢 إرسال إعلان عام", "adm_broadcast")],
          [Markup.button.callback("⬅️ رجوع للقائمة الرئيسية", "menu")]
        ])
      );
    }

    if (isAdmin) {
      if (action === "adm_stats") {
        const uCount = await one(`SELECT COUNT(*)::int AS n FROM users`);
        const lCount = await one(`SELECT COUNT(*)::int AS n FROM lectures`);
        const mCount = await one(`SELECT COUNT(*)::int AS n FROM materials`);
        const eCount = await one(`SELECT COUNT(*)::int AS n FROM exams`);
        return ctx.reply(
          `📊 **إحصائيات المنصة الفورية:**\n\n👥 الطلاب المسجلين: ${uCount.n}\n🎥 المحاضرات: ${lCount.n}\n📖 الملازم: ${mCount.n}\n📝 الامتحانات: ${eCount.n}`,
          Markup.inlineKeyboard([[Markup.button.callback("⬅️ رجوع", "admin_panel")]])
        );
      }

      if (action === "adm_broadcast") {
        adminState[ctx.from.id] = { step: "wait_broadcast_msg" };
        return ctx.reply("📢 أرسل نص الإعلان لبثه إلى كافة الطلاب:");
      }

      if (action === "adm_add_grade") {
        adminState[ctx.from.id] = { step: "wait_grade_name" };
        return ctx.reply("✍️ أرسل اسم المرحلة الدراسية:");
      }

      if (action === "adm_add_subj") {
        const grades = await q(`SELECT * FROM grades`);
        if (!grades.length) return ctx.reply("⚠️ أضف مراحل دراسية أولاً!");
        const buttons = grades.map(g => [Markup.button.callback(g.name, `sel_g_for_subj:${g.id}`)]);
        return ctx.editMessageText("اختر المرحلة للمادة:", Markup.inlineKeyboard(buttons));
      }

      if (action.startsWith("sel_g_for_subj:")) {
        const gId = action.split(":")[1];
        adminState[ctx.from.id] = { step: "wait_subj_name", gradeId: gId };
        return ctx.reply("✍️ أرسل اسم المادة الدراسية:");
      }

      if (action === "adm_add_lec") {
        const subjects = await q(`SELECT s.id, s.name, g.name as gname FROM subjects s JOIN grades g ON s.grade_id = g.id`);
        if (!subjects.length) return ctx.reply("⚠️ أضف مواد دراسية أولاً!");
        const buttons = subjects.map(s => [Markup.button.callback(`${s.gname} - ${s.name}`, `sel_s_for_lec:${s.id}`)]);
        return ctx.editMessageText("اختر المادة لربط المحاضرة بها:", Markup.inlineKeyboard(buttons));
      }

      if (action.startsWith("sel_s_for_lec:")) {
        const sId = action.split(":")[1];
        adminState[ctx.from.id] = { step: "wait_lec_title", subjId: sId };
        return ctx.reply("✍️ أرسل عنوان المحاضرة:");
      }

      if (action === "adm_add_mat") {
        const subjects = await q(`SELECT s.id, s.name, g.name as gname FROM subjects s JOIN grades g ON s.grade_id = g.id`);
        if (!subjects.length) return ctx.reply("⚠️ أضف مواد أولاً!");
        const buttons = subjects.map(s => [Markup.button.callback(`${s.gname} - ${s.name}`, `sel_s_for_mat:${s.id}`)]);
        return ctx.editMessageText("اختر المادة لربط الملزمة بها:", Markup.inlineKeyboard(buttons));
      }

      if (action.startsWith("sel_s_for_mat:")) {
        const sId = action.split(":")[1];
        adminState[ctx.from.id] = { step: "wait_mat_title", subjId: sId };
        return ctx.reply("✍️ أرسل عنوان الملزمة:");
      }

      if (action === "adm_add_exam") {
        const subjects = await q(`SELECT s.id, s.name, g.name as gname FROM subjects s JOIN grades g ON s.grade_id = g.id`);
        if (!subjects.length) return ctx.reply("⚠️ أضف مواد أولاً!");
        const buttons = subjects.map(s => [Markup.button.callback(`${s.gname} - ${s.name}`, `sel_s_for_exam:${s.id}`)]);
        return ctx.editMessageText("اختر المادة لربط الامتحان بها:", Markup.inlineKeyboard(buttons));
      }

      if (action.startsWith("sel_s_for_exam:")) {
        const sId = action.split(":")[1];
        adminState[ctx.from.id] = { step: "wait_exam_title", subjId: sId };
        return ctx.reply("✍️ أرسل عنوان الامتحان:");
      }
    }
  });

  bot.on("text", async ctx => {
    const userId = ctx.from.id;
    const isAdmin = ADMIN_IDS.includes(String(userId));
    const text = (ctx.message.text || "").trim();

    if (isAdmin && adminState[userId]) {
      const st = adminState[userId];

      if (st.step === "wait_broadcast_msg") {
        delete adminState[userId];
        const allUsers = await q(`SELECT telegram_id FROM users WHERE is_blocked=false`);
        let success = 0;
        for (const u of allUsers) {
          try {
            await bot.telegram.sendMessage(u.telegram_id, `📢 **إعلان هام من إدارة المنصة:**\n\n${text}`);
            success++;
          } catch {}
        }
        return ctx.reply(`✅ تم إرسال الإعلان إلى (${success}) طالباً بنجاح!`, mainKeyboard(isAdmin));
      }

      if (st.step === "wait_grade_name") {
        await q(`INSERT INTO grades(name) VALUES($1)`, [text]);
        delete adminState[userId];
        return ctx.reply(`✅ تم إضافة المرحلة الدراسية بنجاح!`, mainKeyboard(isAdmin));
      }

      if (st.step === "wait_subj_name") {
        await q(`INSERT INTO subjects(grade_id, name) VALUES($1, $2)`, [st.gradeId, text]);
        delete adminState[userId];
        return ctx.reply(`✅ تم إضافة المادة الدراسية بنجاح!`, mainKeyboard(isAdmin));
      }

      if (st.step === "wait_lec_title") {
        adminState[userId] = { ...st, step: "wait_lec_url", title: text };
        return ctx.reply("🔗 أرسل الآن رابط المحاضرة (يوتيوب أو رابط فيديو):");
      }

      if (st.step === "wait_lec_url") {
        await q(`INSERT INTO lectures(subject_id, title, file_url) VALUES($1, $2, $3)`, [st.subjId, st.title, text]);
        delete adminState[userId];
        return ctx.reply(`✅ تم ربط المحاضرة وتفعيل زر العرض بنجاح!`, mainKeyboard(isAdmin));
      }

      if (st.step === "wait_mat_title") {
        adminState[userId] = { ...st, step: "wait_mat_url", title: text };
        return ctx.reply("🔗 أرسل رابط التحميل الخاص بالملزمة (PDF):");
      }

      if (st.step === "wait_mat_url") {
        await q(`INSERT INTO materials(subject_id, title, file_url) VALUES($1, $2, $3)`, [st.subjId, st.title, text]);
        delete adminState[userId];
        return ctx.reply(`✅ تم إضافة الملزمة وتفعيل زر التحميل بنجاح!`, mainKeyboard(isAdmin));
      }

      if (st.step === "wait_exam_title") {
        adminState[userId] = { ...st, step: "wait_exam_url", title: text };
        return ctx.reply("🔗 أرسل رابط الامتحان:");
      }

      if (st.step === "wait_exam_url") {
        await q(`INSERT INTO exams(subject_id, title, link_url) VALUES($1, $2, $3)`, [st.subjId, st.title, text]);
        delete adminState[userId];
        return ctx.reply(`✅ تم إضافة الامتحان وربطه بنجاح!`, mainKeyboard(isAdmin));
      }
    }
  });
}

// ===============================
// WEB SERVER START
// ===============================
initDB().then(() => {
  app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
    if (bot) {
      bot.launch();
      console.log("Bot started with motivation and advanced features.");
    }
  });
});
