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
            items_selector = 'ul[open] > li > div[data-testid^="NavigationList__ListItemContent"]'
            
            page.wait_for_selector(items_selector)
            count = page.locator(items_selector).count()
            print(f"Найдено тем для анализа: {count}")

            for i in range(count):
                # Обновляем локаторы, чтобы избежать ошибки Stale Element
                items = page.locator(items_selector)
                topic = items.nth(i)
                
                topic_name = topic.inner_text().split('\n')[0].strip()
                print(f"\n[Тема]: {topic_name}")

                # Раскрываем тему
                topic.click()
                page.wait_for_timeout(1000)

                # Ищем кнопку "Домашнє завдання" по data-testid из вашего скриншота
                hw_button = topic.locator("xpath=./..").locator('div[data-testid="NavigationList__ListItemContent_tab_homework"]')

                if hw_button.count() > 0:
                    print(f"   [!] Найдено 'Домашнє завдання'.")
                    hw_button.first.click()
                    
                    # Ждем загрузки и отрисовки SPA
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(2500) 

                    info = {
                        "status": "Не определено",
                        "deadline": "Не указан",
                        "hw_url": page.url
                    }

                    try:
                        # Сбор статуса по классу со скриншота (p.next-m5589s)
                        status_locator = page.locator('p.next-m5589s')
                        if status_locator.count() > 0:
                            info["status"] = status_locator.first.inner_text().strip()

                        # Сбор дедлайна
                        deadline_label = page.locator('span:has-text("Дедлайн")')
                        if deadline_label.count() > 0:
                            # Извлекаем дату из соседнего span
                            time_val = deadline_label.locator("xpath=./following-sibling::span")
                            if time_val.count() > 0:
                                info["deadline"] = time_val.first.inner_text().strip()

                        print(f"   [S] Статус: {info['status']} | Дедлайн: {info['deadline']}")

                    except Exception as e:
                        print(f"   [!] Ошибка при чтении страницы: {e}")

                    items_data.append({
                        "topic": topic_name,
                        "homework": info
                    })

                    # Назад к списку тем
                    page.go_back()
                    page.wait_for_selector(items_selector, timeout=10000)
                else:
                    print(f"   [x] Поле ДЗ в этой теме отсутствует.")
                    items_data.append({
                        "topic": topic_name,
                        "homework": None
                    })

            # 3. Сохранение в JSON
            os.makedirs("output", exist_ok=True)
            with open("output/goit_scrap.json", "w", encoding="utf-8") as f:
                json.dump(items_data, f, ensure_ascii=False, indent=2)

            browser.close()
            # page.pause()  для просмотра сайта после выполнения кода 


if __name__ == "__main__":
    app_cfg = Config()
    scraper = GoITScraper(app_cfg)
    scraper.run()
