# Развёртывание CodeHogwarts на maks.my

Приложение живёт в `/opt/codehog`, слушает `127.0.0.1:8791`, наружу его отдаёт nginx.

## Что меняется на сервере

| Файл | Что делаем |
|---|---|
| `/opt/codehog/` | новый каталог приложения |
| `/etc/systemd/system/codehog.service` | новый сервис |
| `/etc/nginx/snippets/codehog.location` | новый сниппет |
| `/etc/nginx/sites-available/maks-ai-agents.conf` | заменяется только блок `location /` |

Остальные сервисы не трогаются: `/kedr/`, `/idealsteklo/`, `/diving/`, `/dive-new/`,
`/domaizkedra/`, `/dji-agro/` и `/api/` платформы на 8787 работают как работали.
Прежняя главная (статика «Дом из кедра») остаётся доступной по `/domaizkedra/`.

## Обновление кода

```bash
bash deploy/deploy.sh          # заливает текущую папку и перезапускает сервис
```

## Откат

```bash
ssh root@50.114.115.182
cp /etc/nginx/sites-available/maks-ai-agents.conf.bak-codehog-* \
   /etc/nginx/sites-available/maks-ai-agents.conf
nginx -t && systemctl reload nginx
systemctl stop codehog && systemctl disable codehog
```
