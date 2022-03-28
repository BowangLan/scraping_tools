import timeit
from httpx import AsyncClient, Client, Response
import dateutil.parser
import requests
import pickle
from rich import print
import random
from bs4 import Tag
from typing import *
from .assets import *
import re


def with_client(func):
    def wrapper(*args, client: requests.Session = None, **kwargs):
        if not client:
            print('Client not specified')
            return
        res = func(*args, client=client, **kwargs)
        return res
    return wrapper


def load_cookie(client: AsyncClient, cookie_filename):
    with open(cookie_filename, 'rb') as f:
        client.cookies.update(pickle.load(f))


def save_cookie(cookie_jar, cookie_filename):
    with open(cookie_filename, 'wb') as f:
        pickle.dump(cookie_jar, f)


def try_select(
    source: Union[str, Tag],
    target: str,
    default: str = '',
    default_factory: Callable = None,
    first: bool = True,
    post=lambda x: x
) -> any:
    if isinstance(source, Tag):
        t = source.select(target)
    elif isinstance(source, str):
        t = re.findall(target, source)
    else:
        print("Unsupported source type: %s" % type(source))
        return None
    if t:
        try:
            if first:
                return post(t[0])
            else:
                return post(t)
        except Exception as e:
            print(e)
            return default_factory() if default_factory else default
    else:
        return default


def try_soup_select_text(soup, selector: str, **kwargs):
    return try_select(soup, selector, post=lambda x: x.text.strip(), **kwargs)


def try_soup_select_link(soup, selector: str, **kwargs):
    return try_select(soup, selector, post=lambda x: x['href'], **kwargs)


def with_timeit(func):
    def wrapper(*args, **kwargs):
        start = timeit.default_timer()
        func(*args, **kwargs)
        duration = timeit.default_timer() - start
        print("Finish in {:.2f} seconds".format(duration))
    return wrapper


def with_async_timeit(func):
    async def wrapper(*args, **kwargs):
        start = timeit.default_timer()
        await func(*args, **kwargs)
        duration = timeit.default_timer() - start
        print("Finish in {:.2f} seconds".format(duration))
    return wrapper


def parse_iso_datetime(dt_string):
    return dateutil.parser.isoparse(dt_string).replace(tzinfo=None)




def get_ua():
    return random.choice(ua)


def log_response(res: Response):
    print(f"[{res.status_code}] {res.url}")


def log_response_headers(res: Response):
    print(dict(res.headers.items()))


def log_req_headers(res: Response):
    print(dict(res.request.headers.items()))


async def alog_response(res: Response):
    print(f"[{res.status_code}] {res.url}")


async def alog_response_headers(res: Response):
    print(dict(res.headers.items()))


async def alog_req_headers(res: Response):
    print(dict(res.request.headers.items()))


async_hook_to_function = {
    'log_res': alog_response,
    'log_res_h': alog_response_headers,
    'log_req_h': alog_req_headers,
}

sync_hook_to_function = {
    'log_res': log_response,
    'log_res_h': log_response_headers,
    'log_req_h': log_req_headers,
}


def create_aclient(logs: list = ['log_res'], sync: bool = False, **kwargs):
    """Creates a AsyncClient object with user-agent and even hooks configured.

    Parameters:
     - `logs` (list, optional): a list of event hook names to be added. Defaults to ['log_res']. 
        Available hooks names:
         `log_res` - print status code and url of each response
         `log_res_h` - print the headers of each response
         `log_req_h` - print the headers of each request upon a response
    """
    res_hooks = []
    hook_map = async_hook_to_function if not sync else sync_hook_to_function

    for k in logs:
        if k not in hook_map:
            continue
        res_hooks.append(hook_map[k])

    return AsyncClient(
        event_hooks={'response': res_hooks},
        headers={
            'user-agent': random.choice(ua)
        },
        **kwargs
    ) if not sync else Client(
        event_hooks={'response': res_hooks},
        headers={
            'user-agent': random.choice(ua)
        },
        **kwargs
    )
