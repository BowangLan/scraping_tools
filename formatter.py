import sys
from rich import print
import pyperclip


def parse_cookies(cookie_string):
    output = {}
    for c in cookie_string.split('; '):
        name, *value = c.split('=')
        output[name] = '='.join(value)
    print(output)
    return output


def parse_headers(header_string):
    output = {}
    for c in header_string.split('\n'):
        c = c.strip()
        if not c:
            continue
        name, *value = c.split(': ')
        output[name] = '='.join(value)
    print(output)
    pyperclip.copy(str(output))
    print("Copied to clipboard")
    return output


def get_multiple_input(pop):
    print(pop)
    inp = ''
    while True:
        temp_in = input().strip(' ')
        if temp_in == '':
            break
        inp += temp_in + '\n'
    return inp


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'h':
        user_input = get_multiple_input('Please enter header strings:')
        parse_headers(user_input)
    elif c == 'c':
        user_input = get_multiple_input('Please enter cookie strings:')
        parse_cookies(user_input)
    else:
        print("Invalid argument! Must be either 'c' or 'h'")
