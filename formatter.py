import sys
from rich import print
import pyperclip


def print_number_with_base(size, unit_size: int = 1024, unit: str = 'B', current: str = ''):
    if size < unit_size ** 1:
        pass
    elif size < unit_size ** 2:
        unit = 'K' + unit
        size = float(size) / unit_size
    elif size < unit_size ** 3:
        unit = 'M' + unit
        size = float(size) / unit_size ** 2
    elif size < unit_size ** 4:
        unit = 'G' + unit
        size = float(size) / unit_size ** 3
    elif size < unit_size ** 5:
        unit = 'T' + unit
        size = float(size) / unit_size ** 4
    else:
        return size
    return '%.2f %s' % (size, unit)


def format_cookie_string(cookie_string: str) -> dict:
    output = {}
    for c in cookie_string.split('; '):
        name, *value = c.split('=')
        output[name] = '='.join(value)
    print(output)
    return output


def format_header_string(header_string: str) -> dict:
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
        format_header_string(user_input)
    elif c == 'c':
        user_input = get_multiple_input('Please enter cookie strings:')
        format_cookie_string(user_input)
    else:
        print("Invalid argument! Must be either 'c' or 'h'")
