#一个词频统计函数
def count_tags(tags_list):
    #isinstance（变量，类型）属于内置函数，判断变量是不是这个类型，not取反“如果tags_list不是列表”
    if not isinstance(tags_list,list):
        #成立就扔出一个错误即raise
        raise TypeError("输入必须是列表")
    counts = {}                #相当于在循环外面建立一个空容器，进循环填充


    for tag in tags_list:
        counts[tag]=counts.get(tag,0)+1
    return counts


print(count_tags(['a','b','a']))
print(count_tags([]))
print(count_tags(None))