# -*- coding: utf-8 -*-
import os
import time
import logging
import random
from os import path
from io import StringIO
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import shutil

logger = logging.getLogger()
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    "[%(asctime)s %(levelname)s] %(message)s", datefmt="%H:%M:%S"
)

console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

USERNAME = os.getenv("LINUXDO_USERNAME")
PASSWORD = os.getenv("LINUXDO_PASSWORD")
SCROLL_DURATION = int(os.getenv("SCROLL_DURATION", 0))
HOME_URL = os.getenv("HOME_URL", "https://linux.do/")
CONNECT_URL = os.getenv("CONNECT_URL", "https://connect.linux.do/")

browse_count = 0
connect_info = ""

missing_configs = []

if not USERNAME:
    missing_configs.append("USERNAME")
if not PASSWORD:
    missing_configs.append("PASSWORD")

if missing_configs:
    logging.error(f"缺少必要配置: {', '.join(missing_configs)}，请在环境变量中设置。")
    exit(1)


def load_send():
    cur_path = path.abspath(path.dirname(__file__))
    if path.exists(cur_path + "/notify.py"):
        try:
            from notify import send

            return send
        except ImportError:
            return False
    else:
        return False


class LinuxDoBrowser:
    def __init__(self) -> None:
        logging.info("启动 Selenium")

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")

        chromedriver_path = shutil.which("chromedriver")

        if not chromedriver_path:
            logging.error("chromedriver 未找到，请确保已安装并配置正确的路径。")
            exit(1)

        self.driver = webdriver.Chrome(
            service=Service(chromedriver_path), options=chrome_options
        )

        logging.info("导航到LINUX DO首页")
        self.driver.get(HOME_URL)
        logging.info("初始化完成")

    def simulate_typing(self, element, text, typing_speed=0.1, random_delay=True):
        for char in text:
            element.send_keys(char)
            if random_delay:
                time.sleep(typing_speed + random.uniform(0, 0.1))
            else:
                time.sleep(typing_speed)

    def login(self) -> bool:
        try:
            logging.info("--- 开始尝试登录 ---")

            login_button = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".login-button .d-button-label")
                )
            )
            login_button.click()

            username_field = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#login-account-name"))
            )
            self.simulate_typing(username_field, USERNAME)

            password_field = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "#login-account-password")
                )
            )
            self.simulate_typing(password_field, PASSWORD)

            submit_button = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#login-button"))
            )
            submit_button.click()

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#current-user"))
            )
            logging.info("登录成功")
            return True

        except Exception as e:
            error_message = self.driver.find_elements(
                By.CSS_SELECTOR, "#modal-alert.alert-error"
            )
            if error_message:
                logging.error("登录失败：用户名、电子邮件或密码不正确")
            else:
                logging.error(f"登录失败：{e}")
            return False

    def load_all_topics(self):
        end_time = time.time() + SCROLL_DURATION
        actions = ActionChains(self.driver)

        while time.time() < end_time:
            actions.scroll_by_amount(0, 500).perform()
            time.sleep(0.1)

        logging.info("页面滚动完成，已停止加载更多帖子")

    def click_topic(self):
        try:
            logging.info("--- 开始滚动页面加载更多帖子 ---")
            self.load_all_topics()
            topics = self.driver.find_elements(By.CSS_SELECTOR, "#list-area .title")
            total_topics = len(topics)
            logging.info(f"共找到 {total_topics} 个帖子")

            logging.info("--- 开始浏览帖子 ---")
            global browse_count

            for idx, topic in enumerate(topics):
                parent_element = topic.find_element(By.XPATH, "./ancestor::tr")

                is_pinned = parent_element.find_elements(
                    By.CSS_SELECTOR, ".topic-statuses .pinned"
                )

                if is_pinned:
                    logging.info(f"跳过置顶的帖子：{topic.text.strip()}")
                    continue
                article_title = topic.text.strip()
                logging.info(f"打开第 {idx + 1}/{len(topics)} 个帖子 ：{article_title}")
                article_url = topic.get_attribute("href")

                self.driver.execute_script("window.open('');")
                self.driver.switch_to.window(self.driver.window_handles[-1])

                try:
                    browse_start_time = time.time()
                    self.driver.get(article_url)
                    time.sleep(3)

                except Exception as e:
                    logging.warning(
                        f"打开帖子 ： {article_title} 时发生错误，跳过该帖子。错误信息: {e}"
                    )

                finally:
                    browse_count += 1
                    start_time = time.time()
                    scroll_duration = random.uniform(5, 10)
                    # screenshot_interval = 2  # 设置截图间隔时间，单位是秒
                    # screenshot_count = 0
                    try:
                        while time.time() - start_time < scroll_duration:
                            self.driver.execute_script(
                                "window.scrollBy(0, window.innerHeight);"
                            )

                            # screenshot_count += 1
                            # screenshot_filename = (
                            #     f"screenshot_{idx + 1}_{screenshot_count}.png"
                            # )
                            # self.driver.save_screenshot(screenshot_filename)
                            # logging.info(f"已保存截图: {screenshot_filename}")
                            # time.sleep(screenshot_interval)

                    except Exception as e:
                        logging.warning(f"在滚动过程中发生错误: {e}")
                        return False

                    browse_end_time = time.time()
                    total_browse_time = browse_end_time - browse_start_time
                    logging.info(f"浏览该帖子时间: {total_browse_time:.2f}秒")
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    logging.info(
                        f"已关闭第 {idx + 1}/{len(topics)} 个帖子 ： {article_title}"
                    )

        except Exception as e:
            logging.error(f"处理帖子时出错: {e}")

    def run(self):
        start_time = time.time()
        try:
            if not self.login():
                return
            self.click_topic()
            logging.info("🎉恭喜你，帖子浏览全部完成")
        except Exception as e:
            logging.error(f"运行过程中出错: {e}")
        finally:
            end_time = time.time()
            spend_time = int((end_time - start_time) // 60)
            self.print_connect_info()
            self.driver.quit()
            send = load_send()
            if callable(send):
                send(
                    "Linux.do浏览帖子",
                    f"本次共浏览{browse_count}个帖子\n共用时{spend_time}分钟\n{connect_info}",
                )
            else:
                print("\n加载通知服务失败")

    def print_connect_info(self):
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        logging.info("导航到LINUX DO Connect页面")
        self.driver.get(CONNECT_URL)

        global connect_info

        rows = self.driver.find_elements(By.CSS_SELECTOR, "table tr")

        info = []

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 3:
                project = cells[0].text.strip()
                current = cells[1].text.strip()
                requirement = cells[2].text.strip()
                info.append([project, current, requirement])

        column_widths = [24, 22, 16]

        def calculate_content_width(content):
            return sum(2 if ord(char) > 127 else 1 for char in content)

        def format_cell(content, width, alignment="left"):
            content_length = calculate_content_width(content)
            padding = width - content_length
            if padding > 0:
                if alignment == "left":
                    return content + " " * padding
                elif alignment == "right":
                    return " " * padding + content
                elif alignment == "center":
                    left_padding = padding // 2
                    right_padding = padding - left_padding
                    return " " * left_padding + content + " " * right_padding
            else:
                return content[:width]

        def build_row(cells):
            return "| " + " | ".join(cells) + " |"

        def build_separator():
            return "+" + "+".join(["-" * (width + 2) for width in column_widths]) + "+"

        formatted_info = [
            build_row(
                [
                    format_cell(row[0], column_widths[0]),
                    format_cell(row[1], column_widths[1], "center"),
                    format_cell(row[2], column_widths[2], "center"),
                ]
            )
            for row in info
        ]

        header = build_row(
            [
                format_cell("项目", column_widths[0]),
                format_cell("当前", column_widths[1], "center"),
                format_cell("要求", column_widths[2], "center"),
            ]
        )

        separator = build_separator()

        output = StringIO()
        output.write("在过去 💯 天内：\n")
        output.write(separator + "\n")
        output.write(header + "\n")
        output.write(separator.replace("-", "=") + "\n")
        output.write("\n".join(formatted_info) + "\n")
        output.write(separator + "\n")

        table_output = output.getvalue()
        output.close()

        print(table_output)

        connect_info = "\n在过去 💯 天内：\n" + "\n".join(
            [f"{row[0]}（{row[2]}）：{row[1]}" for row in info]
        )

        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[0])


if __name__ == "__main__":
    linuxdo_browser = LinuxDoBrowser()
    linuxdo_browser.run()
