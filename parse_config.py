'''题目要求
编写函数 parse_config(file_path: str) -> dict，读取指定路径的配置文件。文件每行格式为 key=value。
规则：
1. 忽略空行和以 # 开头的注释行。
2. 去除键和值首尾的空白字符（如 " lr = 0.01 " 解析为 "lr": "0.01"）。
3. 若文件不存在，捕获异常并返回空字典 {}。
输入示例（文件内容）：
# 模型超参数
batch_size = 32
lr=0.001
epochs = 100
输出示例（返回的字典）：
{'batch_size': '32', 'lr': '0.001', 'epochs': '100'}'''
def parse_config(file_path: str) ->dict:
    config={}
    try:
        with open(file_path,'r',encoding='utf-8')as f:
            for line in f:
                #line.strip()剥掉字符串首尾的空白字符
                line=line.strip()
                if not line:
                    continue
                    #line.startswith（）判断字符串是不是以#开头，返回True或者False来执行是否去掉
                if line.startswith('#'):
                    continue
                    #line.split（）按照’=‘把字符串劈成列表，后边的数字是最多劈一次
                key,value=line.split('=',1)    #按第一个‘=’劈成两半一个当键一个当值
                config[key.strip()]=value.strip()           #去掉各自的空白，放入字典中，放入格式：字典名[键]=值
    except FileNotFoundError:
        return config
    return config
print(parse_config('test_config.txt'))
print(parse_config('根本不存在.txt'))