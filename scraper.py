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
    engine, 
    req_builder: Union[Callable[[dict], dict], dict], 
    pre_req_build: Callable[[dict], dict] = lambda r, _: r,
    callback: Callable[[Response], Any] = lambda r: r
) -> RequestSenderBase:
    """Generate a RequestSenderBase object given pre_req_build and post request callback.
    
    Parameters:

     - `req_builder` (function | dict) A method that takes in a engine as a first 
     argument and any arbitrary list arguments and/or dictionary of keyword arguments that
     represents the user input of the request, and returns a dictionary of request parameters.
     If the request parameter dictionary does not depend on any user input, then a static 
     dictionary can also be passed in.
     - `pre_req_build` (function | list) A method that that takes in a dictionary of request 
      parameters and returns a new dictionary of request parameters. This method is executed before building. This can also be a list of methods that will be executed sequencially.
     the request object.
     - `callback` (function) A method that is executed and returned after making the request.
    """
    # if the request build is a request param dictionary
    # then generate a method that returns this dictionary
    if isinstance(req_builder, dict):
        req_dict = req_builder.copy()
        req_builder = lambda _: req_dict

    request_sender = RequestSenderBase(
        engine=engine, 
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
        self.engine = None

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
        def wrapper(req_builder: RequestBuilder):
            self.scrapers[name] = make_scraper(
                None,
                req_builder, 
                pre_req_build=pre_req_build, 
                callback=callback
            )
            # print("Scraper registered: {}".format(name))
            return self.scrapers[name]
        return wrapper

    def register_workflow(
        self, 
        name: str
    ):
        def wrapper(w):
            self.workflows[name] = lambda *args, **kwargs: w(self, *args, **kwargs)
        return wrapper

    def set_engine(self, engine: ScrapingEngineBase):
        for s in self.scrapers.values():
            s.engine = engine
        for m in self.modules.values():
            m.set_engine(engine)

    def load_scraper_module(self, name, module):
        self.modules[name] = module




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

    async def aclose(self) -> Coroutine[None]:
        await self.client.aclose()

    def set_engine(self, _: ScrapingEngineBase):
        pass
    
    def register_scraper(
        self, 
        name: str,
        pre_req_build: Callable[[dict], dict] = lambda r, _: r,
        callback: Callable[[Response], Any] = lambda r: r
    ) -> Callable:
        def wrapper(req_builder: RequestBuilder):
            self.scrapers[name] = make_scraper(
                self,
                req_builder, 
                pre_req_build=pre_req_build, 
                callback=callback
            )
            return self.scrapers[name]
            # print("Scraper registered: {}".format(name))
        return wrapper

    def load_scraper_module(self, name: str, module: ScraperModuleBase) -> None:
        super().load_scraper_module(name, module)
        module.set_engine(self)

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
            

T = TypeVar('T')
RequestBuilder = Callable[[ScrapingEngineBase, Any], Union[dict, Iterable]]


@dataclass
class RequestSenderBase():

    engine: ScrapingEngineBase

    req_builder: RequestBuilder
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
