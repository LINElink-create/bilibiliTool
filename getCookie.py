from selenium import webdriver
import time
import json

# 填写webdriver的保存目录
driver = webdriver.Chrome()

# 记得写完整的url 包括http和https
driver.get('https://space.bilibili.com')

# 程序打开网页后20秒内 “手动登陆账户”
time.sleep(20)

with open('cookies.txt','w') as f:
    # 将cookies保存为json格式
    f.write(json.dumps(driver.get_cookies()))

driver.close()

# 首先清除由于浏览器打开已有的cookies
driver.delete_all_cookies()
