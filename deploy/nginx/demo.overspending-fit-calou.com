# Host Nginx vhost for the public demo instance.
# Copy to /etc/nginx/sites-available/ and symlink to sites-enabled/.
#
# TLS: certbot --nginx -d demo.overspending-fit-calou.com

server {
    listen 80;
    server_name demo.overspending-fit-calou.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name demo.overspending-fit-calou.com;

    ssl_certificate     /etc/letsencrypt/live/demo.overspending-fit-calou.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/demo.overspending-fit-calou.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;

    # API — proxy to demo backend directly (strips /api prefix)
    location /api/ {
        proxy_pass         http://127.0.0.1:8001/;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   X-Forwarded-Prefix /api;
    }

    # Frontend — proxy to demo frontend container
    location / {
        proxy_pass         http://127.0.0.1:5174;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
