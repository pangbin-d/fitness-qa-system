#字典的嵌套访问与类型判断
#  题目要求
# 实现一个函数 safe_get(data, keys, default=None)，通过给定的键列表逐层访问嵌套字典 data。
# 如果任意一层键不存在或当前层不是字典，则返回 default 的值。
# 示例输入：
# data = {'model': {'config': {'temp': 0.7}}}
# keys = ['model', 'config', 'temp']
# 示例输出：
# 0.7
#
# 示例输入：
# keys = ['model', 'config', 'top_p']
# 示例输出：
# None
#
# 示例输入：
# keys = ['model', 'version'] (假设 version 的值是字符串而非字典)
# 示例输出：
# None
#
#  验收标准
#    1. 能正确提取多层嵌套字典中的目标值。
#    2. 当路径中任意键缺失时，能正确返回 default 参数指定的默认值。
#    3. 当路径中某一层级的值不是字典（如字符串或列表）时，不会抛出 TypeError，而是安全返回默认值。
#本质就是别人写的代码不一定规矩，需要假设错误情况出现。
def safe_get(data,keys,default=None):
    current=data
    for key in keys:
        if not isinstance(current,dict):
            return default
        if key not in current:
            return default
        current=current[key]
    return current
data = {
    'model': {
        'config': {'temp': 0.7},
        'version': 'deepseek-v3'
    }
}
#assert“断言”相当于提前说结果是这样，是就true，不是的话就报错
# 1. 正常取到深层值
assert safe_get(data, ['model', 'config', 'temp']) == 0.7

# 2. 深层键不存在 → None
assert safe_get(data, ['model', 'config', 'top_p']) is None

# 3. 中间层是字符串，还想继续往下钻 → None（不能抛 TypeError）
assert safe_get(data, ['model', 'version', 'patch']) is None

# 4. 自定义 default 生效
assert safe_get(data, ['model', 'price'], default=0) == 0

# 5. 第一层键就不存在
assert safe_get(data, ['usage', 'total']) is None

# 6. 起点本身就不是字典
assert safe_get('不是字典', ['a']) is None

# 7. 空 keys：原样返回 data
assert safe_get(data, []) == data

print('全部通过 ✅')