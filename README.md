## Структура

```
Sites/
  main.py         — точка входа FastAPI
  app/            — бэкенд (конфиг, детектор, отчёты, история)
  static/         — frontend (index.html)
  uploads/        — загруженные файлы (создаётся при запуске)
  outputs/        — экспорт отчётов (создаётся при запуске)
  data/           — SQLite БД истории (создаётся при запуске)
```

Модели (`models/best.pt`, `models/weapon_yolov8.pt`) находятся в корне проекта.

## Установка зависимостей

```powershell
pip install -r requirements.txt
```

## Запуск

Из корня проекта:

```powershell
..\venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Откройте http://localhost:8000
