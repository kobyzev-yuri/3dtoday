"""
Утилиты для работы с разделами KB на основе структуры 3dtoday.ru
"""

# Основные разделы KB на основе структуры 3dtoday.ru
KB_SECTIONS = {
    "Техничка": {
        "priority": "high",
        "content_types": ["article", "technical"],
        "description": "Решение проблем 3D-печати, настройка оборудования",
        "keywords": ["stringing", "warping", "layer_separation", "bed_adhesion", 
                    "retraction", "calibration", "tuning"],
        "problem_types": ["stringing", "warping", "layer_separation", "bed_adhesion",
                         "overhang", "underextrusion", "overextrusion", "z_wobble",
                         "elephant_foot", "ghosting", "blobs", "gaps"]
    },
    "Оборудование": {
        "priority": "high",
        "content_types": ["documentation", "comparison", "technical"],
        "description": "Документация по принтерам, настройка оборудования",
        "keywords": ["Ender-3", "Anycubic", "Prusa", "Creality", "specifications",
                    "manual", "setup", "comparison"],
        "problem_types": []
    },
    "Расходные материалы": {
        "priority": "high",
        "content_types": ["article", "comparison", "technical"],
        "description": "Информация о материалах, их свойствах, настройках печати",
        "keywords": ["PLA", "PETG", "ABS", "TPU", "ASA", "PC", "temperature",
                    "bed_temp", "print_temp", "properties"],
        "problem_types": ["material_issues", "temperature", "adhesion"]
    },
    "Применение": {
        "priority": "medium",
        "content_types": ["article", "technical"],
        "description": "Примеры использования 3D-печати, практические кейсы",
        "keywords": ["application", "use case", "example", "industry", "production"],
        "problem_types": []
    },
    "3D-печать": {
        "priority": "medium",
        "content_types": ["article", "technical"],
        "description": "Общие вопросы по 3D-печати, основы, обучение",
        "keywords": ["basics", "tutorial", "guide", "FDM", "SLA", "SLS", "technology"],
        "problem_types": []
    },
    "Обзоры": {
        "priority": "low",
        "content_types": ["comparison", "article"],
        "description": "Обзоры оборудования, материалов, аксессуаров",
        "keywords": ["review", "overview", "comparison", "pros", "cons", "features"],
        "problem_types": []
    },
    "3D-моделирование": {
        "priority": "low",
        "content_types": ["article", "technical"],
        "description": "Создание и подготовка 3D-моделей",
        "keywords": ["modeling", "CAD", "slicing", "preparation"],
        "problem_types": []
    },
    "RepRap": {
        "priority": "low",
        "content_types": ["article", "documentation", "technical"],
        "description": "Информация о проекте RepRap",
        "keywords": ["RepRap", "open source", "DIY"],
        "problem_types": []
    }
}

# Приоритеты разделов для фильтрации
SECTION_PRIORITIES = {
    "high": ["Техничка", "Оборудование", "Расходные материалы"],
    "medium": ["Применение", "3D-печать"],
    "low": ["Обзоры", "3D-моделирование", "RepRap"]
}

# Типы проблем для раздела Техничка
PROBLEM_TYPES = [
    "stringing",
    "warping",
    "layer_separation",
    "bed_adhesion",
    "overhang",
    "underextrusion",
    "overextrusion",
    "z_wobble",
    "elephant_foot",
    "ghosting",
    "blobs",
    "gaps",
    "stringing_retraction",
    "temperature",
    "speed"
]

def get_section_info(section: str) -> dict:
    """Получить информацию о разделе"""
    return KB_SECTIONS.get(section, {
        "priority": "unknown",
        "content_types": [],
        "description": "Неизвестный раздел",
        "keywords": [],
        "problem_types": []
    })

def is_high_priority_section(section: str) -> bool:
    """Проверить, является ли раздел высокоприоритетным"""
    return section in SECTION_PRIORITIES.get("high", [])

def get_sections_by_priority(priority: str) -> list:
    """Получить разделы по приоритету"""
    return SECTION_PRIORITIES.get(priority, [])

def get_relevant_sections_for_problem(problem_type: str) -> list:
    """Получить релевантные разделы для типа проблемы"""
    relevant = []
    for section, info in KB_SECTIONS.items():
        if problem_type in info.get("problem_types", []):
            relevant.append(section)
    return relevant if relevant else ["Техничка"]  # По умолчанию Техничка



