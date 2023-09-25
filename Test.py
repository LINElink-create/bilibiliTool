import re
import codecs

# 打开 JavaScript 文件并以 GBK 编码格式读取内容
with codecs.open('json/崩坏3第一偶像爱酱_27534330/primary/full.json', 'r', encoding='gbk', errors='ignore') as file:
    js_code = file.read()

# 使用正则表达式查找匹配的字符串
pattern = r'BV\w{10}'  # 匹配以 "BV" 开头后跟10位字符的模式
matches = re.findall(pattern, js_code)

match_count = len(matches)
# 打印匹配的字符串

print(match_count)
