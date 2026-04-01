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

def close_topic_if_open(page, topic_element):
    try:
        # контейнер всей темы (li)
        container = topic_element.locator("xpath=ancestor::li")

        # ищем вложенный список (это и есть раскрытая тема)
        nested_list = container.locator("ul")

        is_open = nested_list.count() > 0

        if is_open:
            print("   [-] Тема открыта → закрываю")

            #  стрелка (ВАЖНО: именно кнопка с иконкой)
            toggle_btn = container.locator('button[data-testid^="NavigationList__ListItemIcon"]').first

            toggle_btn.click()
            page.wait_for_timeout(500)

            #  контроль: убеждаемся что закрылась
            page.wait_for_function("""
                (el) => el.querySelectorAll("ul").length === 0
            """, container)

            print("   [✓] Тема закрыта")

        else:
            print("   [✓] Тема уже закрыта")

    except Exception as e:
        print(f"   [!] Ошибка при закрытии темы: {e}")

class GoITScraper:
    def __init__(self, config: Config):
        self.cfg = config

    # КЛИК ПО СТРЕЛКЕ (toggle темы)
    def toggle_topic(self, topic):
        icon_btn = topic.locator(
            'xpath=.//button[contains(@data-testid, "NavigationList__ListItemIcon")]'
        ).first

        if icon_btn.count() > 0:
            icon_btn.click(force=True)
        else:
            topic.click(force=True)

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

            topics = page.locator(topic_selector)
            count = topics.count()

            items_data = []

            # ---  закрываем ВСЕ темы ---
            topic_selector = 'div[data-testid^="NavigationList__ListItemContent"]:not([data-testid*="_tab_"])'
            topics = page.locator(topic_selector)

            for i in range(topics.count()):
                topic = topics.nth(i)
                close_topic_if_open(page, topic)
            print('topics closed')

            # ---  основной цикл ---
            for i in range(count):
                topics = page.locator(topic_selector)  # обновляем DOM
                topic = topics.nth(i)

                try:
                    name = topic.inner_text().split("\n")[0].strip()
                    print(f"\n[Анализ {i+1}/{count}]: {name}")

                    topic.scroll_into_view_if_needed()

                    #  открываем тему
                    self.toggle_topic(topic)
                    page.wait_for_timeout(500)

                    # ищем ДЗ
                    hw_tab = page.locator(
                        'div[data-testid*="_tab_homework"]'
                    ).filter(has_text="Домашнє завдання").first

                    if hw_tab.count() == 0:
                        print("   [-] Нет ДЗ")
                        items_data.append({"topic": name, "homework": None})

                        # закрываем обратно
                        self.toggle_topic(topic)
                        continue

                    hw_tab.wait_for(state="visible", timeout=5000)

                    # переход в ДЗ
                    with page.expect_navigation(wait_until="networkidle"):
                        hw_tab.click()

                    # --- дедлайн ---
                    deadline_label = page.locator('span:has-text("Дедлайн")').first
                    deadline_label.wait_for(timeout=10000)

                    deadline_value = deadline_label.locator(
                        "xpath=following-sibling::span"
                    ).first

                    current_deadline = deadline_value.inner_text().strip()

                    print(f"   [✓] Дедлайн: {current_deadline}")

                    items_data.append({
                        "topic": name,
                        "homework": {
                            "deadline": current_deadline,
                            "hw_url": page.url
                        }
                    })

                    # закрываем тему обратно
                    topics = page.locator(topic_selector)
                    topic = topics.nth(i)

                    self.toggle_topic(topic)
                    page.wait_for_timeout(500)

                except Exception as e:
                    print(f"   [x] Ошибка: {e}")

                    if "homework" in page.url:
                        page.go_back()

                    items_data.append({"topic": name, "homework": None})
                    continue

            # --- сохранение ---
            os.makedirs("output", exist_ok=True)
            with open("output/goit_scrap.json", "w", encoding="utf-8") as f:
                json.dump(items_data, f, ensure_ascii=False, indent=2)

            browser.close()

if __name__ == "__main__":
    app_cfg = Config()
    scraper = GoITScraper(app_cfg)
    scraper.run()