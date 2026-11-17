import copy
# 场景设定：defaults 是开发商样板房配置（默认值），
# override 是业主的改造清单（覆盖值）。
# 你的任务是交出一间"样板房底子+业主改动"的新房，且样板房本身一个螺丝钉都不许动。
def merge_config(defaults,override):
    if not isinstance(defaults,dict) or not isinstance(override,dict):
        raise TypeError("defaults和override都必须是dict类型")
    #深拷贝：里面东西全部复制一份
    result=copy.deepcopy(defaults)
    #items每次递出一对东西：相当于取出成员名＋新值
    for key,o_val in override.items():
        if key in result and isinstance(result[key],dict)and isinstance(o_val,dict):
            result[key]=merge_config(result[key],o_val)
        else:
            result[key]=copy.deepcopy(o_val)
    return result