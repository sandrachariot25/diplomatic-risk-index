"""Minimal HTML tree; extraction fails closed when page structure changes."""
from html.parser import HTMLParser
from dataclasses import dataclass, field

@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def find(self, tag=None, cls=None, id=None):
        result = []
        if ((tag is None or self.tag == tag)
            and (cls is None or cls in self.attrs.get('class', '').split())
            and (id is None or self.attrs.get('id') == id)):
            result.append(self)
        for child in self.children:
            if isinstance(child, Node):
                result.extend(child.find(tag, cls, id))
        return result

    def text(self):
        if self.tag in {'script', 'style', 'nav'}:
            return ''
        if self.tag == 'br':
            return '\n'
        value = ''.join(c.text() if isinstance(c, Node) else c for c in self.children)
        if self.tag in {'p', 'div', 'li', 'h1', 'h2', 'h3', 'dt', 'dd', 'section'}:
            value = '\n' + value + '\n'
        return value

class Tree(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)

def clean(text):
    return '\n'.join(' '.join(line.split()) for line in text.splitlines() if line.strip())

def one(nodes, description):
    if len(nodes) != 1:
        raise ValueError(f'Expected one {description}, got {len(nodes)}')
    return nodes[0]
