from __future__ import annotations
from dataclasses import dataclass, field
from enum import Flag
from typing import *
from httpx import Client, AsyncClient, Response, Request
from .util import create_aclient
from bs4 import BeautifulSoup
import lxml.html
import asyncio



def make_scraper(
    module, 
    req_builder: Union[Callable[[dict], dict], dict], 
    pre_req_build: Callable[[dict], dict] = lambda r, _: r,
    callback: Callable[[Response], Any] = lambda r: r
) -> RequestSenderBase:
    if isinstance(req_builder, dict):
        req_dict = req_builder.copy()
        req_builder = lambda _: req_dict

    request_sender = RequestSenderBase(
        engine=module, 
        req_builder=req_builder, 
        pre_req_build=pre_req_build, 
        callback=callback,
    )
    return request_sender



class ScraperModuleBase():

    def __init__(self):
        self.scrapers = {}
        self.modules = {}
        self.workflows = {}

    def make_scraper(
        self,
        req_builder: Union[Callable[[dict], dict], dict], 
        pre_req_build: Callable[[dict], dict] = lambda r, _: r,
        callback: Callable[[Response], Any] = lambda r: r
    ):
        return make_scraper(
            self,
            req_builder,
            pre_req_build=pre_req_build,
            callback=callback
        )

    def register_scraper(
        self, 
        name: str,
        pre_req_build: Callable[[dict], dict] = lambda r, _: r,
        callback: Callable[[Response], Any] = lambda r: r
    ) -> Callable:
        def wrapper(req_builder: Callable[[dict], dict]):
            self.scrapers[name] = {
                'req_builder': req_builder,
                'pre_req_build': pre_req_build,
                'callback': callback
            }
            # print("Scraper registered: {}".format(name))
        return wrapper

    def register_workflow(
        self, 
        name: str
    ):
        def wrapper(workflow):
            self.workflows[name] = workflow
        return wrapper

    def load_scraper_module(self, name, module):
        self.modules[name] = {}
        for sname,s_dict in module.scrapers.items():
            s = make_scraper(self, **s_dict)
            self.modules[name][sname] = s




class ScrapingEngineBase(ScraperModuleBase):

    initial_static_headers = {}
    global_headers = {}
    header_set = {}
    states = {}

    def __init__(self, cookie: str = '', client_kw={}):
        super().__init__()

        self.client: AsyncClient = create_aclient(**client_kw)

        self.client.headers.update(self.initial_static_headers)

        if cookie:
            self.client.headers.update({'cookie': cookie})

        setattr(self, 'FFF', lambda self: 'r')

    async def aclose(self) -> Coroutine[None]:
        await self.client.aclose()

    def register_scraper(
        self, 
        name: str,
        pre_req_build: Callable[[dict], dict] = lambda r, _: r,
        callback: Callable[[Response], Any] = lambda r: r
    ) -> Callable:
        def wrapper(req_builder: Callable[[dict], dict]):
            self.scrapers[name] = make_scraper(
                self,
                req_builder, 
                pre_req_build=pre_req_build, 
                callback=callback
            )
            # print("Scraper registered: {}".format(name))
        return wrapper

    def register_workflow(
        self, 
        name: str
    ):
        def wrapper(workflow):
            self.workflows[name] = lambda *args, **kwargs: workflow(self, *args, **kwargs)
        return wrapper

    def load_scraper_module(self, name, module):
        for sname,s_dict in module.scrapers.items():
            module.scrapers[sname] = make_scraper(self, **s_dict)
        for wname,w in module.workflows.items():
            module.workflows[wname] = lambda *args, **kwargs: w(module, *args, **kwargs)
        self.modules[name] = module


    def start_many(self, req_builders: Callable[[dict], Iterable], sync: bool = True) -> RequestSenderBase:
        request_sender = RequestSenderBase(self, req_builders, many=True, sync=sync)
        return request_sender

    def add_global_headers(self, headers: dict):
        # self.global_headers.update(headers)
        self.client.headers.update(headers)
    



async def send_request_with_params(client: AsyncClient, params: dict) -> Response:
    req = client.build_request(**params)
    res = await client.send(req)
    return res
            



@dataclass
class RequestSenderBase():

    engine: ScrapingEngineBase

    req_builder: Callable[[dict], Union[dict, Iterable]]
    pre_req_build: Callable[[dict, ScrapingEngineBase], dict] = lambda r, _: r
    callback: Callable[[Response], Any] = lambda r: r

    result_queue: list = field(default_factory=list, init=False)

    many: bool = False
    sync: bool = True

    # async def scrape(self, **input_kwargs) -> Coroutine[Any, Any, RequestSenderBase]:
    async def scrape(self, *input_args, **input_kwargs: dict) -> RequestSenderBase:
        # build request params from input kwargs using user-defined request builder
        req_params = self.req_builder(self.engine, *input_args, **input_kwargs)
        if isinstance(req_params, Generator):
            req_params = list(req_params)
            if len(req_params) == 1:
                req_params = req_params[0]

        req_params = self._process_params(req_params)
        
        c = self.engine.client
        if self.many:
            if self.sync: 
                res = [await send_request_with_params(c, r) for r in req_params]
            else:
                res = await asyncio.gather(*[send_request_with_params(c, r) for r in req_params])
        else:
            res = await send_request_with_params(c, req_params)

        # add the response to the result queue
        self.result_queue.append(res)

        return self.callback(self)


    def _process_params(self, req_params):
        if isinstance(self.pre_req_build, Callable):
            req_params = self.pre_req_build(req_params, self.engine)
            return req_params
        elif isinstance(self.pre_req_build, Iterable):
            for pr in self.pre_req_build:
                req_params = pr(req_params, self.engine)
            return req_params
        else:
            print("Invalid pre request build type: {}, must be a function or a list of functions".format(type(self.pre_req_build)))
            return req_params


    def apply(self, f: Callable[[Any], Any], with_engine=False) -> RequestSenderBase:
        o = self.result_queue[-1]
        if o == None:
            return self
        if with_engine:
            n = f(o, self.engine)
        else:
            n = f(o)
        o = self.result_queue.append(n)
        return self
    

    def get(self) -> Any:
        return self.result_queue[-1]

    
    def pre_parse(self, pre_parser: str) -> RequestSenderBase:
        pre_parsers = {
            'soup': lambda r: BeautifulSoup(r.text, 'lxml'),
            'lxml': lambda r: lxml.html.fromstring(r.text),
            'json': lambda r: r.json(),
            '': lambda res: res,
        }
        if pre_parser not in pre_parsers.keys():
            print("'{}' pre parser not supported".format(pre_parser))
        else:
            self.apply(pre_parsers[pre_parser])
        return self



# @dataclass
# class ScraperBase():

#     engine: ScrapingEngineBase = None

#     # method: str
#     # url: URLTypes

#     # data: RequestData = None,
#     # files: RequestFiles = None,
#     # json: Any = None,
#     # params: QueryParamTypes = None,
#     # headers: HeaderTypes = None,
#     # cookies: CookieTypes = None,
#     # timeout: Union[TimeoutTypes, UseClientDefault] = USE_CLIENT_DEFAULT,

#     req_kwargs: dict = None

#     header_set_name: str = None

#     res: Response = field(default=None, init=False)

#     method_name = ''

#     post_hooks = []
    
#     parse: Callable[[
#         Response, BeautifulSoup, lxml.html.HTMLElement
#     ], Any] = field(default=lambda r: r)
#     validate_before_pre_parse: bool = True

#     sleep_after: int = None

#     validate: Callable[[
#         Union[Response, BeautifulSoup, lxml.html.HTMLElement
#     ]], bool] = field(default=lambda r: True)

#     async def start(self, **kwargs):
#         if self.engine == None:
#             print("No engine specified")
#             return

#         if self.header_set_name and self.header_set_name in self.engine.header_set.keys():
#             if not self.req_kwargs.get('headers'):
#                 self.req_kwargs['headers'] = {}
#             self.req_kwargs['headers'].update(self.engine.header_set[self.header_set_name])

#         # TODO: how to build requests
#         req_params = {k: v.format(**kwargs) for k,v in self.req_kwargs.items()}

#         self.res = await self.send(req_params)

#         if self.validate_before_pre_parse:
#             self.validate(self.res)
#             res_after_pre = self._pre_parse(self.pre_parser, self.res)
#         else:
#             res_after_pre = self._pre_parse(self.pre_parser, self.res)
#             self.validate(res_after_pre)

#         result = self.parse(res_after_pre)
        
#         if self.sleep_after:
#             await asyncio.sleep(self.sleep_after)

#         for h in self.post_hooks:
#             result = h(result)

#         return result


#     async def send(self, req_params):
#         req = self.engine.client.build_request(
#             # method=self.method,
#             # url=self.url,
#             # data=self.data,
#             # files=self.files,
#             # json=self.json,
#             # params=self.params,
#             # headers=self.headers,
#             # cookies=self.cookies,
#             # timeout=self.timeout
#             **req_params
#         )

#         res = await self.engine.client.send(req)

#         return res

#     def build(self, **kwargs):
#         pass

#     def _pre_parse(self, pre_parser: str, res: Response):
#         if pre_parser not in pre_parsers.keys():
#             print("'{}' pre parser not supported".format(pre_parser))
#             pre_parser = ''
#         return pre_parsers[pre_parser](res)

