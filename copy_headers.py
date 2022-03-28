import re
import pyperclip
from rich import print


def replace_header():
    print('Enter headers: (double enter to finish entering)')
    string = ''
    for s in iter(input, ''):  # 引号里面是空行结束标记，为空就直接回车
        # 第二个分组前面也许有0个或1个空格，但是不提取,\1表示提取第一组内容\2以此类推
        s = re.sub("(.*?):[\s]{0,1}(.*)", r"'\1': '\2',", s)
        string += ('\t'+s + '\n')
    headers = 'headers = {\n' + string + '}'
    pyperclip.copy(headers)  # 复制到剪切板
    print(headers)
    print("Copied formatted headers to clipboard")


def main():
    replace_header()


if __name__ == '__main__':
    main()
