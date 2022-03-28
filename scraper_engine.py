from __future__ import annotations
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from scraping_tools.util import create_aclient
import asyncio
import lxml.html
from httpx import Response, Client, AsyncClient
from httpx._client import UseClientDefault, USE_CLIENT_DEFAULT
from typing import *



def transform_dict_wrapper(transform_fields: dict):
    def wrapper(data):
        temp = data.copy()
        for k, v in data.items():
            if k in transform_fields.keys():
                new_k = transform_fields[k]
                temp[new_k] = v
                del temp[k]
        return temp
    return wrapper


def transform_list_wrapper(transform_fields: dict):
    def wrapper(data):
        tr = transform_dict_wrapper(transform_fields)
        return [tr(i) for i in data]
    return wrapper


def filter_allow_dict_wrapper(fields: list):
    def wrapper(data):
        temp = {}
        for k, v in data.items():
            if k in fields:
                temp[k] = v
        return temp
    return wrapper


def filter_allow_list_of_dict_wrapper(fields: list):
    def wrapper(data):
        f = transform_dict_wrapper(fields)
        return [f(i) for i in data]
    return wrapper


def before_parse_lxml(res):
    return [lxml.html.fromstring(r.text) if res else res for r in res]


def before_parse_soup(res):
    return [BeautifulSoup(r.text, 'lxml') if res else res for r in res]


pre_parser_mapping = {
    'soup': before_parse_soup,
    'lxml': before_parse_lxml,
    '': lambda res: res,
}

class ScrapingEngineBase(object):
    """This class represents a scraping engine that starts a list of scrapers.

    This class also provides an environment (a configured client) for any scraper 
    instance.
    """

    initial_static_headers = {}
    header_set = {}
    scrapers = []
    workflows = []

    def __init__(self, cookie: str = '', client_kw={}):
        self.client: AsyncClient = create_aclient(**client_kw)

        self.client.headers.update(self.initial_static_headers)

        if cookie:
            self.client.headers.update({'cookie': cookie})

        for s in self.scrapers:
            s_ins = s(self)
            setattr(self, s_ins.method_name, self.scraper_wrapper(s_ins))

    async def aclose(self):
        await self.client.aclose()

    def scraper_wrapper(self, s_ins):
        """Return a method for scraping given a scraper instance, 

        A scraper instance contains information about how to make the request, how to parse
        the response, etc.

        Return returned scraping method serves as the actual api call, which takes in a dictionary
        of user keyword arguments and return the scraped data.
        """

        async def starter(*args, **kwargs):
            req_list = [r for r in s_ins.start(*args, **kwargs)]
            for r in req_list:
                if 'pre_parser' not in r.keys():
                    r['pre_parser'] = s_ins.pre_parser
            res = await asyncio.gather(*[
                self._scrape_one_req(
                    req, i,
                    callback=getattr(s_ins, 'parse_one', None)
                ) for i, req in enumerate(req_list)])

            single = len(res) == 1

            # attach the raw response to the scraper instance
            s_ins.res = res[0] if single else res

            if not s_ins.validate_response():
                return None

            res = self._pre_parse(s_ins.pre_parser, res)

            res = s_ins.parse(res if not single else res[0])

            for h in s_ins.post_hooks:
                res = h(res)

            return res
        return starter

    async def _scrape_one_req(self, req_params, i: int, callback=None):
        if 'header_set_name' in req_params.keys() and req_params['header_set_name'] in self.header_set:
            req_params['headers'] = self.header_set[req_params['header_set_name']]
            del req_params['header_set_name']

        del req_params['pre_parser']

        req = self.client.build_request(**req_params)
        res = await self.client.send(req)

        if callback:
            return callback(res, i)
        return res

    def _pre_parse(self, pre_parser: str, res: Response):
        if pre_parser not in pre_parser_mapping.keys():
            print("{} pre parser not supported".format(pre_parser))
            pre_parser = ''
        return pre_parser_mapping[pre_parser](res)


@dataclass
class ScraperList():

    items: List[ScraperBase]
    sync: bool = True

    post_hooks = []
    parse: Callable[[list[Any]], Any] = field(default=lambda l: l)

    def __iter__(self):
        for i in self.items:
            yield i

    def __len__(self):
        return len(self.items)

    
    async def start(self, **kwargs):
        if self.sync:
            res = []
            for s in self.items:
                t = await s.do(**kwargs)
                res.append(t)
        else:
            res = await asyncio.gather(*[s.start(**kwargs) for s in self.items])
        return res
            

class ScraperBase():

    post_hooks = []
    pre_parser = ''

    def __init__(self, engine):
        self.engine = engine

    def start(self, **kwargs):
        pass

    def parse(self, res):
        return res

    def validate_response(self):
        if isinstance(self.res, Response):
            if self.res.status_code != 200:
                print("{} Error: {}".format(
                    self.__class__.__name__, self.res.status_code))
                return False
        return True


class WorkflowBase():

    def __init__(self, engine):
        self.engine = engine

    def start(self):
        pass
