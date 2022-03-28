from __future__ import annotations
from dataclasses import dataclass, field
import lxml.html


@dataclass
class Item:

    fields: list[ItemField]
    # combine_fields: list = field(default_factory=list)
    combine_fields: list[dict] = field(default_factory=list)
    root_xpath: str = None

    def extract_from_tree(self, tree):
        output = {f.name: f.extract_from_tree(tree) for f in self.fields}
        for c in self.combine_fields:
            valid = True
            l = len(output[c.fields[0]])
            for f in c.fields:
                valid = len(output[f]) == l
                if not valid:
                    break
            if valid:
                c_output = [
                    {f: output[f][i] for f in c.fields}
                    for i in range(l)
                ]
                output[c.name] = c_output
                for f in c.fields:
                    del output[f]
        return output




@dataclass
class ItemField:

    name: str
    xpath: str
    first: bool = False
    default: str = None
    post: any = None

    def extract_from_tree(self, tree):
        temp = tree.xpath(self.xpath)
        if len(temp) == 0:
            # print('No result for {}'.format(self.xpath))
            return self.default
        else:
            temp = temp if not self.first else temp[0]
            if self.post:
                temp = self.post(temp)
            return temp



def make_item_extractor(item: Item):
    def extractor(tree):
        return extract_item_list_from_tree(tree, item)
    return extractor



def extract_item_list_from_tree(tree, item):
    if item.root_xpath != None:
        f_values = {f.name: f.extract_from_tree(tree) for f in item.fields}
        output = [
            {f.name: f.extract_from_tree(i) for f in item.fields}
            for i in tree.xpath(item.root_xpath)
        ]
        return output
    else:
        f_values = {}
        for f in item.fields:
            t = f.extract_from_tree(tree)
            if t != None:
                f_values[f.name] = t

    if f_values == {}:
        return None

    iv = len(list(f_values.values())[0])
    valid = True
    for i in f_values.values():
        if not iv == len(i):
            valid = False
            break
    if not valid:
        return

    output = [
        {f.name: f_values[f.name][i] for f in item.fields}
        for i in range(iv)
    ]

    return output
