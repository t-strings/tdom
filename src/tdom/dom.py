from html.parser import HTMLParser
from html import escape
from random import random
import re


_prefix = 't🐍' + str(random())[2:5]
_data = f'<!--{_prefix}-->'


ELEMENT = 1
ATTRIBUTE = 2
TEXT = 3
CDATA = 4
# ENTITY_REFERENCE = 5
# ENTITY = 6
# PROCESSING_INSTRUCTION = 7
COMMENT = 8
# DOCUMENT = 9
DOCUMENT_TYPE = 10
FRAGMENT = 11
# NOTATION = 12



TEXT_ELEMENTS = (
  'plaintext',
  'script',
  'style',
  'textarea',
  'title',
  'xmp',
)


VOID_ELEMENTS = (
  'area',
  'base',
  'br',
  'col',
  'embed',
  'hr',
  'img',
  'input',
  'keygen',
  'link',
  'menuitem',
  'meta',
  'param',
  'source',
  'track',
  'wbr',
)



class Props(dict):
  def __init__(self, props):
    super().__init__(props)

  def __getattr__(self, name):
    return self[name] if name in self else None


class Node(dict):
  def __init__(self, **kwargs):
    super().__init__(type=self.type, **kwargs)
    self.parent = None

  def __getattr__(self, name):
    return self[name] if name in self else None


class Comment(Node):
  type = COMMENT

  def __init__(self, data):
    super().__init__(data=data)

  def __str__(self):
    return f'<!--{escape(str(self['data']))}-->'


class DocumentType(Node):
  type = DOCUMENT_TYPE

  def __init__(self, data):
    super().__init__(data=data)

  def __str__(self):
    return f'<!{self['data']}>'


class Text(Node):
  type = TEXT

  def __init__(self, data):
    super().__init__(data=data)

  def __str__(self):
    return escape(str(self['data']))


class Element(Node):
  type = ELEMENT

  def __init__(self, name, xml=False):
    super().__init__(name=name, xml=xml, props={}, children=[])

  def __str__(self):
    xml = self['xml']
    name = self['name']
    html = f'<{name}'
    for key, value in self['props'].items():
      if value != None:
        if isinstance(value, bool):
          if value:
            html += f' {key}=""' if xml else f' {key}'
        else:
          html += f' {key}="{escape(str(value))}"'
    if len(self['children']) > 0:
      html += '>'
      just_text = not xml and name.lower() in TEXT_ELEMENTS
      for child in self['children']:
        html += child['data'] if just_text else str(child)
      html += f'</{name}>'
    elif xml:
      html += ' />'
    else:
      html += '>'
      if not name.lower() in VOID_ELEMENTS:
        html += '</' + name + '>'
    return html


class Fragment(Node):
  type = FRAGMENT

  def __init__(self):
    super().__init__(children=[])

  def __str__(self):
    return ''.join(str(child) for child in self['children'])



def _append(parent, node):
  parent['children'].append(node)
  node.parent = parent


def _appendChildren(parent, nodes, clone=False):
  children = parent['children']
  for node in nodes:
    if clone:
      node = _clone(node)
    children.append(node)
    node.parent = parent


def _clone(node):
  type = node['type']
  if type == FRAGMENT:
    fragment = Fragment()
    _appendChildren(fragment, node['children'], True)
    return fragment
  if type == ELEMENT:
    element = Element(node['name'], node['xml'])
    element['props'] = node['props'].copy()
    _appendChildren(element, node['children'], True)
    return element
  if type == TEXT:
    return Text(node['data'])
  if type == COMMENT:
    return Comment(node['data'])
  if type == DOCUMENT_TYPE:
    return DocumentType(node['data'])


def _replaceWith(current, node):
    parent = current.parent
    children = parent['children']
    children[children.index(current)] = node
    node.parent = parent
    current.parent = None



class DOMParser(HTMLParser):
  def __init__(self, xml=False):
    super().__init__()
    self.xml = xml
    self.node = Fragment()

  def handle_starttag(self, tag, attrs):
    element = Element(tag, self.xml)
    _append(self.node, element)
    self.node = element
    props = element['props']
    for name, value in attrs:
      props[name] = value

  def handle_endtag(self, tag):
    parent = self.node.parent
    if parent:
      self.node = parent

  def handle_data(self, data):
    # this is needed to handle sparse interpolations
    # within <style> or <script> tags where this parser
    # won't allow children nodes and it passes all as data
    text = data.split(_data)
    for i in range(len(text) - 1):
      # empty nodes are ignored
      if len(text[i].strip()) > 0:
        _append(self.node, Text(text[i]))
      # the comment node though is needed to handle updates
      _append(self.node, Comment(_prefix))

    # same applies for the last node
    if len(text[-1].strip()) > 0:
      _append(self.node, Text(text[-1]))

  def handle_comment(self, data):
    if data == '/':
      self.handle_endtag(self.node['name'])
    else:
      _append(self.node, Comment(data))

  def handle_decl(self, data):
    _append(self.node, DocumentType(data))

  def unknown_decl(self, data):
    raise Exception(f'Unknown declaration: {data}')


def parse(content, xml=False):
  parser = DOMParser(xml)
  parser.feed(content)
  return parser.node
