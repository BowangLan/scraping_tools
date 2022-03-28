from __future__ import annotations
import json
import os
from rich import print
import httpx
from dataclasses import dataclass, field, asdict
from typing import *





def get_multiple_input(pop):
    print(pop)
    inp = ''
    while True:
        temp_in = input().strip(' ')
        if temp_in == '':
            break
        inp += temp_in + '\n'
    return inp


class HarAnalyser(object):
    """A HAR object analyzer. 
    A HAR object is a json object containing a list of request and response information captured during
    the network traffic capturing. Each entry in a HAR object represents a request captured, with
    all the information about the request and response except for the response data.

    This class is designed to programmatically analyze website traffic, which is usually done 
    using the browser inspector. Such tasks include:

     - filtering entries based on request resource type
     - filtering entries based on response content type
     - get entries containing certain strings (global search)
     - extract request parameters from an entry, which can be used to make the request with the
     exact url, payload, and headers, etc. in an ioslated environment

    Can be used to automate things when analysing the network traffic of a website.
    """
    def __init__(self):
        self.har = {}

    def load_from_file(self, filename: str):
        if not os.path.exists(filename):
            print(f'{filename} does not exist')
            return
        
        with open(filename, 'r') as f:
            self.har = json.load(f)
            self.entries = EntryList(self.har['log']['entries'])
            print("HAR loaded from {}. Entry count: {}".format(filename, len(self.entries)))




@dataclass
class EntryList:

    data: list[Entry]

    def __post_init__(self):
        for i,e in enumerate(self.data):
            if isinstance(e, dict):
                self.data[i] = Entry(**e)

    def __len__(self):
        return len(self.data)


    def __getitem__(self, key):
        return self.data[key]

    def __iter__(self):
        for e in self.data:
            yield e

    def global_search(self, term: str) -> Iterable[Entry]:
        for e in self.data:
            if term in str(asdict(e)):
                yield e





@dataclass
class Entry:

    _initiator: str
    _priority: str 
    _resourceType: str 
    cache: dict 
    request: Request
    response: Response
    serverIPAddress: str
    startedDateTime: str
    time: float
    timings: dict

    pageref: str = None
    _fromCache: str = None
    connection: str = None
    _webSocketMessages: str = None

    def __post_init__(self):
        if isinstance(self.request, dict):
            self.request = Request(**self.request)
        if isinstance(self.response, dict):
            self.response = Response(**self.response)

    @property
    def request_headers(self):
        return self.request['headers']

    @property
    def response_headers(self):
        return self.response['headers']

    @property
    def status(self):
        return self.response.status

    @property
    def url(self):
        return self.request.url

    @property
    def url_without_params(self):
        return self.url.split('?')[0]

    @property
    def method(self):
        return self.request.method

    @property
    def resource_type(self):
        return self._resourceType

    @property
    def response_content_type(self):
        return self.response.headers.get('content-type')

    def print_info(self):
        print(f"[{self.method} {self.status} {self.resource_type}] {e.url_without_params}")

    def find_set_cookie_headers(self):
        return list(filter(lambda h: h['name'] == 'set-cookie', self.response.headers.data))
    
    def have_set_cookie(self):
        t = self.find_set_cookie_headers()
        return len(t) != 0

    def is_response_json(self):
        return self.response_content_type and 'application/json' in self.response_content_type

    def build_request_params(self):
        params = {
            'method': self.request.method,
            'url': self.request.url,
            'headers': {h['name']: h['value'] for h in self.request.headers.filter_comma_start()}
        }
        return params
    
    def mimic(self) -> httpx.Response:
        params = self.build_request_params()
        client = httpx.Client()
        req = client.build_request(**params)
        res = client.send(req)
        return res




@dataclass
class Request:
    method: str
    url: str
    httpVersion: str
    headers: Headers
    queryString: str
    cookies: list
    headersSize: int
    bodySize: int
    postData: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.headers, list):
            self.headers = Headers(data=self.headers)



@dataclass
class Response:
    status: str
    statusText: str
    httpVersion: str
    headers: Headers
    content: dict
    redirectURL: str
    headersSize: int
    bodySize: int
    _transferSize: int
    cookies: list
    _error: str

    def __post_init__(self):
        if isinstance(self.headers, list):
            self.headers = Headers(data=self.headers)


ignore_headers = [
    'accept', 'accept-language', 'accept-encoding', 
    'sec-ch-ua', 'sec-ch-ua-platform', 'sec-fetch-site', 'sec-fetch-mode', 'sec-fetch-dest', 'sec-ch-ua-mobile', 
    'referer', 'host', 'user-agent',
    ':method', ':authority', ':scheme', ':path'
]

ignore_headers_when_build_request = [
    ':method', ':authority', ':scheme', ':path'
]

@dataclass
class Headers:
    data: list

    def to_tuples(self):
        return [(i['name'], i['value']) for i in self.data]

    def to_dict(self):
        return {i['name']: i['value'] for i in self.data}

    def filter_bording(self):
        return filter(lambda h: h['name'].lower() not in ignore_headers, self.data)

    def filter_comma_start(self):
        return filter(lambda h: h['name'][0] != ':', self.data)

    def get(self, name: str, many: bool = False):
        t = list(filter(lambda h: h['name'].lower() == name.lower(), self.data))
        if t:
            return map(lambda h: h['value'], t) if many else t[0]['value']


# har_string = get_multiple_input('Enter HAR string:')

def headers_list_to_dict(headers: list[dict]):
    output = {i['name']: i['value'] for i in headers}
    return output

def headers_list_to_tuple(headers: list[dict]):
    return [(i['name'], i['value']) for i in headers]

def get_headers_with_set_cookie(headers: list):
    return list(filter(lambda h: h['name'] == 'set-cookie', headers))


def get_entries_with_set_cookie(entries: list):
    e_with_set_cookie = []
    for e in entries:
        h_with_set_cookie = get_headers_with_set_cookie(e['response']['headers'])
        if h_with_set_cookie:
            e_with_set_cookie.append(e)
    print("Entries with set-cookie: {}".format(len(e_with_set_cookie)))
    for e in e_with_set_cookie:
        print(format_entry_status_url(e))
        print(headers_list_to_dict(e['response']['headers']))
        print(e['response']['headers'])


def format_entry_status_url(e):
    return f"[{e['request']['method']} {e['response']['status']} {e['_resourceType']}] {e['request']['url']}"


def print_interesting_headers(headers):
    h = headers_list_to_tuple(headers)
    h = list(filter(lambda h: h[0].lower() not in ignore_headers, h))
    print(h)


def print_all_res(entries, with_res_h=False, with_req_h=False, filter_key=None):
    def print_one(e):
        print(format_entry_status_url(e))
        if with_req_h:
            print_interesting_headers(e['request']['headers'])
            # print(headers_list_to_tuple(e['response']['headers']))
        if with_res_h:
            print_interesting_headers(e['response']['headers'])
            # print(headers_list_to_tuple(e['response']['headers']))
        
    if filter_key:
        for e in filter(filter_key, entries):
            print_one(e)
    else:
        for e in entries:
            print_one(e)


########################################################################
# filter keys
########################################################################

def entry_with_type(t: str):
    return lambda e: e['_resourceType'] == t

def entry_type_fetch():
    return entry_with_type('fetch')


def find_headers_by_value(headers, name, value):
    return list(filter(lambda h: h['name'] == name and h['value'] == value, headers))

def entry_response_json():
    def f(e):
        t = find_headers_by_value(e['response']['headers'], 'content-type', 'application/json')
        return t
    return f

def entry_response_document():
    return lambda e: e['_resourceType'] == 'document'

def global_search(term):
    return lambda e: term in str(e)

def chain_lambda(ls: list):
    def f(e):
        output = True
        for l in ls:
            output = output and l(e)
            if not output:
                break
        return output
    return f


def build_request_params_from_entry(e):
    params = {
        'method': e['request']['method'],
        'url': e['request']['url'],
        'headers': {h['name']: h['value'] for h in e['request']['headers'] if h['name'] not in ignore_headers_when_build_request}
    }
    return params


with open('har1.json', 'r') as f:
    pass
    # har = json.load(f)
    # entries = EntryList(har['log']['entries'])

    # for e in entries.global_search('https://www.freelancer.com/api/projects/0.1/projects?atta'):
    #     e.print_info()
        # print(list(e.request.headers.filter_bording()))
        # print(e.build_request_params())

    # for e in entries.data:
    #     if e.is_response_json():
    #         e.print_info()

    # print_all_res(entries, with_req_h=True, filter_key=global_search('https://www.freelancer.com/api/projects/0.1/projects?atta'))


    # parse_har(har)
    # get_entries_with_set_cookie(har['log']['entries'])

    # print_all_res(entries, filter_key=entry_response_json())
    

    # es = list(filter(global_search('https://www.freelancer.com/api/projects/0.1/projects?atta'), entries))
    # e1 = es[0]
    # params = build_request_params_from_entry(e1)
    # print(params)
    # client = httpx.Client()
    # req = client.build_request(**params)
    # res = client.send(req)
    # print(res)
    # print(res.text)


ha = HarAnalyser()
ha.load_from_file('har1.json')

for e in ha.entries.global_search('https://www.freelancer.com/api/projects/0.1/projects?atta'):
    e.print_info()
    # print(list(e.request.headers.filter_bording()))
    # print(e.build_request_params())

for e in ha.entries:
    if e.is_response_json():
        e.print_info()