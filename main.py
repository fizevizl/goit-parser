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

            # --- 1. Авторизация ---
            page.goto(self.cfg.PAGE)
            page.fill('input[name="email"]', self.cfg.USER)
            page.fill('input[name="password"]', self.cfg.PASS)
            page.click('button[type="submit"]')
            page.wait_for_timeout(3000)

            # --- 2. Переход на курс ---
            page.goto(self.cfg.TARGET_PAGE)
            page.wait_for_load_state("networkidle")

            topic_selector = 'div[data-testid^="NavigationList__ListItemContent"]:not([data-testid*="_tab_"])'
            page.wait_for_selector(topic_selector)

            raw_topics = page.locator(topic_selector).all_inner_texts()
            topic_names = [t.split('\n')[0].strip() for t in raw_topics if t.strip()]

            items_data = []

            print("[!] Подготовка: закрываю все открытые темы...")

            topic_selector = 'div[data-testid^="NavigationList__ListItemContent"]:not([data-testid*="_tab_"])'
            topics = page.locator(topic_selector)

            count = topics.count()

            for i in range(count):
                topic = topics.nth(i)
                
                try:
                    # если внутри есть ДЗ — значит тема открыта
                    container = topic.locator("xpath=ancestor::li")
                    is_open = container.locator('div[data-testid*="_tab_homework"]').count() > 0

                    if is_open:
                        topic.click()
                        page.wait_for_timeout(500)

                except Exception:
                    continue

            print("[✓] Все темы приведены к закрытому состоянию")

            for i, name in enumerate(topic_names):
                print(f"\n[Анализ {i+1}/{len(topic_names)}]: {name}")

                try:
                    # найти тему
                    topic_header = page.locator(topic_selector).filter(has_text=name).first
                    topic_header.scroll_into_view_if_needed()
                    topic_header.wait_for(state="visible", timeout=5000)
                    topic_header.click()

                    # ищем кнопку ДЗ
                    hw_tab = page.locator('div[data-testid*="_tab_homework"]').filter(has_text="Домашнє завдання").first

                    if hw_tab.count() == 0:
                        print("   [-] В теме нет ДЗ")
                        items_data.append({"topic": name, "homework": None})
                        continue

                    hw_tab.wait_for(state="visible", timeout=5000)

                    # --- КЛИК ---
                    with page.expect_navigation(wait_until="networkidle"):
                        hw_tab.click()

                    # --- ЖДЕМ ДЕДЛАЙН ---
                    deadline_label = page.locator('span:has-text("Дедлайн")').first
                    deadline_label.wait_for(timeout=10000)

                    deadline_value = deadline_label.locator('xpath=following-sibling::span').first
                    deadline_value.wait_for(timeout=10000)

                    current_deadline = deadline_value.inner_text().strip()

                    print(f"   [✓] Дедлайн: {current_deadline}")

                    items_data.append({
                        "topic": name,
                        "homework": {
                            "deadline": current_deadline,
                            "hw_url": page.url
                        }
                    })

                    # --- НАЗАД ---
                    page.go_back()
                    page.wait_for_load_state("networkidle")

                    # важно: снова дождаться списка тем
                    page.wait_for_selector(topic_selector)

                    # закрываем тему
                    topic_header = page.locator(topic_selector).filter(has_text=name).first
                    if topic_header.is_visible():
                        topic_header.click()
                        page.wait_for_timeout(500)

                except Exception as e:
                    print(f"   [x] Ошибка: {e}")
                    if "homework" in page.url:
                        page.go_back()
                    items_data.append({"topic": name, "homework": None})
                    continue

            # --- СОХРАНЕНИЕ ---
            os.makedirs("output", exist_ok=True)
            with open("output/goit_scrap.json", "w", encoding="utf-8") as f:
                json.dump(items_data, f, ensure_ascii=False, indent=2)

            browser.close()


if __name__ == "__main__":
    app_cfg = Config()
    scraper = GoITScraper(app_cfg)
    scraper.run()