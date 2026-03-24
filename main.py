import os
import json
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
load_dotenv()

class Config:
    USER = os.environ.get("LGN", "")
    PASS = os.environ.get("PSW", "")
    PAGE = os.environ.get("PAGE", "")
    TARGET_PAGE = os.environ.get("TARGET_PAGE", "")


class GoITScraper:
    def __init__(self, config: Config):
        self.cfg = config

    def run(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={"width": 1600, "height": 900})
            page = context.new_page()

            # 1. Авторизация
            page.goto(self.cfg.PAGE)
            page.fill('input[name="email"]', self.cfg.USER)
            page.fill('input[name="password"]', self.cfg.PASS)
            page.click('button[type="submit"]')
            page.wait_for_timeout(3000)

            # 2. Переход на страницу курса
            page.goto(self.cfg.TARGET_PAGE)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            items_data = []
            # Селектор тем (родительских модулей)
            # Идеальный селектор: берет только заголовки тем, игнорируя вложенные вкладки
            items_selector = 'ul[open] > li > div[data-testid^="NavigationList__ListItemContent"]:not([data-testid*="_tab_"])'
            
            page.wait_for_selector(items_selector)
            count = page.locator(items_selector).count()
            print(f"Найдено чистых тем: {count}")

            for i in range(count):
                # 1. Свежий поиск темы
                items = page.locator(items_selector)
                current_topic = items.nth(i)
                topic_name = current_topic.inner_text().split('\n')[0].strip()
                print(f"\n[Анализ]: {topic_name}")

                # 2. Раскрываем тему
                current_topic.click()
                page.wait_for_timeout(1000)

                # 3. ИЩЕМ КНОПКУ ДЗ (она находится в одном из следующих <li>)
                # Мы ищем элемент с текстом "Домашнє завдання", который ВИДИМ сейчас
                # После клика по теме нужная кнопка становится visible=True
                hw_tab = page.locator('div[data-testid*="homework"]').filter(has_text="Домашнє завдання")

                # Проверяем именно видимость первого попавшегося элемента
                if hw_tab.first.is_visible():
                    print(f"   [+] Перехожу в ДЗ...")
                    
                    # 1. Кликаем
                    hw_tab.first.click()
                    
                    # 2. Ждем сетевой тишины
                    page.wait_for_load_state("networkidle")

                    # 3. КРИТИЧЕСКИЙ МОМЕНТ: 
                    # Ждем, пока в DOM появится дедлайн, и даем ПРИНУДИТЕЛЬНУЮ паузу.
                    # SPA часто меняет URL раньше, чем перерисовывает текст.
                    page.wait_for_timeout(2500) # Увеличили до 2.5 сек для гарантии

                    info = {
                        "status": "Не определено",
                        "deadline": "Не указан",
                        "hw_url": page.url
                    }

                    # 4. Сбор данных
                    try:
                        # Статус
                        status_loc = page.locator('p[class*="next-"]:has-text("Завдання")').first
                        if status_loc.count() > 0:
                            info["status"] = status_el = status_loc.inner_text().strip()

                        # Дедлайн
                        deadline_row = page.locator('span:has-text("Дедлайн")').locator("xpath=./following-sibling::span").first
                        # Ждем, чтобы текст дедлайна вообще появился
                        deadline_row.wait_for(state="visible", timeout=5000)
                        info["deadline"] = deadline_row.inner_text().strip()
                        
                        print(f"   [S] Записано для этой темы: {info['deadline']}")
                    except Exception as e:
                        print(f"   [!] Ошибка парсинга: {e}")

                    items_data.append({"topic": topic_name, "homework": info})

                    # 5. Возврат назад
                    page.go_back()
                    page.wait_for_load_state("networkidle")
                    # Ждем, пока список тем снова станет видимым
                    page.wait_for_selector(items_selector, timeout=10000)
                    
                    # Сворачиваем тему (находим заново)
                    page.locator(items_selector).nth(i).click()
                    page.wait_for_timeout(1000) # Пауза перед следующей итерацией

            os.makedirs("output", exist_ok=True)
            with open("output/goit_scrap.json", "w", encoding="utf-8") as f:
                json.dump(items_data, f, ensure_ascii=False, indent=2)

            browser.close()
            # page.pause()  для просмотра сайта после выполнения кода 

if __name__ == "__main__":
    app_cfg = Config()
    scraper = GoITScraper(app_cfg)
    scraper.run()