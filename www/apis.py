#!/usr/bin/env python3
#-*- coding:utf-8 -*-

__author__='hcyCoding'

class APIError(Exception):
    '''
      the base APIError which contains error(required),data(optional) and message(optional)
    '''
    def __init__(self,error,data='',message=''):
        super(APIError,self).__init__(message)
        self.error=error
        self.data=data
        self.message=message

class APIValueError(APIError):
    '''
      indicate the input value has error or invalid.the data specifies the error field or input form
    '''
    def __init__(self,field,message=''):
        super(APIValueError,self).__init__('value:invalid',field,message)

class APIResourceNotFound(APIError):
    '''
      indicate the resource was not found.the data specifies the resource name
    '''
    def __init__(self,field,message=''):
        super(APIResourceNotFound,self).__init__('value:not found',field,message)

class APIPermissionError(APIError):
    '''
      indicate the api has no permission
    '''
    def __init__(self,message):
        super(APIPermissionError,self).__init__('permission:forbidden','permission',message)