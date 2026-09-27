# منصة جامعة الأنبار التعليمية - App Edition

نسخة تطبيقية Mobile-first مبنية بـ Flask + SQLite + Google Gemini.

تشمل: الحضور، حساب الطالب، ترجمة، تلخيص، خرائط ذهنية، امتحانات، نتائج، إعلانات، ولوحة إدارة لتغيير اسم التطبيق والشعار والألوان.

## Render
Build: `pip install -r requirements.txt`
Start: `gunicorn app:app`

Environment Variables:
- GEMINI_API_KEY
- GEMINI_MODEL=gemini-3.7-flash
- SECRET_KEY
- ADMIN_PASSWORD
- DATABASE_PATH=platform.db
- UPLOAD_FOLDER=uploads
