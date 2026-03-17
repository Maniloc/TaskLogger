# TaskLogger

Веб-приложение для ежедневного учёта рабочих задач по проектам и формирования ежемесячных отчётов.

Стек: **Django 4.2** · **SQLite** · **Chart.js** · **Vanilla JS**

---

## Быстрый старт

```bash
git clone https://github.com/Maniloc/TaskLogger.git
cd TaskLogger

python -m venv venv
source venv/bin/activate        # Linux / Mac
venv\Scripts\activate           # Windows

pip install -r requirements.txt

cp .env.example .env            # заполните SECRET_KEY

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Откройте в браузере: **http://127.0.0.1:8000**

---

## Возможности

### Проекты и задачи
- Создание проектов с указанием инициатора и обоснования
- Задачи с полями: дата, описание, статус, часы, инициатор, обоснование
- Статусы: Выполнено / В работе / Запланировано / Отложено
- Умный ввод часов: `2.5` · `2,5` · `2ч30м` · `2:30`
- Быстрое добавление задачи из любой страницы (кнопка «+ задача» в навбаре)
- Фильтрация по тексту, месяцу, статусу
- Пагинация (25 задач на страницу)
- Редактирование проекта и отдельных задач

### Отчёты
- Группировка по проекту или по дате
- Просмотр в виде таблицы или текста
- Копирование текста одной кнопкой
- Экспорт в **Excel (.xlsx)** с форматированием и итогами

### Аналитика
- Динамика задач и часов по месяцам (последние 12 мес.)
- Активность по дням (последние 30 дней)
- Распределение задач по статусам (donut chart)
- Топ проектов по часам
- Все графики перерисовываются при смене темы

### Дашборд
- Статистика текущего месяца
- График активности за 14 дней
- Мини-диаграмма распределения часов по проектам
- Напоминание если не добавлялись задачи 2+ дней
- Онбординг для новых пользователей

### Личный кабинет
- ФИО (фамилия, имя, отчество), должность, отдел, email
- Имя-отчество и аватар с инициалами отображаются в навбаре
- Профиль создаётся автоматически при регистрации пользователя

### Интерфейс
- 6 тем: **4 тёмных** (Slate, Forest, Crimson, Neutral) и **2 светлых** (Paper, Warm)
- Переключатель тем в навбаре, выбор сохраняется в браузере
- Адаптивная вёрстка (мобильные устройства)
- Favicon

### Администрирование
- Вкладка **«панель»** в навбаре (только для суперпользователей)
- Список всех пользователей со статистикой
- Просмотр задач всех пользователей с фильтрами
- Детальная страница каждого пользователя

---

## Настройка (.env)

```env
DEBUG=True
SECRET_KEY=замените-на-длинную-случайную-строку
ALLOWED_HOSTS=localhost,127.0.0.1
TIME_ZONE=Asia/Almaty
```

---

## Деплой на сервер

```bash
# .env для продакшна
DEBUG=False
SECRET_KEY=длинный-случайный-ключ-50+-символов
ALLOWED_HOSTS=yourdomain.com

python manage.py collectstatic
pip install gunicorn
gunicorn tasktracker.wsgi:application --bind 0.0.0.0:8000
```

Рекомендуется Nginx как прокси перед gunicorn.

---

## Добавить пользователя

```bash
python manage.py createsuperuser
```

Или через Django Admin: `/admin` → Users → Add user.

---

## Структура проекта

```
TaskLogger/
├── projects/
│   ├── models.py        # Project, Task, UserProfile
│   ├── views.py         # все view-функции
│   ├── urls.py
│   ├── admin.py
│   ├── signals.py       # авто-создание профиля
│   ├── migrations/
│   ├── static/
│   │   └── projects/
│   │       └── favicon.ico
│   └── templates/
│       └── projects/
│           ├── base.html          # навбар, темы, quick-add
│           ├── index.html         # дашборд
│           ├── analytics.html     # аналитика с графиками
│           ├── project_detail.html
│           ├── report.html
│           ├── profile.html
│           ├── admin_panel.html
│           ├── admin_user_detail.html
│           ├── task_edit.html
│           ├── quick_add.html
│           └── login.html
├── tasktracker/
│   ├── settings.py
│   └── urls.py
├── .env.example
├── requirements.txt
└── manage.py
```
