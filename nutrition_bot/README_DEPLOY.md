# 🚀 Инструкция по бесплатному переносу бота на сервер 24/7

Ваш бот полностью упакован и готов к запуску в облаке. В проект уже добавлены:
* `Dockerfile` (сборка контейнера)
* `render.yaml` (автонастройка Render.com)
* `Procfile` (для платформ Render / Railway)
* `web_server.py` + веб-интерфейс (`web/`)

Ниже 2 самых простых и 100% бесплатных варианта размещения без банковских карт.

---

## 🏆 Вариант 1 (Рекомендуемый): Render.com
Бесплатный облачный хостинг, идеален для Telegram Web App, так как дает бесплатный **HTTPS-адрес**.

### Шаги (занимает 3 минуты):
1. **Зарегистрируйтесь бесплатно** на сайте [render.com](https://render.com) (через кнопку *Sign in with GitHub* или по Email). Банковская карта **не требуется**.
2. Создайте репозиторий на [github.com](https://github.com) и загрузите туда содержимое папки `nutrition_bot` (или распакованный `nutrition_bot_deploy.zip`).
3. В панели Render нажмите кнопку **New +** ➔ **Web Service**.
4. Выберите ваш репозиторий с ботом.
5. Заполните параметры:
   * **Name:** `afzal-telegram-bot`
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `python bot.py`
   * **Instance Type:** `Free` ($0/mo)
6. В разделе **Environment Variables** добавьте 2 переменные:
   * `BOT_TOKEN` = `<YOUR_TELEGRAM_BOT_TOKEN>`
   * `GEMINI_API_KEY` = `<YOUR_GEMINI_API_KEY>`
   * `WEB_APP_URL` = ваш URL на Render (например: `https://afzal-telegram-bot.onrender.com`)
7. Нажмите **Deploy Web Service**!
   Через 1-2 минуты бот заработает в облаке 24/7, и вы сможете выключить свой компьютер!

---

## ⚡️ Вариант 2 (Вообще без Git): Hugging Face Spaces
Самый легкий способ, файлы можно перетащить прямо мышкой в браузере.

1. Зарегистрируйтесь бесплатно на [huggingface.co](https://huggingface.co).
2. Нажмите **New Space**:
   * **Space name:** `afzal-nutrition-bot`
   * **Space SDK:** выберите **Docker** (Blank)
   * **Space hardware:** **Free CPU** (бесплатно навсегда)
3. Откройте вкладку **Files** ➔ **Add file** ➔ **Upload files** и перетащите все файлы из папки `nutrition_bot`.
4. В разделе **Settings** ➔ **Variables and secrets** добавьте секреты:
   * `BOT_TOKEN`: `<YOUR_TELEGRAM_BOT_TOKEN>`
   * `GEMINI_API_KEY`: `<YOUR_GEMINI_API_KEY>`
5. Нажмите сохранить — контейнер соберется сам и бот будет работать круглосуточно!

