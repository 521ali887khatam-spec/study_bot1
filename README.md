# study_bot1# --- Keep-alive server for Render ---
from aiohttp import web
import os

async def health(request):
    return web.Response(text="Bot is alive!")

app = web.Application()
app.router.add_get('/', health)

def run_keepalive():
    port = int(os.environ.get('PORT', 10000))
    web.run_app(app, host='0.0.0.0', port=port)

from threading import Thread
Thread(target=run_keepalive, daemon=True).start()
