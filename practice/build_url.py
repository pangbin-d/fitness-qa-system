def build_url(base_url,*paths,**kwargs):
    path_part='/'.join(paths)
    query_part='&'.join(f"{k}={v}"for k,v in kwargs.items())
    url=base_url
    if paths:
        url=url+'/'+path_part
    if kwargs:
        url=url+"?"+query_part
    return url

assert build_url('http://api.com', 'v1', 'models', format='json', limit=10) == 'http://api.com/v1/models?format=json&limit=10'
assert build_url('http://api.com', 'v1') == 'http://api.com/v1'
assert build_url('http://api.com') == 'http://api.com'
print('通过 ✅')