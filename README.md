# Notes Manager

Менеджер заметок на Flet с поддержкой облачной синхронизации Supabase.

## Возможности

- Создание, редактирование и удаление заметок
- Поиск по заголовку, дате и содержанию
- Три режима хранения данных:
  - **SQLite** — локальная база данных (не требует интернета)
  - **Files** — JSON-файлы в папке `notes_data/` (не требует интернета)
  - **Облако (Supabase)** — облачная база PostgreSQL (синхронизация между устройствами)
- Запуск на Android через приложение Flet

## Установка

### Требования

- Python 3.10+
- Flet
- Supabase (для облачного режима)

### Установка зависимостей

```bash
pip install flet supabase

### Настройка облачной синхронизации (Supabase)
1.Зарегистрируйтесь на supabase.com
2.Создайте новый проект
3.В SQL Editor выполните скрипт:

CREATE TABLE notes (
    id BIGINT PRIMARY KEY,
    title TEXT,
    date TEXT,
    time TEXT,
    content TEXT
);

ALTER TABLE notes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public access" ON notes FOR ALL USING (true) WITH CHECK (true);

4.В Project Settings → API Keys скопируйте:

Project URL — https://xxxxx.supabase.co
publishable key

5.Скопируйте config_example.py → config.py и вставьте свои значения:

SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "ваш-ключ"

###Запуск

python notes_manager.py


###Запуск на Android

1.Установите приложение Flet из Google Play
2.Убедитесь, что телефон и компьютер в одной Wi-Fi сети
3.Запустите:

flet run --android notes_manager.py

4.Отсканируйте QR-код из терминала камерой телефона
