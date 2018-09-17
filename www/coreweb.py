#!/usr/bin/env python3
#-*- coding:utf-8 -*-

__author__='hcyCoding'

#inspect模块用于收集python对象的信息，可以获取类或函数的参数的信息，源码，解析堆栈，对对象进行类型检查等
import asyncio,os,inspect,logging,functools
from urllib import parse
from aiohttp import web
from apis import APIError

#装饰器
def get(path):
    '''
      define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)  #把原始函数的__name__等属性赋值到warpper函数中
        def wrapper(*args,**kw):  #*args可变参数，传tuple，**kw关键字参数，传dict
            return func(*args,**kw)
        wrapper.__method__='GET'
        wrapper.__route__=path
        return wrapper
    return decorator

#装饰器
def post(path):
    '''
      define decorator @post('path)
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args,**kw):
            return func(*args,**kw)
        wrapper.__method__='POST'
        wrapper.__route__=path
        return wrapper
    return decorator

#获取没有默认值的命名关键字参数
def get_required_kw_args(fn):
    args=[]
    #inspect.signature(fn)获取对象fn的所有参数，返回值是inspect.Signature类型
    #parameters 将inspect.Signature类型转化成一个有序字典类型
    params=inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind==inspect.Parameter.KEYWORD_ONLY and param.default==inspect.Parameter.empty:  #KEYWORD_ONLY  命名关键字类型参数
            args.append(name)
    return tuple(args)

#获取命名关键字参数
def get_named_kw_args(fn):
    args=[]
    params=inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind==inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return args

#判断有没有命名关键字参数
def has_named_kw_args(fn):
    params=inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind==inspect.Parameter.KEYWORD_ONLY:
            return True

#判断有没有关键字参数
def has_var_kw_args(fn):
    params=inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind==inspect.Parameter.VAR_KEYWORD:  #VAR_KEYWORD  关键字类型参数
            return True

#判断是否有request参数，并且该参数是否为最后一个参数
def has_request_args(fn):
    sig=inspect.signature(fn)
    params=sig.parameters
    found=False
    for name,param in params.items():
        if name=='request':
            found=True
            continue
        #VAR_POSITIONAL  可变参数
        if found and (param.kind!=inspect.Parameter.VAR_POSITIONAL and param.kind!=inspect.Parameter.KEYWORD_ONLY and param.kind!=inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function:%s%s'(fn.__name__,str(sig)))
    return found

# 定义RequestHandler从视图函数中分析其需要接受的参数，从web.Request中获取必要的参数
# 调用视图函数，然后把结果转换为web.Response对象，符合aiohttp框架要求
class RequestHandler(object):
    def __init__(self,app,fn):
        self.app=app
        self.func=fn
        self._has_request_arg = has_request_args(fn)
        self._has_var_kw_arg = has_var_kw_args(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    async def __call__(self,request):
        kw=None
        #关键字参数  or  命名关键字参数  or  没有默认值的命名关键字参数
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            if request.method=='POST':
                if not request.content_type:
                    return web.HTTPBadRequest(text='msssing content_type')
                ct=request.content_type.lower()
                if ct.startswith('application/json'):
                    params=await request.json()
                    if not isinstance(params,dict):
                        return web.HTTPBadRequest(text='json body must be object')
                    kw=params
                elif ct.startswith('application/x-www-form-urlencode') or ct.startswith('application/form-data'):
                    params=await request.post()
                    kw=dict(**params)
                else:
                    return web.HTTPBadRequest(text='unsupported content-type:%s'%request.content_type)
            if request.method=='GET':
                qs=request.query_string
                if qs:
                    kw=dict()
                    for k,v in parse.parse_qs(qs,True).items():
                        kw[k]=v[0]
        if kw is None:
            kw=dict(**request.match_info)
        else:
            #如果只有命名关键字参数
            if not self._has_var_kw_arg and self._named_kw_args:
                #remove all unamed kw
                copy=dict()
                #只保留命名关键字参数
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name]=kw[name]
                kw=copy
            #check named arg
            for k,v in request.match_info.items():
                if k in kw:
                    logging.warning('duplicate arg name in named arg and kw args:%s'%k)
                kw[k]=v
        if self._has_request_arg:
            kw['request']=request
        #如果存在无默认值的命名关键字参数
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:  #如果没有传入必须的参数值，报错
                    return web.HTTPBadRequest(text='missing argument:%s'%name)
        logging.info('call with args:%s'%str(kw))
        try:
            r=await self.func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error,data=e.data,message=e.message)

#添加静态文件，如image，js，css
def add_static(app):
    path=os.path.join(os.path.dirname(os.path.abspath(__file__)),'static')
    app.router.add_static('/static/',path)
    logging.info('add static %s=>%s'%('/static/',path))

#注册一个视图函数
def add_route(app,fn):
    method=getattr(fn,'__method__',None)
    path=getattr(fn,'__route__',None)
    if path is None or method is None:
        raise ValueError('@get or @post not define in %s'%str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn=asyncio.coroutine(fn)
    logging.info('add route %s %s=>%s(%s)'%(method,path,fn.__name__,', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method,path,RequestHandler(app,fn))

def add_routes(app,module_name):
    n=module_name.rfind('.')  #返回字符串最后一次出现的位置(从右向左查询)，如果没有匹配项则返回-1
    if n==(-1):
        #每个函数都有着自已的名字空间，叫做局部名字空间，它记录了函数的变量，包括 函数的参数和局部定义的变量。  locals()返回局部名字空间
        #每个模块拥有它自已的名字空间，叫做全局名字空间，它记录了模块的变量，包括函数、类、其它导入的模块、模块级的变量和常量  globals()返回全局名字空间
        mod=__import__(module_name,globals(),locals())  # __import__ 作用同import语句，但__import__是一个函数，并且只接收字符串作为参数
    else:
        name=module_name[n+1:]
        mod=getattr(__import__(module_name[:n],globals(),locals(),[name]),name)
    for attr in dir(mod):  #dir() 函数不带参数时，返回当前范围内的变量、方法和定义的类型列表；带参数时，返回参数的属性、方法列表
        if attr.startswith('_'):
            continue
        fn=getattr(mod,attr)
        if callable(fn):
            method=getattr(fn,'__method__',None)
            path=getattr(fn,'__route__',None)
            if method and path:
                add_route(app,fn)