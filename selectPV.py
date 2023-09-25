import json
import codecs

# 打开 GBK 编码的 JSON 文件并读取内容
with codecs.open('json/崩坏3第一偶像爱酱_27534330/primary/full.json', 'r', encoding='utf-8', errors='ignore') as file:
    data = json.load(file)

# 筛选出不包含 "录像" 的条目
filtered_data = [item for item in data if "录像" not in json.dumps(item, ensure_ascii=False)]

# 将筛选后的数据保存回原始文件
with codecs.open('json/崩坏3第一偶像爱酱_27534330/primary/New.json', 'w', encoding='utf-8', errors='ignore') as file:
    json.dump(filtered_data, file, ensure_ascii=False, indent=4)
