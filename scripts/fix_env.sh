#!/bin/bash
# fix_env.sh

echo "🔧 اصلاح دسترسی به متغیرهای .env..."

# 1. خواندن متغیرها از .env
source .env

# 2. جایگزینی در فایل Nginx
echo "📝 جایگزینی متغیرها در Nginx..."
sed -i "s/\${DOMAIN}/$DOMAIN/g" nginx/conf.d/odoo.conf

# 3. جایگزینی در فایل Odoo
echo "📝 جایگزینی متغیرها در Odoo..."
sed -i "s/db_password = .*/db_password = $POSTGRES_PASSWORD/" odoo/config/odoo.conf

# 4. ری‌استارت سرویس‌ها
echo "🔄 ری‌استارت سرویس‌ها..."
docker-compose down
docker-compose up -d

# 5. بررسی وضعیت
echo "✅ بررسی وضعیت کانتینرها..."
sleep 10
docker-compose ps

echo "🎉 انجام شد! اکنون می‌توانید به Odoo دسترسی داشته باشید:"
echo "http://$DOMAIN:8069"