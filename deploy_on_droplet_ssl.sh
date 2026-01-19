#!/usr/bin/env bash
set -e

# -------------------------
# 1. Update system
# -------------------------
apt update && apt upgrade -y
apt install -y python3-pip python3-venv python3-dev libpq-dev postgresql postgresql-contrib nginx git curl ufw software-properties-common

# -------------------------
# 2. Setup PostgreSQL
# -------------------------
sudo -i -u postgres psql << EOF
CREATE DATABASE mydb;
CREATE USER myuser WITH PASSWORD 'mypassword';
ALTER ROLE myuser SET client_encoding TO 'utf8';
ALTER ROLE myuser SET default_transaction_isolation TO 'read committed';
ALTER ROLE myuser SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE mydb TO myuser;
\q
EOF

# -------------------------
# 3. Clone Django project
# -------------------------
cd /opt
git clone https://github.com/yourusername/yourproject.git
cd yourproject

# -------------------------
# 4. Setup virtualenv & install requirements
# -------------------------
python3 -m venv venv
source venv/bin/activate

if [ -f requirements.txt ]; then
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# If you have a custom requirements.sh script
if [ -f requirements.sh ]; then
    bash requirements.sh
fi

# -------------------------
# 5. Collect static files & migrations
# -------------------------
export DJANGO_SETTINGS_MODULE=yourproject.settings
python manage.py migrate
python manage.py collectstatic --noinput

# -------------------------
# 6. Gunicorn systemd service
# -------------------------
cat > /etc/systemd/system/gunicorn.service << EOL
[Unit]
Description=gunicorn daemon for Django project
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/opt/yourproject
ExecStart=/opt/yourproject/venv/bin/gunicorn --access-logfile - --workers 3 --bind unix:/opt/yourproject/gunicorn.sock yourproject.wsgi:application

[Install]
WantedBy=multi-user.target
EOL

systemctl daemon-reload
systemctl enable gunicorn
systemctl start gunicorn

# -------------------------
# 7. Configure Nginx
# -------------------------
cat > /etc/nginx/sites-available/yourproject << EOL
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
        root /opt/yourproject;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/opt/yourproject/gunicorn.sock;
    }
}
EOL

ln -s /etc/nginx/sites-available/yourproject /etc/nginx/sites-enabled || true
nginx -t
systemctl restart nginx

# -------------------------
# 8. Setup firewall
# -------------------------
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# -------------------------
# 9. Install Certbot & enable SSL
# -------------------------
add-apt-repository universe -y
apt install -y certbot python3-certbot-nginx

certbot --nginx --non-interactive --agree-tos -m your-email@example.com -d yourdomain.com -d www.yourdomain.com

# -------------------------
# 10. Reload Nginx
# -------------------------
systemctl reload nginx

echo "✅ Deployment with SSL complete!"
echo "Visit https://yourdomain.com to see your app."
