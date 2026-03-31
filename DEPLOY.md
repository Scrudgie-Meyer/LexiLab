# lexilab — Deploy to Railway

## Крок 1 — Підготовка репозиторію

```bash
git init
git add .
git commit -m "initial commit"

# Створи репо на GitHub та запуш
git remote add origin https://github.com/YOUR_USERNAME/lexilab.git
git push -u origin main
```

---

## Крок 2 — Створення проєкту на Railway

1. Перейди на https://railway.app та увійди через GitHub
2. Натисни **New Project**
3. Обери **Deploy from GitHub repo**
4. Вибери репозиторій `lexilab`
5. Railway автоматично знайде `Dockerfile` і почне збірку

---

## Крок 3 — Додавання PostgreSQL

1. У проєкті натисни **+ New**
2. Обери **Database → Add PostgreSQL**
3. Railway автоматично створить БД і додасть змінну `DATABASE_URL`

> ⚠️ Railway дає `DATABASE_URL` у форматі `postgresql://...`
> Нам потрібен `postgresql+asyncpg://...`
> Це вирішується у наступному кроці.

---

## Крок 4 — Environment Variables

У Settings → Variables додай:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://USER:PASS@HOST:PORT/DB` ← замінити `postgresql://` на `postgresql+asyncpg://` |
| `ALLOWED_ORIGINS` | `https://YOUR_APP.up.railway.app` |
| `ENVIRONMENT` | `production` |

> Значення `USER`, `PASS`, `HOST`, `PORT`, `DB` знайдеш у розділі **PostgreSQL → Variables** свого Railway проєкту.

---

## Крок 5 — Деплой

Railway деплоїть автоматично після кожного `git push`.

Якщо потрібно задеплоїти вручну:
1. Railway Dashboard → твій сервіс
2. **Deployments → Redeploy**

---

## Крок 6 — Перевірка

Після деплою перейди на:

```
https://YOUR_APP.up.railway.app/          ← фронтенд
https://YOUR_APP.up.railway.app/health    ← {"status": "ok"}
https://YOUR_APP.up.railway.app/docs      ← Swagger UI
```

---

## Структура Railway проєкту

```
lexilab (Railway Project)
├── lexilab-api     ← твій FastAPI сервіс (з Dockerfile)
└── lexilab-db      ← PostgreSQL (Railway managed)
```

---

## Локальний запуск (для розробки)

```bash
# 1. Скопіюй .env.example → .env та заповни значення
cp .env.example .env

# 2. Запусти через Docker Compose
docker-compose up

# або без Docker:
pip install -r requirements.txt
uvicorn main:app --reload
```

Локальний фронтенд: відкрий `frontend/index.html` напряму в браузері.

---

## Оновлення після змін

```bash
git add .
git commit -m "your changes"
git push
# Railway автоматично перебудує та задеплоїть
```
