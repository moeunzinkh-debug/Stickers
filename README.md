# Telegram Sticker Bot — Cloudflare Worker + Render

Telegram → Cloudflare Worker → Render → Telegram API។ Worker ពិនិត្យ webhook secret ហើយបញ្ជូន update ទៅ Render។ Render រត់ Python, Pillow និង ffmpeg ដើម្បីកែច្នៃ sticker។ មិនត្រូវការ Cloudflare Containers ទេ។

## 1. Deploy Render

បង្កើត Web Service ពី repository នេះដោយប្រើ `render.yaml` / Docker។ កំណត់ environment variables នៅ Render៖

- `TELEGRAM_BOT_TOKEN`: token ពី BotFather។
- `TELEGRAM_WEBHOOK_SECRET`: តម្លៃចៃដន្យផ្ទាល់ខ្លួន (១–២៥៦ តួអក្សរ មានតែ `A-Z`, `a-z`, `0-9`, `_`, `-`)។ ត្រូវប្រើតម្លៃដូចគ្នានៅ Worker និង Telegram។
- `PORT`: `8000` (កំណត់រួចក្នុង `render.yaml`)។

ចម្លង URL របស់ Render ដូចជា `https://your-service.onrender.com`។ បើ service ចាស់មាន `WEBHOOK_URL` ដែលចង្អុលទៅ Render សូមលុប variable នោះចេញ ហើយ redeploy ដើម្បីកុំឱ្យវាកំណត់ webhook ទៅ Render វិញ។

## 2. Deploy Cloudflare Worker

ត្រូវការ Node.js និង Cloudflare account៖

```sh
npm ci
npx wrangler login
npx wrangler secret put RENDER_ORIGIN
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET
npm run deploy
```

នៅ prompt ទីមួយ បញ្ចូល Render URL ដោយគ្មាន path ឬ slash បន្ថែម។ នៅ prompt ទីពីរ បញ្ចូល secret ដូចនៅ Render។ ចម្លង URL `https://...workers.dev` ពីលទ្ធផល deploy។ Worker មិនត្រូវការ bot token ទេ។

## 3. ភ្ជាប់ Telegram webhook

ដំណើរការក្នុង terminal (កុំចែករំលែក token ឬ secret)៖

```sh
read -r -s -p 'Bot token: ' BOT_TOKEN; echo
read -r -s -p 'Webhook secret: ' WEBHOOK_SECRET; echo
read -r -p 'Worker URL (https://...workers.dev): ' WORKER_URL
curl -sS -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
  --data-urlencode "url=${WORKER_URL%/}/webhook" \
  --data-urlencode "secret_token=${WEBHOOK_SECRET}" \
  --data-urlencode 'max_connections=1'
unset BOT_TOKEN WEBHOOK_SECRET WORKER_URL
```

ពិនិត្យថាលទ្ធផលមាន `"ok":true` រួចផ្ញើ `/start` ទៅ bot។ ប្រសិនបើប្តូរ secret ត្រូវធ្វើបច្ចុប្បន្នភាពនៅ Render និង Worker ហើយចុះឈ្មោះ webhook ម្តងទៀត។ ទំព័រ `/` ពិនិត្យតែ Worker; Render `/` ពិនិត្យ server ប៉ុណ្ណោះ។

## កម្រិត

Render free service អាចដេកពេលគ្មានសកម្មភាព និងចំណាយពេលចាប់ផ្តើមឡើងវិញ; Telegram អាច retry នៅពេល backend មិនទាន់ឆ្លើយ។ សន្ទនា និងបញ្ជី sticker sets រក្សាទុកតែក្នុង memory ដូចកូដដើម ដូច្នេះបាត់ពេល Render restart ឬ redeploy។ Sticker sets ដែលបានបង្កើតនៅ Telegram នៅតែមាន ប៉ុន្តែ `/list` និង `/add` មិនអាចរកឃើញបញ្ជីចាស់។ ត្រូវបន្ថែម persistent storage មុនប្រើ production។ ប្រើ Render instance តែមួយសម្រាប់ state ក្នុង memory។
