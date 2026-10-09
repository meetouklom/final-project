# Deploy DormFix on PythonAnywhere

This guide uses the project's SQLite database for an initial deployment.
Back up the database and uploaded media regularly.

## 1. Upload and install the project

Create a GitHub repository and upload the project. Do not upload passwords,
email credentials, secret keys, local databases, or user uploads.

In a PythonAnywhere Bash console:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 2. Configure the web app

In the PythonAnywhere **Web** tab:

1. Create a new web app using **Manual configuration** and the Python version
   used by the virtual environment.
2. Set the virtualenv path to
   `/home/YOUR_USERNAME/YOUR_REPOSITORY/.venv`.
3. Configure the WSGI file:

```python
import os
import sys

project_home = '/home/YOUR_USERNAME/YOUR_REPOSITORY'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['DJANGO_SETTINGS_MODULE'] = 'dormrepair.settings'
os.environ['DJANGO_SECRET_KEY'] = 'replace-with-a-long-random-secret'
os.environ['DJANGO_DEBUG'] = 'False'
os.environ['DJANGO_ALLOWED_HOSTS'] = 'YOUR_USERNAME.pythonanywhere.com'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

4. Set static files:
   - URL: `/static/`
   - Directory: `/home/YOUR_USERNAME/YOUR_REPOSITORY/staticfiles`
5. Set media files:
   - URL: `/media/`
   - Directory: `/home/YOUR_USERNAME/YOUR_REPOSITORY/media`

## 3. Configure password-reset email

Set these environment variables in the WSGI environment or the hosting
provider's environment settings. Use the values supplied by your email
provider, and never commit SMTP credentials:

```text
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=your-provider-smtp-host
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_USE_TLS=True
DJANGO_EMAIL_HOST_USER=your-smtp-username
DJANGO_EMAIL_HOST_PASSWORD=your-smtp-app-password
DJANGO_DEFAULT_FROM_EMAIL=DormFix <no-reply@your-domain.example>
```

With `DJANGO_DEBUG=False`, SMTP is the default email backend. Verify that the
hosting provider permits outbound SMTP and send a test email before relying on
password reset. If SMTP is not configured correctly, the dashboard reports
that a reset email could not be sent.

Public registration is limited to resident accounts. Supervisors can assign
roles from the protected dashboard; trusted initial supervisors should be
created or assigned through Django Admin.

## 4. Reload and verify

Press **Reload** in the PythonAnywhere Web tab and open:

```text
https://YOUR_USERNAME.pythonanywhere.com/
```

## Updating the site

After pushing changes, update the deployment from the PythonAnywhere Bash
console:

```bash
cd ~/YOUR_REPOSITORY
git pull
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Then press **Reload** in the Web tab.
