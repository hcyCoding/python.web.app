

import orm
from models import User,Blog,Comment
import asyncio


async def test(loop):
    await orm.create_pool(loop,user='root', password='123456', db='awesome')
    u = User(name='Test', email='test6@example.com', passwd='1234567890', image='about:blank')
    await u.save()

async def findall(loop):
    await orm.create_pool(loop,user='root', password='123456', db='awesome')
    rs=await User.findAll()
    print(rs)

loop = asyncio.get_event_loop()
loop.run_until_complete(findall(loop))