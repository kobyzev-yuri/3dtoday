#!/usr/bin/env python3
"""
Тест KB MCP Server
"""

import sys
import asyncio
from pathlib import Path

# Добавляем путь к модулям проекта
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_mcp_server():
    """Тест подключения к MCP серверу и вызова инструментов"""
    
    print("="*60)
    print("🧪 Тест KB MCP Server")
    print("="*60)
    
    # Параметры сервера
    server_params = StdioServerParameters(
        command="python3",
        args=[str(Path(__file__).parent / "kb_mcp_server.py")]
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Инициализация сессии
                print("\n1️⃣ Инициализация MCP сессии...")
                await session.initialize()
                print("✅ Сессия инициализирована")
                
                # Получение списка инструментов
                print("\n2️⃣ Получение списка инструментов...")
                tools_result = await session.list_tools()
                tools = tools_result.tools
                print(f"✅ Найдено инструментов: {len(tools)}")
                for tool in tools:
                    print(f"   • {tool.name}: {tool.description[:60]}...")
                
                # Тест 1: get_kb_statistics
                print("\n3️⃣ Тест: get_kb_statistics()")
                try:
                    stats_result = await session.call_tool("get_kb_statistics", {})
                    print(f"✅ Статистика получена:")
                    if stats_result.content:
                        for content in stats_result.content:
                            if hasattr(content, 'text'):
                                print(f"   {content.text}")
                            else:
                                print(f"   {content}")
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
                
                # Тест 2: search_kb_articles
                print("\n4️⃣ Тест: search_kb_articles('stringing')")
                try:
                    search_result = await session.call_tool(
                        "search_kb_articles",
                        {
                            "query": "stringing",
                            "limit": 3
                        }
                    )
                    print(f"✅ Поиск выполнен")
                    if search_result.content:
                        for content in search_result.content:
                            if hasattr(content, 'text'):
                                print(f"   {content.text[:200]}...")
                            else:
                                print(f"   {content}")
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
                    import traceback
                    traceback.print_exc()
                
                print("\n" + "="*60)
                print("✅ Тест завершен")
                print("="*60)
                
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_mcp_server())
    sys.exit(0 if success else 1)



