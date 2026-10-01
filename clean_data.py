#用列表推导式清洗AI传感器脏数据
'''要求
编写函数 `clean_data(raw_data, threshold)` 对一维传感器数据进行清洗和特征变换。
输入：`raw_data` 为包含浮点数和 `None` 的列表，`threshold` 为最低有效阈值。
处理逻辑：
1. 剔除 `None` 值。
2. 剔除小于 `threshold` 的数值。
3. 对保留的有效数值进行平方操作（模拟非线性特征变换）'''
def clean_data(raw_data,threshold):
    #and有短路特性，左边n is not None不成立右边不会执行判断
    result=[n**2 for n in raw_data if n is not None and n>=threshold]
    return result
print(clean_data([1.5,None,3.0,-2.0],0.0))
print(clean_data([],0.0))
print(clean_data([None,-5.0],0.0))