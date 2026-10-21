import json
#raw_text:str:参数注解；->tuple[str,bool]返回值注解，声明该函数返回一个元组，第一个是str，第二个是bool值
def parse_sse_stream(raw_text:str)->tuple[str,bool]:
    parts=[]                            #装每一段content碎片
    finished=False                      #信号灯：默认没读完
    for line in raw_text.splitlines():  #整段文本按照换行切成一行一行
        line=line.strip()
        if line.startswith('data: '):   #只认data开头的行
            payload=line[6:]            #剥掉前6个字符：’data： ‘
        else:
            continue
        if payload=='[DONE]':           #先拦结束标记，因为DONE不是合法JSON，json.loads会直接抛异常
            finished=True
            break
        data=json.loads(payload)
        parts.append(data['content'])       #取出这一段进parts
    return ''.join(parts),finished      #碎片无缝拼成整句，连信号灯一起返回
#验收
t1 = (': keep-alive\ndata: '
      '{"content": "深蹲"}\n\ndata: '
      '{"content": "3组"}\ndata: '
      '[DONE]\n')
assert parse_sse_stream(t1) == ('深蹲3组', True)

assert parse_sse_stream('') == ('', False)

t3 = 'data: {"content": "卧推"}\n'
assert parse_sse_stream(t3) == ('卧推', False)

print('全部通过')
