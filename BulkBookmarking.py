from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
from time import sleep

options = webdriver.ChromeOptions()
user_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/117.0.0.0 Safari/537.36')
options.add_argument(f'user-agent={user_agent}')

# 创建一个Chrome WebDriver
driver = webdriver.Chrome()

# 打开目标网页
driver.get('https://www.bilibili.com/video/BV1R4411b7so')  # 用实际的网页URL替换

with open('cookies.txt', 'r') as f:
    # 使用json读取cookies 注意读取的是文件 所以用load而不是loads
    cookies_list = json.load(f)

# 方法1 将expiry类型变为int
# for cookie in cookies_list:
#     # 并不是所有cookie都含有expiry 所以要用dict的get方法来获取
#     if isinstance(cookie.get('expiry'), float):
#         cookie['expiry'] = int(cookie['expiry'])
#     driver.add_cookie(cookie)

# 方法2删除该字段
for cookie in cookies_list:
    # 该字段有问题所以删除就可以
    if 'expiry' in cookie:
        del cookie['expiry']
    driver.add_cookie(cookie)

sleep(6)
btn = driver.find_element(By.XPATH, '/html/body/div[2]/div[2]/div[1]/div[3]/div[1]/div[3]/div/*[name()="svg"]')

sleep(1.5)
btn.click()
sleep(5)
# 一个叫test的收藏夹
btn = driver.find_element(By.XPATH, "//div/div[@class='group-list']/ul/li[2]/label/input")
print(btn.is_displayed())
print(btn.is_selected())
# btn.click()
driver.execute_script("arguments[0].click();", btn)
sleep(1.5)
btn = driver.find_element(By.XPATH, "//div/div[@class='bottom']/button")
btn.click()
sleep(1.5)

# 关闭浏览器
driver.quit()
