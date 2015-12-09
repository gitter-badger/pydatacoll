from collections import defaultdict
try:
    import ujson as json
except ImportError:
    import json
import asyncio
import functools
import aioredis
# import api_hour
from aiohttp import web
import redis

import pydatacoll.utils.logger as my_logger
from pydatacoll.utils.json_response import JSON
from pydatacoll.resources.protocol import *
from pydatacoll.utils.func_container import ParamFunctionContainer, param_function

logger = my_logger.getLogger('APIServer')
HANDLER_TIME_OUT = 15


class APIServer(ParamFunctionContainer):
    def __init__(self, web_app: web.Application, io_loop: asyncio.AbstractEventLoop=None,
                 redis_pool: aioredis.RedisPool=None):
        super().__init__()
        self.web_app = web_app
        self.io_loop = io_loop or asyncio.get_event_loop()
        self.redis_pool = redis_pool or self.io_loop.run_until_complete(
            functools.partial(aioredis.create_pool, ('localhost', 6379), db=1, minsize=5, maxsize=10,
                              encoding='utf-8')())
        self.redis_client = redis.StrictRedis(db=1, decode_responses=True)
        self._add_router()

    def _add_router(self):
        for fun_name, args in self.module_arg_dict.items():
            self.web_app.router.add_route(args['method'], args['url'], getattr(self, fun_name), name=fun_name)

    def make_handler(self, **kwargs):
        return self.web_app.make_handler(**kwargs)

    @staticmethod
    async def _find_keys(redis_client, match: str):
        cursor = None
        all_keys = set()
        try:
            while cursor != 0:
                res = await redis_client.scan(cursor or b'0', match=match)
                cursor, keys = res
                all_keys.update(keys)
        except Exception as e:
            logger.error('_find_keys failed: %s', repr(e), exc_info=True)
        return all_keys

    @param_function(method='GET', url=r'/')
    async def get_index(self, request):
        doc_list = ['pydatacoll server is running, API is:\n']
        method_dict = defaultdict(list)
        for route in self.web_app.router.routes():
            method_dict[route.method].append('method: {:<8} URL: {}://{}{}'.format(
                route.method, request.scheme, request.host,
                route._formatter if hasattr(route, '_formatter') else route._path),
            )
        doc_list.append('\n'.join(sorted(method_dict['GET'])))
        doc_list.append('\n'.join(sorted(method_dict['POST'])))
        doc_list.append('\n'.join(sorted(method_dict['PUT'])))
        doc_list.append('\n'.join(sorted(method_dict['DELETE'])))
        return web.Response(text='\n'.join(doc_list))

    @param_function(method='GET', url=r'/api/v1/device_protocols')
    async def get_device_protocol_list(self, request):
        return JSON(DEVICE_PROTOCOLS)

    @param_function(method='GET', url=r'/api/v1/term_protocols')
    async def get_term_protocol_list(self, request):
        return JSON(TERM_PROTOCOLS)

    @param_function(method='GET', url=r'/api/v1/devices')
    async def get_device_list(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                device_list = await redis_client.smembers('SET:DEVICE')
                return JSON(device_list)
        except Exception as e:
            logger.error('get_device_list failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='GET', url=r'/api/v1/devices/{device_id}')
    async def get_device(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                device = await redis_client.hgetall('HS:DEVICE:{}'.format(request.match_info['device_id']))
                if not device:
                    return web.Response(status=404, text='device_id not found!')
                return JSON(device)
        except Exception as e:
            logger.error('get_device failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='GET', url=r'/api/v1/terms')
    async def get_term_list(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                term_list = await redis_client.smembers('SET:TERM')
                return JSON(term_list)
        except Exception as e:
            logger.error('get_term_list failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='GET', url=r'/api/v1/terms/{term_id}')
    async def get_term(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                term_id = request.match_info['term_id']
                term = await redis_client.hgetall('HS:TERM:{}'.format(term_id))
                if not term:
                    return web.Response(status=404, text='term_id not found!')
                return JSON(term)
        except Exception as e:
            logger.error('get_term failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='GET', url=r'/api/v1/items')
    async def get_item_list(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                item_list = await redis_client.smembers('SET:ITEM')
                return JSON(item_list)
        except Exception as e:
            logger.error('get_item_list failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='GET', url=r'/api/v1/items/{item_id}')
    async def get_item(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                item_id = request.match_info['item_id']
                item = await redis_client.hgetall('HS:ITEM:{}'.format(item_id))
                if not item:
                    return web.Response(status=404, text='item_id not found!')
                return JSON(item)
        except Exception as e:
            logger.error('get_item failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='GET', url=r'/api/v1/devices/{device_id}/terms')
    async def get_device_term_list(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                device_id = request.match_info['device_id']
                found = await redis_client.exists('SET:DEVICE_TERM:{}'.format(device_id))
                if not found:
                    return web.Response(status=404, text='device_id not found!')
                term_list = await redis_client.smembers('SET:DEVICE_TERM:{}'.format(device_id))
                return JSON(term_list)
        except Exception as e:
            logger.error('get_device_term_list failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='GET', url=r'/api/v1/terms/{term_id}/items')
    async def get_term_item_list(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                term_id = request.match_info['term_id']
                found = await redis_client.exists('SET:TERM_ITEM:{}'.format(term_id))
                if not found:
                    return web.Response(status=404, text='term_id not found!')
                item_list = await redis_client.smembers('SET:TERM_ITEM:{}'.format(term_id))
                return JSON(item_list)
        except Exception as e:
            logger.error('get_term_item_list failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='GET', url=r'/api/v1/terms/{term_id}/items/{item_id}')
    async def get_term_item(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                term_id = request.match_info['term_id']
                item_id = request.match_info['item_id']
                found = await redis_client.exists('HS:TERM:{}'.format(term_id))
                if not found:
                    return web.Response(status=404, text='term_id not found!')
                found = await redis_client.exists('HS:ITEM:{}'.format(item_id))
                if not found:
                    return web.Response(status=404, text='item_id not found!')
                term_item = await redis_client.hgetall('HS:TERM_ITEM:{}:{}'.format(term_id, item_id))
                if not term_item:
                    return web.Response(status=404, text='term_item not found!')
                return JSON(term_item)
        except Exception as e:
            logger.error('get_term_item failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))
        
    @param_function(method='GET', url=r'/api/v1/devices/{device_id}/terms/{term_id}/items/{item_id}/datas')
    async def get_data_list(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                device_id = request.match_info['device_id']
                term_id = request.match_info['term_id']
                item_id = request.match_info['item_id']
                data_list = await redis_client.lrange('LST:DATA:{}:{}:{}'.format(device_id, term_id, item_id), 0, -1)
                return JSON(data_list)
        except Exception as e:
            logger.error('get_data_list failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='GET', url=r'/api/v1/devices/{device_id}/terms/{term_id}/items/{item_id}/datas/{index}')
    async def get_data(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                device_id = request.match_info['device_id']
                term_id = request.match_info['term_id']
                item_id = request.match_info['item_id']
                index = int(request.match_info['index'])
                data_list = await redis_client.lindex('LST:DATA:{}:{}:{}'.format(device_id, term_id, item_id), index)
                return JSON(data_list)
        except Exception as e:
            logger.error('get_data failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='POST', url=r'/api/v1/devices')
    async def create_device(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                device_data = await request.read()
                device_dict = json.loads(device_data)
                logger.debug('new device arg=%s', device_dict)
                found = await redis_client.exists('HS:DEVICE:{}'.format(device_dict['id']))
                if found:
                    return web.Response(status=409, text='device already exists!')
                self.redis_client.hmset('HS:DEVICE:{}'.format(device_dict['id']), device_dict)
                await redis_client.sadd('SET:DEVICE', device_dict['id'])
                await redis_client.publish('CHANNEL:DEVICE_ADD', device_data)
                return web.Response()
        except Exception as e:
            logger.error('create_device failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='PUT', url=r'/api/v1/devices/{device_id}')
    async def update_device(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                device_id = request.match_info['device_id']
                old_device = await redis_client.hgetall('HS:DEVICE:{}'.format(device_id))
                if not old_device:
                    return web.Response(status=404, text='device_id not found!')
                device_data = await request.read()
                device_dict = json.loads(device_data)
                if str(device_dict['id']) != device_id:
                    await self.del_device(request)
                    await self.create_device(request)
                else:
                    self.redis_client.hmset('HS:DEVICE:{}'.format(device_id), device_dict)
                    await redis_client.publish('CHANNEL:DEVICE_FRESH', device_data)
                return web.Response()
        except Exception as e:
            logger.error('update_device failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='DELETE', url=r'/api/v1/devices/{device_id}')
    async def del_device(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                device_id = request.match_info['device_id']
                device_dict = await redis_client.hgetall('HS:DEVICE:{}'.format(device_id))
                if not device_dict:
                    return web.Response(status=404, text='device_id not found!')
                await redis_client.publish('CHANNEL:DEVICE_DEL', json.dumps(device_id))
                await redis_client.delete('HS:DEVICE:{}'.format(device_id))
                await redis_client.srem('SET:DEVICE', device_id)
                # delete all terms connected to that device
                term_list = await redis_client.smembers('SET:DEVICE_TERM:{}'.format(device_id))
                for term_id in term_list:
                    await redis_client.delete('HS:TERM:{}'.format(term_id))
                    await redis_client.srem('SET:TERM', term_id)
                    keys = await self._find_keys(redis_client, 'HS:TERM_ITEM:{}:*'.format(term_id))
                    if keys:
                        self.redis_client.delete(*keys)
                    await redis_client.delete('SET:TERM_ITEM:{}'.format(term_id))
                await redis_client.delete('SET:DEVICE_TERM:{}'.format(device_id))
                await redis_client.delete('LST:FRAME:{}'.format(device_id))
                # delete values
                keys = await self._find_keys(redis_client, 'LST:DATA:{}:*'.format(device_id))
                if keys:
                        self.redis_client.delete(*keys)
                # delete mapping
                keys = await self._find_keys(redis_client, 'HS:MAPPING:*:{}:*'.format(device_id))
                if keys:
                        self.redis_client.delete(*keys)
                return web.Response()
        except Exception as e:
            logger.error('del_device failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='POST', url=r'/api/v1/terms')
    async def create_term(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                term_data = await request.read()
                term_dict = json.loads(term_data)
                logger.debug('new term arg=%s', term_dict)
                found = await redis_client.exists('HS:TERM:{}'.format(term_dict['id']))
                if found:
                    return web.Response(status=409, text='term already exists!')
                self.redis_client.hmset('HS:TERM:{}'.format(term_dict['id']), term_dict)
                await redis_client.sadd('SET:TERM', term_dict['id'])
                await redis_client.sadd('SET:DEVICE_TERM:{}'.format(term_dict['device_id']), term_dict['id'])
                await redis_client.publish('CHANNEL:TERM_ADD"', term_data)
                return web.Response()
        except Exception as e:
            logger.error('create_term failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='PUT', url=r'/api/v1/terms/{term_id}')
    async def update_term(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                term_id = request.match_info['term_id']
                old_term = await redis_client.hgetall('HS:TERM:{}'.format(term_id))
                if not old_term:
                    return web.Response(status=404, text='term_id not found!')
                term_data = await request.read()
                term_dict = json.loads(term_data)
                if str(term_dict['id']) != term_id:
                    await self.del_term(request)
                    await self.create_term(request)
                else:
                    self.redis_client.hmset('HS:TERM:{}'.format(term_id), term_dict)
                    if term_dict['device_id'] != old_term['device_id']:
                        await redis_client.publish('CHANNEL:TERM_DEL', json.dumps(old_term))
                        await redis_client.publish('CHANNEL:TERM_ADD', term_data)
                return web.Response()
        except Exception as e:
            logger.error('update_term failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))
        
    @param_function(method='DELETE', url=r'/api/v1/terms/{term_id}')
    async def del_term(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                term_id = request.match_info['term_id']
                term_info = await redis_client.hgetall('HS:TERM:{}'.format(term_id))
                if not term_info:
                    return web.Response(status=404, text='term_id not found!')
                device_id = term_info['device_id']
                await redis_client.publish('CHANNEL:TERM_DEL', json.dumps({'device_id': device_id, 'term_id': term_id}))
                await redis_client.delete('HS:TERM:{}'.format(term_id))
                await redis_client.srem('SET:TERM', term_id)
                await redis_client.srem('SET:DEVICE_TERM:{}'.format(term_info['device_id']), term_id)
                await redis_client.delete('SET:TERM_ITEM:{}'.format(term_id))
                # delete all values
                keys = await self._find_keys(redis_client, 'LST:DATA:*:{}:*'.format(term_id))
                if keys:
                        self.redis_client.delete(*keys)
                # delete from protocols mapping
                all_keys = set()
                keys = await self._find_keys(redis_client, 'HS:MAPPING:*')
                for key in keys:
                    map_key = await redis_client.hgetall(key)
                    if str(map_key['term_id']) == term_id:
                        all_keys.add(key)
                if all_keys:
                        self.redis_client.delete(*all_keys)
                return web.Response()
        except Exception as e:
            logger.error('del_term failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='POST', url=r'/api/v1/items')
    async def create_item(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                item_data = await request.read()
                item_dict = json.loads(item_data)
                logger.debug('new item arg=%s', item_dict)
                found = await redis_client.exists('HS:ITEM:{}'.format(item_dict['id']))
                if found:
                    return web.Response(status=409, text='item already exists!')
                self.redis_client.hmset('HS:ITEM:{}'.format(item_dict['id']), item_dict)
                await redis_client.sadd('SET:ITEM', item_dict['id'])
                return web.Response()
        except Exception as e:
            logger.error('create_item failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='PUT', url=r'/api/v1/items/{item_id}')
    async def update_item(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                item_id = request.match_info['item_id']
                old_item = await redis_client.hgetall('HS:ITEM:{}'.format(item_id))
                if not old_item:
                    return web.Response(status=404, text='item_id not found!')
                item_data = await request.read()
                item_dict = json.loads(item_data)
                if str(item_dict['id']) != item_id:
                    await self.del_item(request)
                    await self.create_item(request)
                else:
                    self.redis_client.hmset('HS:ITEM:{}'.format(item_id), item_dict)
                return web.Response()
        except Exception as e:
            logger.error('update_item failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))
        
    @param_function(method='DELETE', url=r'/api/v1/items/{item_id}')
    async def del_item(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                item_id = request.match_info['item_id']
                found = await redis_client.exists('HS:ITEM:{}'.format(item_id))
                if not found:
                    return web.Response(status=404, text='item_id not found!')
                await redis_client.delete('HS:ITEM:{}'.format(item_id))
                await redis_client.srem('SET:ITEM', item_id)
                # delete from term->item set
                keys = await self._find_keys(redis_client, 'SET:TERM_ITEM:*')
                for key in keys:
                    await redis_client.srem(key, item_id)
                # delete from term->item hash
                keys = await self._find_keys(redis_client, 'HS:TERM_ITEM:*:{}'.format(item_id))
                if keys:
                        self.redis_client.delete(*keys)
                # delete from protocols mapping
                all_keys = set()
                keys = await self._find_keys(redis_client, 'HS:MAPPING:*')
                for key in keys:
                    map_key = await redis_client.hgetall(key)
                    if map_key and str(map_key['item_id']) == item_id:
                        all_keys.add(key)
                if all_keys:
                        await redis_client.delete(*all_keys)
                # delete all values
                keys = await self._find_keys(redis_client, 'LST:DATA:*:*:{}'.format(item_id))
                if keys:
                        self.redis_client.delete(*keys)
                return web.Response()
        except Exception as e:
            logger.error('del_item failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='POST', url=r'/api/v1/terms/{term_id}/items')
    async def create_term_item(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                term_item_data = await request.read()
                term_item_dict = json.loads(term_item_data)
                logger.debug('new term_item arg=%s', term_item_dict)
                term_id = request.match_info['term_id']
                if term_id != str(term_item_dict['term_id']):
                    return web.Response(status=400, text='term_id mismatch in url and body!')
                item_id = term_item_dict['item_id']
                found = await redis_client.exists('HS:TERM:{}'.format(term_id))
                if not found:
                    return web.Response(status=404, text='term_id not found!')
                found = await redis_client.exists('HS:ITEM:{}'.format(item_id))
                if not found:
                    return web.Response(status=404, text='item_id not found!')
                found = await redis_client.exists('HS:TERM_ITEM:{}:{}'.format(term_id, item_id))
                if found:
                    return web.Response(status=409, text='term_item already exists!')
                term_info = await redis_client.hgetall('HS:TERM:{}'.format(term_id))
                device_id = term_info['device_id']
                term_item_dict.update({'device_id': device_id})
                device_info = await redis_client.hgetall('HS:DEVICE:{}'.format(device_id))
                self.redis_client.hmset('HS:TERM_ITEM:{}:{}'.format(term_id, item_id), term_item_dict)
                await redis_client.sadd('SET:TERM_ITEM:{}'.format(term_id), item_id)
                # delete old mapping
                all_keys = set()
                keys = await self._find_keys(redis_client, 'HS:MAPPING:{}:*:*'.format(device_info['protocol'].upper()))
                for key in keys:
                    map_key = await redis_client.hgetall(key)
                    if str(map_key['term_id']) == term_id and str(map_key['item_id']) == item_id:
                        all_keys.add(key)
                if all_keys:
                        self.redis_client.delete(*all_keys)
                self.redis_client.hmset('HS:MAPPING:{}:{}:{}'.format(
                    device_info['protocol'].upper(), device_id, term_item_dict['protocol_code']), term_item_dict)
                await redis_client.publish('CHANNEL:TERM_ITEM_ADD', json.dumps(term_item_dict))
                return web.Response()
        except Exception as e:
            logger.error('create_term_item failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='PUT', url=r'/api/v1/terms/{term_id}/items/{item_id}')
    async def update_term_item(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                term_item_data = await request.read()
                term_item_dict = json.loads(term_item_data)
                term_id = request.match_info['term_id']
                item_id = request.match_info['item_id']
                old_term_item = await redis_client.hgetall('HS:TERM_ITEM:{}:{}'.format(term_id, item_id))
                if not old_term_item:
                    return web.Response(status=404, text='term_item not found!')
                if str(term_item_dict['term_id']) == term_id and str(term_item_dict['item_id']) == item_id:
                    await self.del_term_item(request)
                    await self.create_term_item(request)
                return web.Response()
        except Exception as e:
            logger.error('update_term_item failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='DELETE', url=r'/api/v1/terms/{term_id}/items/{item_id}')
    async def del_term_item(self, request):
        try:
            with (await self.redis_pool) as redis_client:
                term_id = request.match_info['term_id']
                item_id = request.match_info['item_id']
                term_item_dict = await redis_client.hgetall('HS:TERM_ITEM:{}:{}'.format(term_id, item_id))
                if not term_item_dict:
                    return web.Response(status=404, text='term_item not found!')
                term_info = await redis_client.hgetall('HS:TERM:{}'.format(term_id))
                device_id = term_info['device_id']
                device_info = await redis_client.hgetall('HS:DEVICE:{}'.format(device_id))
                await redis_client.publish('CHANNEL:TERM_ITEM_DEL',
                                           json.dumps({'device_id': device_id, 'term_id': term_id, 'item_id': item_id}))
                await redis_client.delete('HS:TERM_ITEM:{}:{}'.format(term_id, item_id))
                await redis_client.srem('SET:TERM_ITEM:{}'.format(term_id), item_id)
                await redis_client.delete('HS:MAPPING:{}:{}:{}'.format(
                    device_info['protocol'].upper(), device_id, term_item_dict['protocol_code']))
                # delete all values
                keys = await self._find_keys(redis_client, 'LST:DATA:*:{}:{}'.format(term_id, item_id))
                if keys:
                        self.redis_client.delete(*keys)
                return web.Response()
        except Exception as e:
            logger.error('del_term_item failed: %s', repr(e), exc_info=True)
            return web.Response(status=400, text=repr(e))

    @param_function(method='POST', url=r'/api/v1/device_call')
    async def device_call(self, request):
        redis_client = None
        channel_name = None
        try:
            redis_client = await self.redis_pool.acquire()
            call_data = await request.read()
            call_data_dict = json.loads(call_data)
            logger.debug('new call_data arg=%s', call_data_dict)
            found = await redis_client.exists('HS:DEVICE:{}'.format(call_data_dict['device_id']))
            if not found:
                return web.Response(status=404, text='device_id not found!')
            found = await redis_client.exists('HS:TERM:{}'.format(call_data_dict['term_id']))
            if not found:
                return web.Response(status=404, text='term_id not found!')
            found = await redis_client.exists('HS:ITEM:{}'.format(call_data_dict['item_id']))
            if not found:
                return web.Response(status=404, text='item_id not found!')
            found = await redis_client.exists('HS:TERM_ITEM:{}:{}'.format(call_data_dict['term_id'],
                                                                          call_data_dict['item_id']))
            if not found:
                return web.Response(status=404, text='term_item not found!')
            await redis_client.publish('CHANNEL:DEVICE_CALL', call_data)
            channel_name = 'CHANNEL:DEVICE_CALL:{}:{}:{}'.format(
                call_data_dict['device_id'], call_data_dict['term_id'], call_data_dict['item_id'])
            res = await redis_client.subscribe(channel_name)
            cb = asyncio.futures.Future()
            async def reader(ch):
                while await ch.wait_message():
                    msg = await ch.get_json()
                    logger.debug('device_call got msg: %s', msg)
                    cb.set_result(msg)
            tsk = asyncio.ensure_future(reader(res[0]))
            rst = await asyncio.wait_for(cb, HANDLER_TIME_OUT)
            await redis_client.unsubscribe(channel_name)
            await tsk
            self.redis_pool.release(redis_client)
            return JSON(rst)
        except Exception as e:
            logger.exception(e)
            logger.error('device_call failed: %s', repr(e), exc_info=True)
            if redis_client and redis_client.in_pubsub and channel_name:
                await redis_client.unsubscribe(channel_name)
            return web.Response(status=400, text=repr(e))

    @param_function(method='POST', url=r'/api/v1/device_ctrl')
    async def device_ctrl(self, request):
        redis_client = None
        channel_name = None
        try:
            redis_client = await self.redis_pool.acquire()
            ctrl_data = await request.read()
            ctrl_data_dict = json.loads(ctrl_data)
            logger.debug('new ctrl_data arg=%s', ctrl_data_dict)
            found = await redis_client.exists('HS:DEVICE:{}'.format(ctrl_data_dict['device_id']))
            if not found:
                return web.Response(status=404, text='device_id not found!')
            found = await redis_client.exists('HS:TERM:{}'.format(ctrl_data_dict['term_id']))
            if not found:
                return web.Response(status=404, text='term_id not found!')
            found = await redis_client.exists('HS:ITEM:{}'.format(ctrl_data_dict['item_id']))
            if not found:
                return web.Response(status=404, text='item_id not found!')
            found = await redis_client.exists('HS:TERM_ITEM:{}:{}'.format(ctrl_data_dict['term_id'],
                                                                          ctrl_data_dict['item_id']))
            if not found:
                return web.Response(status=404, text='term_item not found!')
            await redis_client.publish('CHANNEL:DEVICE_CTRL', ctrl_data)
            channel_name = 'CHANNEL:DEVICE_CTRL:{}:{}:{}'.format(
                ctrl_data_dict['device_id'], ctrl_data_dict['term_id'], ctrl_data_dict['item_id'])
            res = await redis_client.subscribe(channel_name)
            cb = asyncio.futures.Future()
            async def reader(ch):
                while await ch.wait_message():
                    msg = await ch.get_json()
                    logger.debug('device_ctrl got msg: %s', msg)
                    cb.set_result(msg)
            tsk = asyncio.ensure_future(reader(res[0]))
            rst = await asyncio.wait_for(cb, HANDLER_TIME_OUT)
            await redis_client.unsubscribe(channel_name)
            await tsk
            self.redis_pool.release(redis_client)
            return JSON(rst)
        except Exception as e:
            logger.exception(e)
            logger.error('device_ctrl failed: %s', repr(e), exc_info=True)
            if redis_client and redis_client.in_pubsub and channel_name:
                await redis_client.unsubscribe(channel_name)
            return web.Response(status=400, text=repr(e))

# class Container(api_hour.Container):
#     """
#         run in cmd: api_hour -w 4 api_server:Container
#     """
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # Declare HTTP server
#         self.servers['http'] = web.Application(loop=kwargs['loop'])
#         self.servers['http'].ah_container = self  # keep a reference in HTTP server to Container
#         self.api_server = APIServer(io_loop=kwargs['loop'], web_app=self.servers['http'])
#
#     def make_servers(self, socket):
#         # This method is used by api_hour command line to bind your HTTP server on socket
#         return [self.servers['http'].make_handler(logger=self.worker.log,
#                                                   keep_alive=self.worker.cfg.keepalive,
#                                                   access_log=self.worker.log.access_log,
#                                                   access_log_format=self.worker.cfg.access_log_format)]


def run_server(port=8080):
    loop = asyncio.get_event_loop()
    web_app = web.Application()
    api_server = APIServer(web_app)
    handler = api_server.make_handler()
    server = loop.run_until_complete(loop.create_server(handler, '127.0.0.1', port))
    logger.info('serving on %s', server.sockets[0].getsockname())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(handler.finish_connections(1.0))
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.run_until_complete(web_app.finish())
    loop.close()

if __name__ == '__main__':
    run_server()