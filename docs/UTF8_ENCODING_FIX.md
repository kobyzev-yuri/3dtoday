# Исправление кодировки UTF-8 в JSON ответах

## 🔍 Проблема

В JSON ответах от FastAPI русский текст отображался в виде Unicode escape-последовательностей:

```json
{
  "description": "\u0423\u0432\u0435\u043b\u0438\u0447\u044c\u0442\u0435 retraction \u0434\u043e 6 \u043c\u043c"
}
```

Вместо правильного:
```json
{
  "description": "Увеличьте retraction до 6 мм"
}
```

## 🔧 Причина

FastAPI по умолчанию использует `JSONResponse`, который использует `json.dumps()` с `ensure_ascii=True` (по умолчанию). Это приводит к экранированию всех не-ASCII символов в виде `\uXXXX`.

## ✅ Решение

Создан кастомный `UnicodeJSONResponse`, который использует `ensure_ascii=False`:

```python
class UnicodeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,  # Ключевое изменение!
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")
```

И установлен как класс ответа по умолчанию:

```python
app.router.default_response_class = UnicodeJSONResponse
```

## 📋 Что было изменено

**Файл:** `backend/app/main.py`

1. Добавлен импорт `json` и `Any`
2. Создан класс `UnicodeJSONResponse`
3. Установлен как `default_response_class` для всего приложения

## 🧪 Проверка

После перезапуска FastAPI проверьте:

```bash
curl http://localhost:8000/api/kb/articles/test_stringing_pla_001 | python3 -m json.tool
```

Теперь русский текст должен отображаться правильно:

```json
{
  "solutions": [
    {
      "parameter": "retraction_length",
      "value": 6,
      "unit": "mm",
      "description": "Увеличьте retraction до 6 мм"
    }
  ]
}
```

## 🔄 Применение изменений

**Важно:** После изменения кода нужно перезапустить FastAPI:

```bash
# Остановите текущий процесс (Ctrl+C)
# Затем запустите снова:
./scripts/start_fastapi.sh
```

Или если запускали вручную:
```bash
cd backend && PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 Дополнительная информация

- [FastAPI JSONResponse documentation](https://fastapi.tiangolo.com/advanced/custom-response/#jsonresponse)
- [Python json.dumps ensure_ascii parameter](https://docs.python.org/3/library/json.html#json.dumps)

