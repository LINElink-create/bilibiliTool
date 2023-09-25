import json

# 打开 JSON 文件并读取内容
with open('json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# 在 JSON 对象中查找特定键（例如 'url'）
search_key = 'url'
found_strings = []

for item in data:
    if search_key in item:
        found_strings.append(item[search_key])

# 打印找到的字符串值
for string_value in found_strings:
    print(string_value)

