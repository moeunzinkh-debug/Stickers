export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/' && request.method === 'GET') {
      return new Response('Sticker Bot Worker is running');
    }
    if (url.pathname !== '/webhook' || request.method !== 'POST') {
      return new Response('Not found', { status: 404 });
    }
    if (!env.RENDER_ORIGIN || !env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response('Worker is not configured', { status: 503 });
    }
    if (request.headers.get('X-Telegram-Bot-Api-Secret-Token') !== env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response('Unauthorized', { status: 401 });
    }
    let backend;
    try {
      backend = new URL(env.RENDER_ORIGIN);
      if (backend.protocol !== 'https:' || backend.username || backend.password || backend.pathname !== '/' || backend.search || backend.hash) throw new Error('invalid origin');
    } catch {
      return new Response('Invalid Render origin', { status: 503 });
    }
    backend.pathname = '/webhook';
    try {
      return await fetch(backend.toString(), {
        method: 'POST',
        headers: {
          'Content-Type': request.headers.get('Content-Type') || 'application/json',
          'X-Telegram-Bot-Api-Secret-Token': env.TELEGRAM_WEBHOOK_SECRET,
        },
        body: request.body,
        redirect: 'manual',
      });
    } catch (error) {
      console.error('Render backend unavailable:', error);
      return new Response('Render backend unavailable', { status: 502 });
    }
  },
};
