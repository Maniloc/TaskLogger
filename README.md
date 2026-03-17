# TaskTracker v2

Система учёта задач по проектам с генерацией отчётов, тёмными темами и экспортом в Excel.

## Быстрый старт

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # заполнить SECRET_KEY
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Темы интерфейса
Переключатель тем прямо в навигации — 4 тёмных темы:
- **Dark Slate** — синяя акцентная (по умолчанию)
- **Dark Forest** — зелёная акцентная
- **Dark Crimson** — красная акцентная
- **Dark Neutral** — нейтральная серая

## Новое в v2
- Поле `status` у задачи: запланировано / в работе / выполнено / отложено
- Поле `hours` (число) вместо строки — суммируется в отчётах
- Экспорт отчёта в Excel (.xlsx) с форматированием
- Дашборд с аналитикой текущего месяца
- Пагинация задач (25 на страницу)
- Фильтр по статусу
- Безопасные настройки через .env
- whitenoise для раздачи статики

## Деплой
```bash
# .env
DEBUG=False
SECRET_KEY=ваш-длинный-случайный-ключ
ALLOWED_HOSTS=yourdomain.com

python manage.py collectstatic
gunicorn tasktracker.wsgi:application --bind 0.0.0.0:8000
```
