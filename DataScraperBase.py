from __future__ import annotations
from abc import ABC, abstractmethod
from typing import *
from httpx import Response, Request, Client, AsyncClient
import datetime
from .util import get_ua 



class DataScraperBase(object):
    """The base class for a data scraper.
    A data scraper is an object that encapsolate the various scraping logic, and use a
    intuitive way to represent scraping information. 

    Args:
        object (_type_): _description_
    """
    # states of the scraper, these these can be automatically loaded and saved.
    states: list = []

    # output path of the saved data file
    path: str = ''

    event_hooks = {
        'on_request': [],
        'on_response': [],
    }

    def __init__(self, 
                 client,
                 path: str = None, 
                 data_store: any = None):
        cls = self.__class__
        self.client = client
        self.path = path if path else cls.path
        self.data_store = data_store

        self.break_hook = False

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def build_request(self, *args, **kwargs) -> Request:
        pass

    def doit(self, *args, **kwargs):
        req = self.build_request(*args, **kwargs)
        res = self.client.send(req)

        for hook in self.event_hooks['on_response']:
            try:
                res = hook(res)
            except:
                break

        output = []
        for item in res:
            temp = {}

            if self.field == []:
                temp.update(item)

            else:
                for field in self.fields:
                    if not field.get('source_name'):
                        field['source_name'] = field['name']
                    v = getattr(item, field['input_name'],
                                field.get('default'))
                    setattr(temp, field['name'], v)

            output.append(temp)
        self.update_many(output)
        return output

    def should_update_item(self, item: any) -> bool:
        return True

    def update_many(self, data: list) -> None:
        for item in data:
            if not self.should_update_item(item):
                continue
            self.update_one(item)

    def create_if_not_exist(self, item: any) -> bool:
        t = self.get_one(item)
        if not t:
            self.data_store.create_one(t)
            return True

    def get_one(self, item: any) -> any:
        return self.data_store.get_one(item)

    def save(self, data: list) -> None:
        self.data_store.save(data)

    def save_one(self, item: any) -> None:
        self.data_store.save(item)

