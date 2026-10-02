#->是pyth固定语法，叫做返回值标注箭头，意思是函数吐出来的东西是后面这个类型。只是声明一个字典类型，不是真的字典，所以不用大括号
def build_api_config(model_name:str,temperature:float=0.7,max_tokens:int=100,top_p:float=1.0)->dict:
    if temperature<0.0 or temperature>2.0:
        raise ValueError("temperature必须在0.0到2.0之间！")
    return{
        "model":model_name,
        "temperature":temperature,
        "max_tokens":max_tokens,
        'top_p':top_p
    }
if __name__=='__main__':
   print(build_api_config('gpt-4',0.5))
   print(build_api_config('gpt4'))
   print(build_api_config('gpt4',3.0))