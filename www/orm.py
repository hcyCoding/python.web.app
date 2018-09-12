#!/usr/bin/env python3
#-*- coding:utf-8 -*-

__author__='hcyCoding'

import logging
import asyncio
import aiomysql

logging.basicConfig(level=logging.INFO)

#创建mysql数据库连接池
async def create_pool(loop,**kw):
    logging.info('create database connection pool...')
    global __pool
    __pool=await aiomysql.create_pool(
        host=kw.get('host','localhost')
        port=kw.get('port',3306)
        user=kw['user']
        password=kw['password']
        db=kw['db']
        charset=kw.get('charset','utf8')
        autocommit=kw.get('autocommit',True)
        maxsize=kw.get('maxsize',10)
        minsize=kw.get('minsize',1)
        loop=loop
    )

#执行查询sql语句
async select(sql,args,size=None):
    log(sql,args)
    global __pool
    with (await __pool) as conn:
        cursor=await conn.cursor(aiomysql.DictCursor)
        await cursor.execute(sql.replace('?','%s'),args or ())
        if size:
            rs=await cursor.fetchmany(size)
        else:
            rs=cursor.fetchall()
        cursor.close()
        logging.info('rows return:%s'%len(rs))
        return rs

#执行增，删，改sql语句
async def execute(sql,args):
    log(sql)
    with (await __loop) as conn:
        try:
            cursor=conn.cursor()
            await cursor.execute(sql.replace('?','%s'),args)
            affected=cursor.rowcount
            await cursor.close()
        except BaseException as e:
            raise
        return affected

def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)

#ORM映射的基类
class Model(dict,metaclass=ModelMetaclass):
    def __init__(self,**kw):
        super(Model,self).__init__(**kw)
    def __getattr__(self,key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r'"Model" object has no attribute "%s"'%key)
    def __setattr__(self,key,value):
        self[key]=value
    def getValue(self,key):
        return getattr(self,key,None)
    def getValueOrDefault(self,key):
        value=getattr(self,key,None)
        if value is None:
            field=self.__mapping__[key]
            if field.default is not None:
                value=field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s:%s'%(key,str(value)))
                setattr(self,key,value)
        return value
    #classmethod 修饰符对应的函数不需要实例化,类似C#里的static方法
    @classmethod
    async def find(cls,pk):
        'find object by primary key'
        rs=await select('%s where `%s`=?'%(cls.__select__,cls.__primary_key__),[pk],1))
        if len(rs)==0:
            return None
        return cls(**rs[0])
    @classmethod
    async def findAll(cls,where=None,args=None,**kw):
        'find objects by where'
        sql=[cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args=[]
        orderBy=kw.get('orderBy',None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit=kw.get('limit',None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit,int):
                sql.append('?')
                sql.append(limit)
            elif isinstance(limit,tuple) and len(limit)==2:
                sql.append('?,?')  #向列表中添加一个对象object
                sql.extend(limit)  #把一个序列seq的内容添加到列表中
            else:
                raise ValueError('invalid limit value:%s'%str(limit))
        rs=await select(' '.join(sql),args)
        return [cls(**r) for r in rs]
    @classmethod
    async def findNumber(cls,selectField,where=None,args=None):
        'find number by select  and where'
        sql=['select %s __num__ from `%s`'%(selectField,cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs=await select(' '.join(sql),args,1)
        if len(rs)==0:
            return None
        return rs[0]['__num__']
    async save(self):
        args=list(map(self.getValueOrDefault,self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows=await.execute(self.__insert__,args)
        if rows!=1:
            logging.warn('faild to insert record:affected rows:%s'%rows)
    async def update(self):
        args=list(map(self.getValue,self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows=await execute(self.__update__,args)
        if rows!=1:
            logging.warn('faild to update by primary key:affected rows:%s'%rows)
    async def remove(self):
        args=[self.getValue(self.__primary_key__)]
        rows=await execute(self.__delete__,args)
        if rows!=1:
            logging.warn('faild to remove by primary key:affected rows:%s'%rows)

class Field(object):
    def __init__(self,name,column_type,primary_key,default):
        self.name=name
        self.column_type=column_type
        self.primary_key=primary_key
        self.default=default
    def __str__(self):
        return '<%s,%s:%s>'%(self.__class__.__name__,self.column_type,self.name)
    __repr__=__str__

class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
    super().__init__(name, ddl, primary_key, default)

class IntegerField(Field):
    def __init__(self,name=None, primary_key=False, default=None, ddl='smallint')

class ModelMetaclass(type):
    def __new__(cls,name,bases,attrs):
        if name=='Model':
            return type.__new__(cls,name,bases,attrs)
        tableName=attrs.get('__tableName__',None) or name
        logging.info('found model:%s (table:%s)'%(name,tableName))
        #获取所有field和主键名
        mappings=dict()
        fields=[]
        primaryKey=None
        for k,v in attrs.items():
            if isinstance(v,Field):
                logging.info(' found mapping :%s==>%s'%(k,v))
                mapping[k]=v
                if v.primary_key:
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field:%s'%k)
                    primaryKey=k
                else:
                    fields.append(k)
            if not primaryKey:
                raise RuntimeError('primary key not found')
            if k in mappings.keys():
                attrs.pop(k)
            #防止sql注入
            escaped_fields=list(map(lambda f: '`%s`' % f, fields))
            attrs['__mapping__']=mappings
            attrs['__table__']=tableName
            attrs['__primary_key__']=primaryKey
            attrs['__fields__']=fields
            #构造sql语句
            attrs['__select__']='select `%s`, %s from `%s`'%(primaryKey,','.join(escaped_fields),tableName)
            attrs['__insert__']='insert into `%s` (%s,`%s`) values (%s)'%(tableName,','.join(escaped_fields),primaryKey,create_args_string(len(escaped_fields)+1))
            attrs['__update__']='update `%s` set %s where `%s`=?'%(tableName,','.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)),primaryKey)
            attrs['__delete__']='delete from `%s` where `%s`=?'%(tableName,primaryKey)
            return type.__new__(cls,name,bases,attrs)