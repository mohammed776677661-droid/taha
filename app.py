import os
import sqlite3
import secrets
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, session,
    render_template_string, jsonify, send_from_directory,
    flash
)
from werkzeug.utils import secure_filename

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None


# =========================================================
# CONFIG
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

DATABASE = os.environ.get(
    "DATABASE_PATH",
    "platform.db"
)

UPLOAD_FOLDER = os.environ.get(
    "UPLOAD_FOLDER",
    "uploads"
)

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "123456"
)

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    ""
)

GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.7-flash"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            site_name TEXT DEFAULT 'منصة جامعة الأنبار التعليمية',
            logo TEXT DEFAULT '',
            primary_color TEXT DEFAULT '#2563eb',
            secondary_color TEXT DEFAULT '#0f172a',
            accent_color TEXT DEFAULT '#f59e0b',
            welcome TEXT DEFAULT 'معاً نحو مستقبل جامعي أفضل',
            notice TEXT DEFAULT 'أهلاً بكم في منصة جامعة الأنبار التعليمية'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            college TEXT DEFAULT '',
            department TEXT DEFAULT '',
            stage TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            attendance_date TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            icon TEXT DEFAULT 'fa-book',
            color TEXT DEFAULT '#2563eb'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            video_url TEXT DEFAULT '',
            file_url TEXT DEFAULT '',
            lesson_number INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT DEFAULT '',
            duration INTEGER DEFAULT 30,
            questions TEXT DEFAULT '',
            answers TEXT DEFAULT '',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT,
            exam_id INTEGER,
            score INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ai_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT,
            tool TEXT,
            input_text TEXT,
            output_text TEXT,
            created_at TEXT
        )
    """)

    cur.execute(
        "SELECT COUNT(*) AS c FROM settings"
    )

    if cur.fetchone()["c"] == 0:
        cur.execute("""
            INSERT INTO settings
            (site_name, welcome, notice)
            VALUES (?, ?, ?)
        """, (
            "منصة جامعة الأنبار التعليمية",
            "معاً نحو مستقبل جامعي أفضل",
            "أهلاً بكم في منصة جامعة الأنبار التعليمية"
        ))

    cur.execute(
        "SELECT COUNT(*) AS c FROM subjects"
    )

    if cur.fetchone()["c"] == 0:

        subjects = [
            ("الطب", "مواد ومحاضرات كلية الطب", "fa-heart-pulse"),
            ("الهندسة", "محاضرات ومواد هندسية", "fa-gears"),
            ("علوم الحاسوب", "البرمجة وتقنيات المعلومات", "fa-laptop-code"),
            ("العلوم", "مواد العلوم الأساسية", "fa-flask"),
            ("الآداب", "المواد الإنسانية والأدبية", "fa-book-open"),
            ("التربية", "المناهج والمواد التربوية", "fa-school"),
            ("القانون", "محاضرات ومواد القانون", "fa-scale-balanced"),
            ("الإدارة والاقتصاد", "المواد الإدارية والاقتصادية", "fa-chart-line"),
        ]

        for item in subjects:
            cur.execute("""
                INSERT INTO subjects
                (name, description, icon)
                VALUES (?, ?, ?)
            """, item)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# HELPERS
# =========================================================

def settings():
    conn = db()
    row = conn.execute(
        "SELECT * FROM settings LIMIT 1"
    ).fetchone()
    conn.close()
    return row


def admin_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if not session.get("admin"):
            return redirect(url_for("admin_login"))

        return func(*args, **kwargs)

    return wrapper


def current_student():
    return session.get("student_name", "")


def gemini_client():

    if not GEMINI_API_KEY or genai is None:
        return None

    try:
        return genai.Client(
            api_key=GEMINI_API_KEY
        )
    except Exception:
        return None


def ask_gemini(prompt):

    client = gemini_client()

    if not client:
        return "لم يتم تفعيل Gemini بعد. أضف GEMINI_API_KEY في إعدادات Render."

    try:

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        if hasattr(response, "text") and response.text:
            return response.text

        return "لم يتم الحصول على نتيجة."

    except Exception as e:

        return f"حدث خطأ أثناء الاتصال بالذكاء الاصطناعي: {str(e)}"


def save_ai_history(tool, input_text, output_text):

    conn = db()

    conn.execute("""
        INSERT INTO ai_history
        (student_name, tool, input_text, output_text, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        current_student(),
        tool,
        input_text,
        output_text,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


# =========================================================
# BASE HTML
# =========================================================

BASE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<meta name="theme-color"
content="{{ settings.primary_color }}">

<title>{{ title }} - {{ settings.site_name }}</title>

<link rel="manifest"
href="{{ url_for('manifest') }}">

<link rel="stylesheet"
href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css">

<style>

*{
    box-sizing:border-box;
    margin:0;
    padding:0;
}

body{
    font-family:
    Tahoma,
    Arial,
    sans-serif;

    background:#f1f5f9;
    color:#172033;
}

a{
    text-decoration:none;
    color:inherit;
}

.container{
    width:min(1100px,94%);
    margin:auto;
}

.navbar{
    background:{{ settings.secondary_color }};
    color:white;
    position:sticky;
    top:0;
    z-index:1000;
    box-shadow:0 3px 15px rgba(0,0,0,.15);
}

.nav-inner{
    min-height:68px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:15px;
}

.brand{
    display:flex;
    align-items:center;
    gap:10px;
    font-weight:900;
}

.brand img{
    width:42px;
    height:42px;
    object-fit:cover;
    border-radius:12px;
}

.nav-links{
    display:flex;
    gap:7px;
    flex-wrap:wrap;
}

.nav-links a{
    padding:10px 13px;
    border-radius:10px;
    color:white;
    font-size:14px;
}

.nav-links a:hover{
    background:rgba(255,255,255,.12);
}

.hero{
    margin:25px 0;
    padding:35px 25px;
    border-radius:25px;
    color:white;
    background:
    linear-gradient(
        135deg,
        {{ settings.primary_color }},
        {{ settings.secondary_color }}
    );
    box-shadow:0 15px 35px rgba(15,23,42,.15);
}

.hero h1{
    font-size:32px;
    margin-bottom:10px;
}

.hero p{
    opacity:.9;
    line-height:1.9;
}

.notice{
    background:white;
    border-right:5px solid {{ settings.accent_color }};
    padding:17px;
    border-radius:15px;
    margin:20px 0;
    box-shadow:0 5px 18px rgba(0,0,0,.06);
}

.grid{
    display:grid;
    grid-template-columns:
    repeat(auto-fit,minmax(210px,1fr));
    gap:17px;
}

.card{
    background:white;
    border-radius:20px;
    padding:22px;
    box-shadow:0 7px 22px rgba(0,0,0,.07);
    transition:.2s;
}

.card:hover{
    transform:translateY(-3px);
}

.card-icon{
    width:52px;
    height:52px;
    display:flex;
    align-items:center;
    justify-content:center;
    border-radius:15px;
    color:white;
    background:{{ settings.primary_color }};
    font-size:22px;
    margin-bottom:15px;
}

.card h3{
    margin-bottom:8px;
}

.card p{
    color:#64748b;
    line-height:1.8;
    font-size:14px;
}

.btn{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    gap:8px;
    border:none;
    cursor:pointer;
    background:{{ settings.primary_color }};
    color:white;
    padding:12px 18px;
    border-radius:12px;
    margin-top:13px;
    font-size:15px;
}

.btn:hover{
    opacity:.9;
}

.btn-danger{
    background:#dc2626;
}

.btn-green{
    background:#16a34a;
}

.btn-dark{
    background:#172033;
}

.input,
textarea,
select{
    width:100%;
    padding:13px;
    border:1px solid #dbe3ef;
    border-radius:12px;
    outline:none;
    margin-top:7px;
    margin-bottom:15px;
    background:white;
    font-family:inherit;
}

textarea{
    min-height:150px;
    resize:vertical;
}

label{
    font-weight:bold;
    font-size:14px;
}

.section-title{
    margin:30px 0 15px;
    display:flex;
    justify-content:space-between;
    align-items:center;
}

.table-wrap{
    overflow-x:auto;
    background:white;
    border-radius:18px;
}

table{
    width:100%;
    border-collapse:collapse;
}

th,td{
    padding:13px;
    border-bottom:1px solid #edf1f6;
    text-align:right;
}

th{
    background:#f8fafc;
}

.footer{
    margin-top:45px;
    background:#0f172a;
    color:white;
    padding:30px 0;
    text-align:center;
}

.flash{
    margin:15px 0;
    padding:13px;
    border-radius:12px;
    background:#dcfce7;
    color:#166534;
}

.stat{
    font-size:30px;
    font-weight:900;
    color:{{ settings.primary_color }};
}

.admin-bar{
    background:#111827;
    color:white;
    padding:10px;
    text-align:center;
}

.ai-box{
    background:white;
    padding:20px;
    border-radius:20px;
    box-shadow:0 5px 20px rgba(0,0,0,.07);
    line-height:2;
    white-space:pre-wrap;
}

.video{
    width:100%;
    aspect-ratio:16/9;
    border:0;
    border-radius:18px;
}

@media(max-width:700px){

    .nav-inner{
        flex-direction:column;
        padding:12px 0;
    }

    .nav-links{
        justify-content:center;
    }

    .hero h1{
        font-size:24px;
    }

    .grid{
        grid-template-columns:
        repeat(2,1fr);
    }

}

@media(max-width:450px){

    .grid{
        grid-template-columns:1fr;
    }

}

</style>

</head>

<body>

{% if session.get("admin") %}
<div class="admin-bar">
    <a href="{{ url_for('admin') }}">
        لوحة تحكم الإدارة
    </a>
    |
    <a href="{{ url_for('admin_logout') }}">
        تسجيل الخروج
    </a>
</div>
{% endif %}

<nav class="navbar">

<div class="container nav-inner">

<a class="brand" href="{{ url_for('home') }}">

{% if settings.logo %}
<img src="{{ settings.logo }}">
{% else %}
<div class="card-icon" style="margin:0;width:42px;height:42px;">
<i class="fa-solid fa-graduation-cap"></i>
</div>
{% endif %}

<span>
{{ settings.site_name }}
</span>

</a>

<div class="nav-links">

<a href="{{ url_for('home') }}">
<i class="fa-solid fa-house"></i>
الرئيسية
</a>

<a href="{{ url_for('subjects') }}">
<i class="fa-solid fa-book"></i>
المواد
</a>

<a href="{{ url_for('ai') }}">
<i class="fa-solid fa-robot"></i>
الذكاء الاصطناعي
</a>

<a href="{{ url_for('exams') }}">
<i class="fa-solid fa-file-pen"></i>
الاختبارات
</a>

<a href="{{ url_for('profile') }}">
<i class="fa-solid fa-user"></i>
حسابي
</a>

</div>

</div>

</nav>

<main class="container">

{% with messages = get_flashed_messages() %}
{% for message in messages %}
<div class="flash">
{{ message }}
</div>
{% endfor %}
{% endwith %}

{{ content|safe }}

</main>

<footer class="footer">

<div class="container">

<strong>{{ settings.site_name }}</strong>

<br>

{{ settings.welcome }}

<br><br>

جميع الحقوق محفوظة © {{ now.year }}

</div>

</footer>

</body>
</html>
"""


def render_page(title, content, **context):

    s = settings()

    return render_template_string(
        BASE,
        title=title,
        content=render_template_string(
            content,
            settings=s,
            now=datetime.now(),
            **context
        ),
        settings=s,
        now=datetime.now(),
        **context
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    conn = db()

    subjects = conn.execute("""
        SELECT * FROM subjects
        ORDER BY id DESC
    """).fetchall()

    announcements = conn.execute("""
        SELECT * FROM announcements
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    content = """

<div class="hero">

<h1>
<i class="fa-solid fa-graduation-cap"></i>
{{ settings.site_name }}
</h1>

<p>
{{ settings.welcome }}
</p>

{% if not session.get('student_name') %}

<a class="btn"
href="{{ url_for('attendance') }}">
<i class="fa-solid fa-user-check"></i>
دخول الطالب وتسجيل الحضور
</a>

{% endif %}

</div>

<div class="notice">
<i class="fa-solid fa-bullhorn"></i>
<strong>إعلان:</strong>
{{ settings.notice }}
</div>

<div class="section-title">
<h2>الخدمات التعليمية</h2>
</div>

<div class="grid">

<div class="card">
<div class="card-icon">
<i class="fa-solid fa-book-open"></i>
</div>
<h3>المحاضرات</h3>
<p>الوصول إلى المحاضرات والمواد التعليمية.</p>
<a class="btn" href="{{ url_for('subjects') }}">الدخول</a>
</div>

<div class="card">
<div class="card-icon">
<i class="fa-solid fa-robot"></i>
</div>
<h3>مساعد Gemini</h3>
<p>ترجمة وتلخيص وشرح وحل الأسئلة بالذكاء الاصطناعي.</p>
<a class="btn" href="{{ url_for('ai') }}">استخدام المساعد</a>
</div>

<div class="card">
<div class="card-icon">
<i class="fa-solid fa-pen-to-square"></i>
</div>
<h3>الاختبارات</h3>
<p>اختبارات إلكترونية ومعرفة النتائج.</p>
<a class="btn" href="{{ url_for('exams') }}">الاختبارات</a>
</div>

<div class="card">
<div class="card-icon">
<i class="fa-solid fa-user-check"></i>
</div>
<h3>الحضور</h3>
<p>سجل حضورك اليومي داخل المنصة.</p>
<a class="btn" href="{{ url_for('attendance') }}">تسجيل الحضور</a>
</div>

</div>

<div class="section-title">
<h2>الكليات والمواد</h2>
</div>

<div class="grid">

{% for subject in subjects %}

<div class="card">

<div class="card-icon">
<i class="fa-solid {{ subject.icon }}"></i>
</div>

<h3>{{ subject.name }}</h3>

<p>
{{ subject.description }}
</p>

<a class="btn"
href="{{ url_for('subject', subject_id=subject.id) }}">
عرض المواد
</a>

</div>

{% endfor %}

</div>

{% if announcements %}

<div class="section-title">
<h2>آخر الإعلانات</h2>
</div>

{% for a in announcements %}

<div class="notice">

<h3>{{ a.title }}</h3>

<p style="margin-top:8px;">
{{ a.content }}
</p>

<small>
{{ a.created_at[:16] }}
</small>

</div>

{% endfor %}

{% endif %}
"""

    return render_page(
        "الرئيسية",
        content,
        subjects=subjects,
        announcements=announcements
    )


# =========================================================
# ATTENDANCE
# =========================================================

@app.route("/attendance", methods=["GET", "POST"])
def attendance():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        college = request.form.get("college", "").strip()
        department = request.form.get("department", "").strip()
        stage = request.form.get("stage", "").strip()
        phone = request.form.get("phone", "").strip()

        if not name:
            flash("اكتب اسم الطالب.")
            return redirect(url_for("attendance"))

        conn = db()

        student = conn.execute("""
            SELECT * FROM students
            WHERE name=?
            ORDER BY id DESC
            LIMIT 1
        """, (name,)).fetchone()

        if not student:

            cur = conn.execute("""
                INSERT INTO students
                (name,college,department,stage,phone,created_at)
                VALUES(?,?,?,?,?,?)
            """, (
                name,
                college,
                department,
                stage,
                phone,
                datetime.now().isoformat()
            ))

            student_id = cur.lastrowid

        else:
            student_id = student["id"]

        today = str(date.today())

        existing = conn.execute("""
            SELECT id FROM attendance
            WHERE student_id=?
            AND attendance_date=?
        """, (
            student_id,
            today
        )).fetchone()

        if not existing:

            conn.execute("""
                INSERT INTO attendance
                (student_id,attendance_date,created_at)
                VALUES(?,?,?)
            """, (
                student_id,
                today,
                datetime.now().isoformat()
            ))

        conn.commit()
        conn.close()

        session["student_name"] = name

        flash("تم تسجيل حضورك بنجاح.")
        return redirect(url_for("home"))

    content = """

<div class="hero">
<h1>تسجيل حضور الطالب</h1>
<p>
سجل معلوماتك للدخول إلى المنصة.
</p>
</div>

<div class="card">

<form method="POST">

<label>اسم الطالب</label>
<input class="input"
name="name"
required
placeholder="اكتب اسمك الكامل">

<label>الكلية</label>
<input class="input"
name="college"
placeholder="مثال: كلية العلوم">

<label>القسم</label>
<input class="input"
name="department"
placeholder="مثال: قسم علوم الحاسوب">

<label>المرحلة</label>

<select class="input" name="stage">

<option value="">اختر المرحلة</option>
<option>الأولى</option>
<option>الثانية</option>
<option>الثالثة</option>
<option>الرابعة</option>
<option>الخامسة</option>
<option>السادسة</option>

</select>

<label>رقم الهاتف</label>

<input class="input"
name="phone"
placeholder="اختياري">

<button class="btn" type="submit">
<i class="fa-solid fa-check"></i>
تسجيل الحضور والدخول
</button>

</form>

</div>
"""

    return render_page(
        "تسجيل الحضور",
        content
    )


# =========================================================
# SUBJECTS
# =========================================================

@app.route("/subjects")
def subjects():

    conn = db()

    rows = conn.execute("""
        SELECT * FROM subjects
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    content = """

<div class="hero">
<h1>المواد الدراسية</h1>
<p>اختر الكلية أو المادة للوصول إلى المحاضرات.</p>
</div>

<div class="grid">

{% for subject in rows %}

<div class="card">

<div class="card-icon">
<i class="fa-solid {{ subject.icon }}"></i>
</div>

<h3>{{ subject.name }}</h3>

<p>{{ subject.description }}</p>

<a class="btn"
href="{{ url_for('subject', subject_id=subject.id) }}">
دخول المادة
</a>

</div>

{% endfor %}

</div>
"""

    return render_page(
        "المواد",
        content,
        rows=rows
    )


@app.route("/subject/<int:subject_id>")
def subject(subject_id):

    conn = db()

    subject_row = conn.execute("""
        SELECT * FROM subjects
        WHERE id=?
    """, (subject_id,)).fetchone()

    lessons = conn.execute("""
        SELECT * FROM lessons
        WHERE subject_id=?
        ORDER BY lesson_number ASC,id ASC
    """, (subject_id,)).fetchall()

    conn.close()

    if not subject_row:
        return "المادة غير موجودة", 404

    content = """

<div class="hero">

<h1>
<i class="fa-solid {{ subject_row.icon }}"></i>
{{ subject_row.name }}
</h1>

<p>
{{ subject_row.description }}
</p>

</div>

{% if lessons %}

{% for lesson in lessons %}

<div class="card" style="margin-bottom:15px;">

<h3>
المحاضرة {{ lesson.lesson_number }}
:
{{ lesson.title }}
</h3>

<p>
{{ lesson.description }}
</p>

{% if lesson.video_url %}

<div style="margin-top:15px;">

<iframe
class="video"
src="{{ lesson.video_url }}"
allowfullscreen>
</iframe>

</div>

{% endif %}

{% if lesson.file_url %}

<a class="btn"
href="{{ lesson.file_url }}"
target="_blank">

<i class="fa-solid fa-file"></i>
فتح الملف

</a>

{% endif %}

</div>

{% endfor %}

{% else %}

<div class="card">
لا توجد محاضرات مضافة لهذه المادة حالياً.
</div>

{% endif %}
"""

    return render_page(
        subject_row["name"],
        content,
        subject_row=subject_row,
        lessons=lessons
    )


# =========================================================
# AI
# =========================================================

@app.route("/ai")
def ai():

    content = """

<div class="hero">

<h1>
<i class="fa-solid fa-robot"></i>
المساعد التعليمي الذكي
</h1>

<p>
استخدم Gemini للترجمة والتلخيص والشرح وحل الأسئلة.
</p>

</div>

<div class="grid">

<div class="card">
<div class="card-icon">
<i class="fa-solid fa-language"></i>
</div>
<h3>الترجمة</h3>
<p>ترجمة النصوص بين العربية والإنجليزية.</p>
<a class="btn" href="{{ url_for('ai_tool',tool='translate') }}">
ابدأ
</a>
</div>

<div class="card">
<div class="card-icon">
<i class="fa-solid fa-compress"></i>
</div>
<h3>التلخيص</h3>
<p>اختصر المحاضرات والنصوص الطويلة.</p>
<a class="btn" href="{{ url_for('ai_tool',tool='summary') }}">
ابدأ
</a>
</div>

<div class="card">
<div class="card-icon">
<i class="fa-solid fa-brain"></i>
</div>
<h3>الخريطة الذهنية</h3>
<p>حوّل الدرس إلى نقاط منظمة.</p>
<a class="btn" href="{{ url_for('ai_tool',tool='mindmap') }}">
ابدأ
</a>
</div>

<div class="card">
<div class="card-icon">
<i class="fa-solid fa-circle-question"></i>
</div>
<h3>حل الأسئلة</h3>
<p>أرسل السؤال واحصل على شرح للحل.</p>
<a class="btn" href="{{ url_for('ai_tool',tool='solve') }}">
ابدأ
</a>
</div>

</div>
"""

    return render_page(
        "الذكاء الاصطناعي",
        content
    )


@app.route("/ai/<tool>", methods=["GET", "POST"])
def ai_tool(tool):

    names = {
        "translate": "الترجمة الذكية",
        "summary": "التلخيص الذكي",
        "mindmap": "الخريطة الذهنية",
        "solve": "حل الأسئلة"
    }

    if tool not in names:
        return "الأداة غير موجودة", 404

    result = ""

    if request.method == "POST":

        text = request.form.get("text", "").strip()

        if text:

            if tool == "translate":

                prompt = f"""
ترجم النص التالي ترجمة تعليمية دقيقة.
إذا كان النص عربياً ترجمه إلى الإنجليزية،
وإذا كان إنجليزياً ترجمه إلى العربية.

النص:

{text}
"""

            elif tool == "summary":

                prompt = f"""
لخص النص التالي للطالب الجامعي باللغة العربية.
استخرج أهم الأفكار والنقاط والتعاريف.
اجعل التلخيص واضحاً ومنظماً.

النص:

{text}
"""

            elif tool == "mindmap":

                prompt = f"""
حوّل النص التالي إلى خريطة ذهنية نصية منظمة باللغة العربية.
استخدم عنواناً رئيسياً ثم محاور وفرعيات.

النص:

{text}
"""

            else:

                prompt = f"""
أنت مساعد تعليمي جامعي.
حل السؤال التالي خطوة بخطوة باللغة العربية.
اذكر القانون أو الفكرة المستخدمة ثم الحل والنتيجة.

السؤال:

{text}
"""

            result = ask_gemini(prompt)

            save_ai_history(
                tool,
                text,
                result
            )

    content = """

<div class="hero">

<h1>{{ names[tool] }}</h1>

<p>
اكتب النص ثم اضغط تنفيذ.
</p>

</div>

<div class="card">

<form method="POST">

<textarea
name="text"
required
placeholder="اكتب النص أو السؤال هنا..."></textarea>

<button class="btn" type="submit">
<i class="fa-solid fa-wand-magic-sparkles"></i>
تنفيذ بواسطة Gemini
</button>

</form>

</div>

{% if result %}

<div class="section-title">
<h2>النتيجة</h2>
</div>

<div class="ai-box">
{{ result }}
</div>

{% endif %}
"""

    return render_page(
        names[tool],
        content,
        names=names,
        tool=tool,
        result=result
    )


# =========================================================
# EXAMS
# =========================================================

@app.route("/exams")
def exams():

    conn = db()

    rows = conn.execute("""
        SELECT * FROM exams
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    content = """

<div class="hero">

<h1>
<i class="fa-solid fa-file-pen"></i>
الاختبارات
</h1>

<p>
اختبر معلوماتك وسجل نتيجتك.
</p>

</div>

<div class="grid">

{% for exam in rows %}

<div class="card">

<div class="card-icon">
<i class="fa-solid fa-clipboard-question"></i>
</div>

<h3>{{ exam.title }}</h3>

<p>
المادة:
{{ exam.subject }}
</p>

<p>
المدة:
{{ exam.duration }} دقيقة
</p>

<a class="btn"
href="{{ url_for('exam', exam_id=exam.id) }}">
بدء الاختبار
</a>

</div>

{% else %}

<div class="card">
لا توجد اختبارات حالياً.
</div>

{% endfor %}

</div>
"""

    return render_page(
        "الاختبارات",
        content,
        rows=rows
    )


@app.route("/exam/<int:exam_id>", methods=["GET", "POST"])
def exam(exam_id):

    conn = db()

    exam_row = conn.execute("""
        SELECT * FROM exams
        WHERE id=?
    """, (exam_id,)).fetchone()

    conn.close()

    if not exam_row:
        return "الاختبار غير موجود", 404

    questions = []

    for line in exam_row["questions"].splitlines():

        if line.strip():
            questions.append(line.strip())

    if request.method == "POST":

        score = 0
        total = len(questions)

        answer_key = []

        for line in exam_row["answers"].splitlines():

            if line.strip():
                answer_key.append(line.strip())

        for i in range(total):

            user_answer = request.form.get(
                f"q{i}",
                ""
            ).strip().lower()

            correct = ""

            if i < len(answer_key):
                correct = answer_key[i].strip().lower()

            if user_answer == correct:
                score += 1

        conn = db()

        conn.execute("""
            INSERT INTO results
            (student_name,exam_id,score,total,created_at)
            VALUES(?,?,?,?,?)
        """, (
            current_student() or "طالب",
            exam_id,
            score,
            total,
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

        return redirect(
            url_for(
                "exam_result",
                exam_id=exam_id,
                score=score,
                total=total
            )
        )

    content = """

<div class="hero">

<h1>{{ exam_row.title }}</h1>

<p>
المادة: {{ exam_row.subject }}
</p>

<p>
الوقت المحدد:
{{ exam_row.duration }} دقيقة
</p>

</div>

<form method="POST">

{% for q in questions %}

<div class="card" style="margin-bottom:15px;">

<h3>
السؤال {{ loop.index }}
</h3>

<p style="margin:10px 0;line-height:1.9;">
{{ q }}
</p>

<input
class="input"
name="q{{ loop.index0 }}"
placeholder="اكتب إجابتك هنا"
required>

</div>

{% endfor %}

{% if questions %}

<button class="btn btn-green" type="submit">

<i class="fa-solid fa-paper-plane"></i>
إرسال الاختبار

</button>

{% else %}

<div class="card">
لم تتم إضافة أسئلة لهذا الاختبار.
</div>

{% endif %}

</form>
"""

    return render_page(
        exam_row["title"],
        content,
        exam_row=exam_row,
        questions=questions
    )


@app.route("/exam/<int:exam_id>/result")
def exam_result(exam_id):

    score = int(request.args.get("score", 0))
    total = int(request.args.get("total", 0))

    percentage = 0

    if total:
        percentage = round(
            score / total * 100
        )

    content = """

<div class="hero">

<h1>
<i class="fa-solid fa-trophy"></i>
نتيجة الاختبار
</h1>

<p>
تم تسجيل نتيجتك بنجاح.
</p>

</div>

<div class="card" style="text-align:center;">

<div class="stat">
{{ score }} / {{ total }}
</div>

<h2 style="margin-top:10px;">
{{ percentage }}%
</h2>

<br>

<a class="btn"
href="{{ url_for('exams') }}">
العودة إلى الاختبارات
</a>

</div>
"""

    return render_page(
        "نتيجة الاختبار",
        content,
        score=score,
        total=total,
        percentage=percentage
    )


# =========================================================
# PROFILE
# =========================================================

@app.route("/profile")
def profile():

    name = current_student()

    if not name:
        return redirect(url_for("attendance"))

    conn = db()

    student = conn.execute("""
        SELECT * FROM students
        WHERE name=?
        ORDER BY id DESC
        LIMIT 1
    """, (name,)).fetchone()

    attendance_count = 0

    if student:

        attendance_count = conn.execute("""
            SELECT COUNT(*) AS c
            FROM attendance
            WHERE student_id=?
        """, (
            student["id"],
        )).fetchone()["c"]

    results = conn.execute("""
        SELECT
            results.*,
            exams.title
        FROM results
        LEFT JOIN exams
        ON exams.id=results.exam_id
        WHERE results.student_name=?
        ORDER BY results.id DESC
        LIMIT 10
    """, (name,)).fetchall()

    conn.close()

    content = """

<div class="hero">

<h1>
<i class="fa-solid fa-user-graduate"></i>
حساب الطالب
</h1>

<p>
أهلاً {{ name }}
</p>

</div>

<div class="grid">

<div class="card">

<h3>اسم الطالب</h3>

<div class="stat"
style="font-size:22px;margin-top:10px;">
{{ student.name if student else name }}
</div>

</div>

<div class="card">

<h3>أيام الحضور</h3>

<div class="stat">
{{ attendance_count }}
</div>

</div>

<div class="card">

<h3>الكلية</h3>

<p style="margin-top:10px;">
{{ student.college if student else 'غير محددة' }}
</p>

</div>

<div class="card">

<h3>القسم</h3>

<p style="margin-top:10px;">
{{ student.department if student else 'غير محدد' }}
</p>

</div>

</div>

<div class="section-title">
<h2>نتائج الاختبارات</h2>
</div>

<div class="table-wrap">

<table>

<tr>
<th>الاختبار</th>
<th>النتيجة</th>
<th>النسبة</th>
</tr>

{% for r in results %}

<tr>

<td>{{ r.title or 'اختبار' }}</td>

<td>
{{ r.score }} / {{ r.total }}
</td>

<td>
{% if r.total %}
{{ ((r.score / r.total) * 100)|round|int }}%
{% else %}
0%
{% endif %}
</td>

</tr>

{% else %}

<tr>
<td colspan="3">
لا توجد نتائج بعد.
</td>
</tr>

{% endfor %}

</table>

</div>
"""

    return render_page(
        "حسابي",
        content,
        name=name,
        student=student,
        attendance_count=attendance_count,
        results=results
    )


# =========================================================
# NOTIFICATIONS
# =========================================================

@app.route("/notifications")
def notifications():

    conn = db()

    rows = conn.execute("""
        SELECT * FROM announcements
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    content = """

<div class="hero">

<h1>
<i class="fa-solid fa-bell"></i>
الإعلانات والتنبيهات
</h1>

</div>

{% for row in rows %}

<div class="notice">

<h3>{{ row.title }}</h3>

<p style="margin:8px 0;">
{{ row.content }}
</p>

<small>
{{ row.created_at[:16] }}
</small>

</div>

{% else %}

<div class="card">
لا توجد إعلانات حالياً.
</div>

{% endfor %}
"""

    return render_page(
        "الإعلانات",
        content,
        rows=rows
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        if password == ADMIN_PASSWORD:

            session["admin"] = True

            return redirect(
                url_for("admin")
            )

        flash("كلمة المرور غير صحيحة.")

    content = """

<div class="hero">

<h1>
<i class="fa-solid fa-lock"></i>
دخول الإدارة
</h1>

<p>
لوحة التحكم الخاصة بإدارة المنصة.
</p>

</div>

<div class="card">

<form method="POST">

<label>
كلمة مرور الإدارة
</label>

<input
class="input"
type="password"
name="password"
required>

<button class="btn" type="submit">
دخول
</button>

</form>

</div>
"""

    return render_page(
        "دخول الإدارة",
        content
    )


@app.route("/admin/logout")
def admin_logout():

    session.pop("admin", None)

    return redirect(
        url_for("home")
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
@admin_required
def admin():

    conn = db()

    students = conn.execute(
        "SELECT COUNT(*) AS c FROM students"
    ).fetchone()["c"]

    subjects_count = conn.execute(
        "SELECT COUNT(*) AS c FROM subjects"
    ).fetchone()["c"]

    lessons_count = conn.execute(
        "SELECT COUNT(*) AS c FROM lessons"
    ).fetchone()["c"]

    exams_count = conn.execute(
        "SELECT COUNT(*) AS c FROM exams"
    ).fetchone()["c"]

    conn.close()

    content = """

<div class="hero">

<h1>
<i class="fa-solid fa-gauge-high"></i>
لوحة تحكم المنصة
</h1>

<p>
إدارة المحتوى والطلاب والإعدادات.
</p>

</div>

<div class="grid">

<div class="card">
<h3>الطلاب</h3>
<div class="stat">{{ students }}</div>
</div>

<div class="card">
<h3>المواد</h3>
<div class="stat">{{ subjects_count }}</div>
</div>

<div class="card">
<h3>المحاضرات</h3>
<div class="stat">{{ lessons_count }}</div>
</div>

<div class="card">
<h3>الاختبارات</h3>
<div class="stat">{{ exams_count }}</div>
</div>

</div>

<div class="section-title">
<h2>إدارة المنصة</h2>
</div>

<div class="grid">

<a class="card" href="{{ url_for('admin_settings') }}">
<div class="card-icon">
<i class="fa-solid fa-palette"></i>
</div>
<h3>إعدادات المنصة</h3>
<p>الاسم والشعار والألوان.</p>
</a>

<a class="card" href="{{ url_for('admin_subjects') }}">
<div class="card-icon">
<i class="fa-solid fa-book"></i>
</div>
<h3>إدارة المواد</h3>
<p>إضافة وحذف المواد.</p>
</a>

<a class="card" href="{{ url_for('admin_lessons') }}">
<div class="card-icon">
<i class="fa-solid fa-video"></i>
</div>
<h3>المحاضرات</h3>
<p>إضافة روابط المحاضرات والملفات.</p>
</a>

<a class="card" href="{{ url_for('admin_exams') }}">
<div class="card-icon">
<i class="fa-solid fa-file-pen"></i>
</div>
<h3>الاختبارات</h3>
<p>إنشاء الاختبارات والأسئلة.</p>
</a>

<a class="card" href="{{ url_for('admin_announcements') }}">
<div class="card-icon">
<i class="fa-solid fa-bullhorn"></i>
</div>
<h3>الإعلانات</h3>
<p>إضافة إعلانات للطلاب.</p>
</a>

</div>
"""

    return render_page(
        "لوحة التحكم",
        content,
        students=students,
        subjects_count=subjects_count,
        lessons_count=lessons_count,
        exams_count=exams_count
    )


# =========================================================
# ADMIN SETTINGS
# =========================================================

@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():

    if request.method == "POST":

        site_name = request.form.get(
            "site_name",
            ""
        )

        logo = request.form.get(
            "logo",
            ""
        )

        primary = request.form.get(
            "primary_color",
            "#2563eb"
        )

        secondary = request.form.get(
            "secondary_color",
            "#0f172a"
        )

        accent = request.form.get(
            "accent_color",
            "#f59e0b"
        )

        welcome = request.form.get(
            "welcome",
            ""
        )

        notice = request.form.get(
            "notice",
            ""
        )

        conn = db()

        conn.execute("""
            UPDATE settings
            SET site_name=?,
                logo=?,
                primary_color=?,
                secondary_color=?,
                accent_color=?,
                welcome=?,
                notice=?
            WHERE id=1
        """, (
            site_name,
            logo,
            primary,
            secondary,
            accent,
            welcome,
            notice
        ))

        conn.commit()
        conn.close()

        flash("تم حفظ الإعدادات.")

        return redirect(
            url_for("admin_settings")
        )

    s = settings()

    content = """

<div class="hero">

<h1>إعدادات المنصة</h1>

<p>
غيّر اسم المنصة والشعار والألوان.
</p>

</div>

<div class="card">

<form method="POST">

<label>اسم المنصة</label>

<input class="input"
name="site_name"
value="{{ s.site_name }}">

<label>رابط الشعار</label>

<input class="input"
name="logo"
value="{{ s.logo }}"
placeholder="https://...">

<label>اللون الأساسي</label>

<input class="input"
type="color"
name="primary_color"
value="{{ s.primary_color }}">

<label>لون القائمة</label>

<input class="input"
type="color"
name="secondary_color"
value="{{ s.secondary_color }}">

<label>اللون المميز</label>

<input class="input"
type="color"
name="accent_color"
value="{{ s.accent_color }}">

<label>رسالة الترحيب</label>

<input class="input"
name="welcome"
value="{{ s.welcome }}">

<label>الإعلان الرئيسي</label>

<textarea
name="notice">{{ s.notice }}</textarea>

<button class="btn" type="submit">
<i class="fa-solid fa-save"></i>
حفظ الإعدادات
</button>

</form>

</div>
"""

    return render_page(
        "إعدادات المنصة",
        content,
        s=s
    )


# =========================================================
# ADMIN SUBJECTS
# =========================================================

@app.route("/admin/subjects", methods=["GET", "POST"])
@admin_required
def admin_subjects():

    conn = db()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        )

        icon = request.form.get(
            "icon",
            "fa-book"
        )

        if name:

            conn.execute("""
                INSERT INTO subjects
                (name,description,icon)
                VALUES(?,?,?)
            """, (
                name,
                description,
                icon
            ))

            conn.commit()

            flash("تمت إضافة المادة.")

    rows = conn.execute("""
        SELECT * FROM subjects
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    content = """

<div class="hero">

<h1>إدارة المواد</h1>

</div>

<div class="card">

<form method="POST">

<label>اسم المادة</label>

<input class="input"
name="name"
required>

<label>الوصف</label>

<input class="input"
name="description">

<label>أيقونة Font Awesome</label>

<input class="input"
name="icon"
value="fa-book">

<button class="btn">
إضافة المادة
</button>

</form>

</div>

<div class="section-title">
<h2>المواد الحالية</h2>
</div>

{% for row in rows %}

<div class="card" style="margin-bottom:12px;">

<h3>
<i class="fa-solid {{ row.icon }}"></i>
{{ row.name }}
</h3>

<p>
{{ row.description }}
</p>

<a class="btn btn-danger"
href="{{ url_for('delete_subject',subject_id=row.id) }}"
onclick="return confirm('حذف المادة؟')">
حذف
</a>

</div>

{% endfor %}
"""

    return render_page(
        "إدارة المواد",
        content,
        rows=rows
    )


@app.route("/admin/subjects/delete/<int:subject_id>")
@admin_required
def delete_subject(subject_id):

    conn = db()

    conn.execute(
        "DELETE FROM lessons WHERE subject_id=?",
        (subject_id,)
    )

    conn.execute(
        "DELETE FROM subjects WHERE id=?",
        (subject_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin_subjects")
    )


# =========================================================
# ADMIN LESSONS
# =========================================================

@app.route("/admin/lessons", methods=["GET", "POST"])
@admin_required
def admin_lessons():

    conn = db()

    if request.method == "POST":

        subject_id = request.form.get(
            "subject_id"
        )

        title = request.form.get(
            "title",
            ""
        )

        description = request.form.get(
            "description",
            ""
        )

        video_url = request.form.get(
            "video_url",
            ""
        )

        file_url = request.form.get(
            "file_url",
            ""
        )

        lesson_number = request.form.get(
            "lesson_number",
            1
        )

        conn.execute("""
            INSERT INTO lessons
            (
                subject_id,
                title,
                description,
                video_url,
                file_url,
                lesson_number,
                created_at
            )
            VALUES(?,?,?,?,?,?,?)
        """, (
            subject_id,
            title,
            description,
            video_url,
            file_url,
            lesson_number,
            datetime.now().isoformat()
        ))

        conn.commit()

        flash("تمت إضافة المحاضرة.")

    subjects_rows = conn.execute("""
        SELECT * FROM subjects
        ORDER BY name
    """).fetchall()

    lessons = conn.execute("""
        SELECT
            lessons.*,
            subjects.name AS subject_name
        FROM lessons
        LEFT JOIN subjects
        ON subjects.id=lessons.subject_id
        ORDER BY lessons.id DESC
    """).fetchall()

    conn.close()

    content = """

<div class="hero">

<h1>إدارة المحاضرات</h1>

</div>

<div class="card">

<form method="POST">

<label>المادة</label>

<select class="input"
name="subject_id"
required>

{% for subject in subjects_rows %}

<option value="{{ subject.id }}">
{{ subject.name }}
</option>

{% endfor %}

</select>

<label>عنوان المحاضرة</label>

<input class="input"
name="title"
required>

<label>الوصف</label>

<textarea
name="description"></textarea>

<label>رابط الفيديو</label>

<input class="input"
name="video_url"
placeholder="رابط YouTube أو الفيديو">

<label>رابط الملف</label>

<input class="input"
name="file_url"
placeholder="رابط PDF أو ملف">

<label>رقم المحاضرة</label>

<input class="input"
type="number"
name="lesson_number"
value="1">

<button class="btn">
<i class="fa-solid fa-plus"></i>
إضافة المحاضرة
</button>

</form>

</div>

<div class="section-title">
<h2>المحاضرات الحالية</h2>
</div>

{% for lesson in lessons %}

<div class="card" style="margin-bottom:12px;">

<h3>
{{ lesson.title }}
</h3>

<p>
المادة:
{{ lesson.subject_name }}
</p>

<p>
رقم المحاضرة:
{{ lesson.lesson_number }}
</p>

<a class="btn btn-danger"
href="{{ url_for('delete_lesson',lesson_id=lesson.id) }}"
onclick="return confirm('حذف المحاضرة؟')">
حذف
</a>

</div>

{% endfor %}
"""

    return render_page(
        "إدارة المحاضرات",
        content,
        subjects_rows=subjects_rows,
        lessons=lessons
    )


@app.route("/admin/lessons/delete/<int:lesson_id>")
@admin_required
def delete_lesson(lesson_id):

    conn = db()

    conn.execute(
        "DELETE FROM lessons WHERE id=?",
        (lesson_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin_lessons")
    )


# =========================================================
# ADMIN EXAMS
# =========================================================

@app.route("/admin/exams", methods=["GET", "POST"])
@admin_required
def admin_exams():

    conn = db()

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        )

        subject = request.form.get(
            "subject",
            ""
        )

        duration = request.form.get(
            "duration",
            30
        )

        questions = request.form.get(
            "questions",
            ""
        )

        answers = request.form.get(
            "answers",
            ""
        )

        conn.execute("""
            INSERT INTO exams
            (
                title,
                subject,
                duration,
                questions,
                answers,
                created_at
            )
            VALUES(?,?,?,?,?,?)
        """, (
            title,
            subject,
            duration,
            questions,
            answers,
            datetime.now().isoformat()
        ))

        conn.commit()

        flash("تم إنشاء الاختبار.")

    rows = conn.execute("""
        SELECT * FROM exams
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    content = """

<div class="hero">

<h1>إدارة الاختبارات</h1>

<p>
كل سطر في خانة الأسئلة يمثل سؤالاً.
وكل سطر في خانة الإجابات يمثل الإجابة الصحيحة المقابلة.
</p>

</div>

<div class="card">

<form method="POST">

<label>عنوان الاختبار</label>

<input class="input"
name="title"
required>

<label>المادة</label>

<input class="input"
name="subject">

<label>مدة الاختبار بالدقائق</label>

<input class="input"
type="number"
name="duration"
value="30">

<label>الأسئلة</label>

<textarea
name="questions"
placeholder="السؤال الأول
السؤال الثاني
السؤال الثالث"></textarea>

<label>الإجابات الصحيحة</label>

<textarea
name="answers"
placeholder="الإجابة الأولى
الإجابة الثانية
الإجابة الثالثة"></textarea>

<button class="btn">
<i class="fa-solid fa-plus"></i>
إنشاء الاختبار
</button>

</form>

</div>

<div class="section-title">
<h2>الاختبارات الحالية</h2>
</div>

{% for row in rows %}

<div class="card" style="margin-bottom:12px;">

<h3>{{ row.title }}</h3>

<p>
المادة:
{{ row.subject }}
</p>

<a class="btn btn-danger"
href="{{ url_for('delete_exam',exam_id=row.id) }}"
onclick="return confirm('حذف الاختبار؟')">
حذف
</a>

</div>

{% endfor %}
"""

    return render_page(
        "إدارة الاختبارات",
        content,
        rows=rows
    )


@app.route("/admin/exams/delete/<int:exam_id>")
@admin_required
def delete_exam(exam_id):

    conn = db()

    conn.execute(
        "DELETE FROM exams WHERE id=?",
        (exam_id,)
    )

    conn.execute(
        "DELETE FROM results WHERE exam_id=?",
        (exam_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin_exams")
    )


# =========================================================
# ADMIN ANNOUNCEMENTS
# =========================================================

@app.route("/admin/announcements", methods=["GET", "POST"])
@admin_required
def admin_announcements():

    conn = db()

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        )

        content_text = request.form.get(
            "content",
            ""
        )

        conn.execute("""
            INSERT INTO announcements
            (title,content,created_at)
            VALUES(?,?,?)
        """, (
            title,
            content_text,
            datetime.now().isoformat()
        ))

        conn.commit()

        flash("تم نشر الإعلان.")

    rows = conn.execute("""
        SELECT * FROM announcements
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    content = """

<div class="hero">

<h1>إدارة الإعلانات</h1>

</div>

<div class="card">

<form method="POST">

<label>عنوان الإعلان</label>

<input class="input"
name="title"
required>

<label>محتوى الإعلان</label>

<textarea
name="content"
required></textarea>

<button class="btn">
<i class="fa-solid fa-bullhorn"></i>
نشر الإعلان
</button>

</form>

</div>

{% for row in rows %}

<div class="notice">

<h3>{{ row.title }}</h3>

<p style="margin:10px 0;">
{{ row.content }}
</p>

<a class="btn btn-danger"
href="{{ url_for('delete_announcement',announcement_id=row.id) }}"
onclick="return confirm('حذف الإعلان؟')">
حذف
</a>

</div>

{% endfor %}
"""

    return render_page(
        "إدارة الإعلانات",
        content,
        rows=rows
    )


@app.route("/admin/announcements/delete/<int:announcement_id>")
@admin_required
def delete_announcement(announcement_id):

    conn = db()

    conn.execute(
        "DELETE FROM announcements WHERE id=?",
        (announcement_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin_announcements")
    )


# =========================================================
# FILE UPLOAD
# =========================================================

@app.route("/uploads/<path:filename>")
def uploads(filename):

    return send_from_directory(
        UPLOAD_FOLDER,
        filename
    )


# =========================================================
# PWA
# =========================================================

@app.route("/manifest.webmanifest")
def manifest():

    s = settings()

    return jsonify({
        "name": s["site_name"],
        "short_name": "جامعة الأنبار",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f1f5f9",
        "theme_color": s["primary_color"],
        "lang": "ar",
        "dir": "rtl",
        "icons": []
    })


@app.route("/sw.js")
def service_worker():

    js = """
self.addEventListener("install", event => {
    self.skipWaiting();
});

self.addEventListener("activate", event => {
    self.clients.claim();
});

self.addEventListener("fetch", event => {
});
"""

    return (
        js,
        200,
        {
            "Content-Type":
            "application/javascript"
        }
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok",
        "platform": "University AI Platform",
        "gemini": bool(GEMINI_API_KEY)
    })


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
