from scraping_tools.util import *
from bs4 import BeautifulSoup
from httpx import AsyncClient, Client, Response, Request
import asyncio
from rich import print
import os
import lxml.html
from bs4 import BeautifulSoup
import sys

if __name__ == '__main__':
    client = create_aclient(logs=['log_res', 'log_req_h'], sync=True)
    if len(sys.argv) > 1:
        url = sys.argv[1]
        res = client.get(url)
        soup = BeautifulSoup(res.text, 'lxml')
        tree = lxml.html.fromstring(res.text)
