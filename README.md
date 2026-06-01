# yt2tg — YouTube → Telegram Archiver

Archiva canales y playlists de YouTube y los envía a Telegram, del más antiguo al más nuevo. Soporta envío opcional de comentarios como archivo TXT.

**Bot:** [@yt2tg_a_bot](https://t.me/yt2tg_a_bot)

---

## Características

- Archiva el backlog completo de un canal/playlist (oldest → newest)
- Detecta y envía videos nuevos automáticamente (polling cada 15-20 min)
- Soporte para `@handles`, URLs de canales y playlists
- Comentarios opcionales por video en TXT (con replies, likes, fechas, badges de creator)
- Múltiples canales y múltiples chats/grupos independientes
- Estado persistente en PostgreSQL (sobrevive reinicios)
- CI/CD con GitHub Actions

---

## Comandos

| Comando | Descripción |
|---|---|
| `/add @canal` | Registrar canal (solo videos) |
| `/add @canal --comments` | Canal + todos los comentarios de cada video |
| `/add @canal --comments -500` | Canal + top 500 comentarios (más nuevos primero) |
| `/add https://youtube.com/playlist?list=xxx` | Playlist |
| `/stop <@canal\|URL>` | Pausar envío |
| `/resume <@canal\|URL>` | Reanudar desde donde quedó |
| `/restart <@canal\|URL>` | Reenviar todo desde el principio (con confirmación) |
| `/remove <@canal\|URL>` | Dejar de monitorear |
| `/list` | Canales activos con estadísticas |
| `/status` | Estado del bot |
| `/help` | Ayuda |

---

## Formato de mensajes

```
🎬 Título del video
📺 Nombre del canal
📅 2025-05-30
👁️ 1.2M  ❤️ 45K  💬 3.2K
💬 Descripción...
🔗 https://youtube.com/watch?v=...
```

### Formato del TXT de comentarios

```
TÍTULO:    Video Title
CANAL:     Channel Name
URL:       https://youtube.com/watch?v=...
FECHA:     2025-05-30
COMENTARIOS: 1234 totales / mostrando 500
========================================================================

[1] @usuario · 👍 1.2K · 2025-05-30 14:32
    Gran video!

  ↳ [1.1] @otro · 👍 23 · 2025-05-30 15:00
         Totalmente de acuerdo

[2] @creador 📺 · 👍 500 · 2025-05-30 16:00 ❤️
    ¡Gracias por el apoyo!
```

---

## Despliegue

```bash
git clone https://github.com/seminarioA/yt2tg.git
cd yt2tg
cp .env.example .env
nano .env
mkdir -p data/metadata data/temp data/comments
docker-compose up -d --build
```

### Variables de entorno

| Variable | Descripción |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot |
| `POSTGRES_PASSWORD` | Contraseña PostgreSQL |
| `DATA_DIR` | Directorio de datos (default: `/data`) |
| `POLL_INTERVAL_MIN` | Mínimo minutos entre polls (default: `15`) |
| `POLL_INTERVAL_MAX` | Máximo minutos entre polls (default: `20`) |
| `COOKIES_FILE` | (Opcional) Cookies de YouTube en formato Netscape |
