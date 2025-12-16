# Источники изображений для KB

Список URL с изображениями дефектов 3D-печати и технической документацией для добавления в базу знаний.

## 🎯 Приоритетные источники (с картинками дефектов)

### 1. Simplify3D Print Quality Troubleshooting Guide
**Отличный источник с качественными изображениями дефектов**

- **Stringing/Oozing**: https://www.simplify3d.com/resources/print-quality-troubleshooting/stringing-or-oozing/
- **Warping**: https://www.simplify3d.com/resources/print-quality-troubleshooting/warping/
- **Layer Separation**: https://www.simplify3d.com/resources/print-quality-troubleshooting/layer-separation-and-splitting/
- **Under-Extrusion**: https://www.simplify3d.com/resources/print-quality-troubleshooting/under-extrusion/
- **Over-Extrusion**: https://www.simplify3d.com/resources/print-quality-troubleshooting/over-extrusion/
- **Not Sticking to Bed**: https://www.simplify3d.com/resources/print-quality-troubleshooting/not-sticking-to-the-bed/
- **Gaps in Top Layers**: https://www.simplify3d.com/resources/print-quality-troubleshooting/gaps-in-top-layers/
- **Overheating**: https://www.simplify3d.com/resources/print-quality-troubleshooting/overheating/
- **Layer Shifting**: https://www.simplify3d.com/resources/print-quality-troubleshooting/layer-shifting/
- **Grinding Filament**: https://www.simplify3d.com/resources/print-quality-troubleshooting/grinding-filament/
- **Lines on Side**: https://www.simplify3d.com/resources/print-quality-troubleshooting/lines-on-side-of-print/
- **Vibrations/Ringing**: https://www.simplify3d.com/resources/print-quality-troubleshooting/vibrations-and-ringing/
- **Gaps in Thin Walls**: https://www.simplify3d.com/resources/print-quality-troubleshooting/gaps-in-thin-walls/
- **Small Features Not Printed**: https://www.simplify3d.com/resources/print-quality-troubleshooting/small-features-not-printed/
- **Inconsistent Extrusion**: https://www.simplify3d.com/resources/print-quality-troubleshooting/inconsistent-extrusion/
- **Poor Surface Above Supports**: https://www.simplify3d.com/resources/print-quality-troubleshooting/poor-surface-above-supports/
- **Dimensional Accuracy**: https://www.simplify3d.com/resources/print-quality-troubleshooting/dimensional-accuracy/
- **Poor Bridging**: https://www.simplify3d.com/resources/print-quality-troubleshooting/poor-bridging/

**Главная страница**: https://www.simplify3d.com/support/print-quality-troubleshooting/

### 2. All3DP Troubleshooting Guides
**Хорошие руководства с изображениями**

- **Stringing**: https://all3dp.com/2/3d-print-stringing-how-to-fix-it/
- **Warping**: https://all3dp.com/2/3d-printing-warping-how-to-fix-it/
- **Layer Separation**: https://all3dp.com/2/3d-print-layer-separation-how-to-fix-it/
- **Bed Adhesion**: https://all3dp.com/2/3d-print-not-sticking-to-bed-how-to-fix-it/
- **Under-Extrusion**: https://all3dp.com/2/3d-printing-under-extrusion-how-to-fix-it/
- **Over-Extrusion**: https://all3dp.com/2/3d-printing-over-extrusion-how-to-fix-it/

### 3. MatterHackers Guides
**Технические статьи с изображениями**

- **Common 3D Printing Problems**: https://www.matterhackers.com/articles/common-3d-printing-problems-and-how-to-fix-them
- **Stringing Guide**: https://www.matterhackers.com/articles/3d-printing-stringing-guide

### 4. Prusa Knowledge Base
**Официальная документация Prusa с картинками**

- **Print Quality Guide**: https://help.prusa3d.com/article/print-quality-guide_1250
- **Stringing**: https://help.prusa3d.com/article/stringing-or-oozing_1256
- **Warping**: https://help.prusa3d.com/article/warping_1257
- **Layer Separation**: https://help.prusa3d.com/article/layer-separation-and-splitting_1258

### 5. 3Dtoday.ru (русскоязычные статьи)
**Нужно найти конкретные статьи с картинками**

- Раздел "Техничка": https://3dtoday.ru/blogs/tech/
- Раздел "Вопросы и ответы": https://3dtoday.ru/questions
- Блоги пользователей: https://3dtoday.ru/blogs/

**Рекомендуется искать статьи с тегами:**
- stringing, сопли, ниточки
- warping, деформация, отслоение
- layer separation, расслоение слоев
- bed adhesion, адгезия к столу

### 6. MakerBot Troubleshooting
**Руководства с изображениями**

- **Troubleshooting Guide**: https://www.makerbot.com/learn/troubleshooting/
- **Print Quality Issues**: https://www.makerbot.com/learn/troubleshooting/print-quality-issues/

### 7. Ultimaker Support
**Техническая документация**

- **Print Quality Troubleshooting**: https://support.ultimaker.com/hc/en-us/articles/360011962619-Print-quality-troubleshooting-guide

## 📸 Типы изображений для индексации

### Приоритет 1: Дефекты печати
- Stringing (сопли, ниточки)
- Warping (деформация, отслоение углов)
- Layer separation (расслоение слоев)
- Bed adhesion problems (проблемы с адгезией)
- Over/under extrusion (пере/недоэкструзия)

### Приоритет 2: Технические схемы
- Схемы настройки retraction
- Диаграммы температурных режимов
- Схемы калибровки принтера
- Иллюстрации настроек слайсера

### Приоритет 3: Примеры решений
- До/после исправления дефектов
- Примеры правильных настроек
- Сравнительные изображения

## 🔧 Как добавлять изображения в KB

### Метод 1: Через административный интерфейс
1. Откройте `frontend/admin_ui.py`
2. Выберите метод "По URL (через LLM)"
3. Вставьте URL статьи с изображениями
4. Система автоматически извлечет изображения и проиндексирует их

### Метод 2: Прямая индексация изображений
```python
from backend.app.services.article_indexer import get_article_indexer

indexer = get_article_indexer()

# Индексация изображения из URL
await indexer.index_image(
    image_data={
        "article_id": "stringing_example_001",
        "title": "Пример stringing на PLA",
        "problem_type": "stringing",
        "printer_models": ["Ender-3"],
        "materials": ["PLA"],
        "symptoms": ["ниточки", "сопли"]
    },
    image_path="https://example.com/stringing_image.jpg",
    generate_embedding=True
)
```

## 📋 План добавления

### Неделя 1: Основные дефекты
- [ ] Stringing (5-10 изображений)
- [ ] Warping (5-10 изображений)
- [ ] Layer separation (5-10 изображений)

### Неделя 2: Дополнительные дефекты
- [ ] Bed adhesion (3-5 изображений)
- [ ] Over/under extrusion (3-5 изображений)
- [ ] Layer shifting (3-5 изображений)

### Неделя 3: Технические схемы
- [ ] Схемы настройки (5-10 изображений)
- [ ] Диаграммы температур (3-5 изображений)

## ✅ Критерии качества изображений

**Хорошее изображение:**
- ✅ Четко виден дефект или решение
- ✅ Хорошее разрешение (минимум 800x600)
- ✅ Релевантно теме 3D-печати
- ✅ Есть описание или контекст

**Плохое изображение (не добавлять):**
- ❌ Размытое или низкого качества
- ❌ Не релевантно теме
- ❌ Нет контекста или описания

## 🔗 Полезные ресурсы

- **Reddit r/3Dprinting**: https://www.reddit.com/r/3Dprinting/ - много примеров дефектов
- **Thingiverse Troubleshooting**: https://www.thingiverse.com/groups/3d-printing/topic:1378
- **YouTube каналы**: Teaching Tech, CHEP, 3D Printing Nerd - видео с примерами дефектов

## 📝 Примечания

- Все изображения должны быть связаны со статьями или иметь метаданные
- Приоритет - изображения с четким описанием проблемы и решения
- Изображения индексируются в отдельную коллекцию `kb_3dtoday_images` в Qdrant
- Используются эмбеддинги OpenCLIP для семантического поиска по изображениям


