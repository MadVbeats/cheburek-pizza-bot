# Бот «Чебурек и Пицца»

Telegram-бот для точки общепита: меню с ценами, корзина и предзаказ,
который приходит в личку рабочего Telegram-аккаунта.

## Стек

- Python 3.11+
- aiogram 3
- Меню — в `menu.json` (правится без изменения кода)
- Корзина хранится в памяти процесса

## Установка

```powershell
cd D:\cheburek-pizza-bot
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Заполните `.env`:

```
BOT_TOKEN=токен от @BotFather
ADMIN_ID=ваш числовой Telegram ID
PROXY_URL=
```

Свой ID можно узнать у бота [@userinfobot](https://t.me/userinfobot).

`PROXY_URL` нужен, если сервер находится там, где api.telegram.org
заблокирован. Поддерживаются HTTP и SOCKS5, например:
`PROXY_URL=socks5://user:pass@host:port`.

## Запуск

```powershell
.venv\Scripts\python bot.py
```

## Как работает

1. `/start` → главное меню: 🍽 Меню, 🛒 Корзина, ✅ Оформить заказ, ℹ️ Инфо
2. В меню — категории (чебуреки, пицца, напитки, соусы) → позиции с ценами → «Добавить в корзину»
3. В корзине — ➖/➕ по позициям, очистка, оформление
4. Оформление: имя → телефон → самовывоз/доставка (+адрес) → подтверждение
5. Готовый предзаказ (состав, сумма, контакты клиента) отправляется сообщением на `ADMIN_ID`
6. Клиент получает номер заказа

## Интеграция с iiko

Заказы автоматически создаются в iiko через облако iikoTransport
(api-ru.iiko.services) как предзаказы самовывоза; тип получения и адрес
передаются в комментарии к заказу — оператор видит их в iikoDelivery.

Подключение:

1. В личном кабинете iiko.Business включите доступ по API
   (Настройки → API / Транспортный модуль) и скопируйте **apiLogin**
2. Заполните в `.env`:

```
IIKO_API_LOGIN=ключ из личного кабинета
IIKO_ORGANIZATION_ID=
IIKO_TERMINAL_GROUP_ID=
```

3. Узнайте ID организации и точки продаж:

```powershell
.venv\Scripts\python scripts\iiko_check.py
```

Скрипт выведет список организаций и terminalGroups — впишите нужные ID
в `.env` (если оставить пустыми, возьмутся первые найденные).

4. Свяжите позиции бота с номенклатурой iiko: запустите скрипт из п.3 —
   он сохранит `iiko_nomenclature.json` со всеми позициями и их UUID.
   Пропишите эти UUID в `menu.json` полем `"iiko_id"`:

```json
{ "name": "Чебурек классический", "price": 160, "iiko_id": "uuid-из-iiko" }
```

Без `iiko_id` позиция продаётся через бота, но заказ в iiko не уйдёт
(в уведомлении админа будет пометка 🔴 с именами проблемных позиций).

## Mini App (как у Яндекс Еды)

Бот теперь умеет работать как **Telegram Mini App** — меню с картинками прямо внутри Телеги.

### Что добавлено
- `server.py` — FastAPI бэкенд: `GET /api/menu` и `POST /api/order` + раздача фронта из `webapp/`
- `webapp/` — фронт (HTML/CSS/JS + `telegram-web-app.js`), корзина, оформление
- Кнопка `🥟 Открыть приложение` в `bot.py`/`keyboards.py` (появляется если задан `WEBAPP_URL`)

### Запуск Mini App локально
```powershell
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python server.py  # или: uvicorn server:app --host 0.0.0.0 --port 8000 --reload
# открой http://localhost:8000 — увидишь приложение
# бот в другом терминале:
.venv\Scripts\python bot.py
```

### Деплой
1. Залей `webapp/` + `server.py` на хостинг с HTTPS (Render, Railway, VPS, Vercel и т.д.)
2. В `.env` пропиши `WEBAPP_URL=https://твой-домен.com`
3. Перезапусти бота — в `/start` появится кнопка **Открыть приложение**
4. В @BotFather → твой бот → Menu Button → укажи тот же URL (опционально)

Без `WEBAPP_URL` бот работает как раньше (классические кнопки).

## Настройка под себя

- Цены и позиции: `menu.json` (можно менять на работающем боте — применяется после перезапуска)
- Адрес, часы работы, телефон: `INFO_TEXT` и `ADDRESS_TEXT` в `handlers/user.py`
- Дизайн Mini App: `webapp/style.css` и `webapp/index.html`
