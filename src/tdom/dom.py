from html.parser import HTMLParser
from html import escape
import re


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

# TODO: style,script,textarea,title,xmp are nodes which content is not escaped
#       and it cannot contain interpolations right now but these need to be handled

VOID_ELEMENTS = re.compile(
  r'^(?:area|base|br|col|embed|hr|img|input|keygen|link|menuitem|meta|param|source|track|wbr)$',
  re.IGNORECASE
)



class Node(dict):
  def __init__(self, **kwargs):
    super().__init__(type=self.type, **kwargs)
    self.parent = None

  def __getattribute__(self, name):
    return self[name] if name in self else super().__getattribute__(name)


class Comment(Node):
  type = COMMENT

  def __init__(self, data):
    super().__init__(data=data)

  def __str__(self):
    return f"<!--{escape(str(self['data']))}-->"


class DocumentType(Node):
  type = DOCUMENT_TYPE

  def __init__(self, data):
    super().__init__(data=data)

  def __str__(self):
    return f"<!{self['data']}>"


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
    name = self['name']
    html = f"<{name}"
    for key, value in self['props'].items():
      if value != None:
        if isinstance(value, bool):
          if value:
            html += f" {key}"
        else:
          html += f" {key}=\"{escape(str(value))}\""
    if len(self['children']) > 0:
      html += ">"
      for child in self['children']:
        # TODO: handle <title> and others that don't need/want escaping
        html += str(child)
      html += f"</{name}>"
    elif self['xml']:
      html += " />"
    else:
      html += ">"
      if not VOID_ELEMENTS.match(name):
        html += "</" + name + ">"
    return html


class Fragment(Node):
  type = FRAGMENT

  def __init__(self):
    super().__init__(children=[])

  def __str__(self):
    return "".join(str(child) for child in self['children'])



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
    # TODO Test if current.parent is None before doing the following
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
    _append(self.node, Text(data))

  def handle_comment(self, data):
    if data == '/':
      self.handle_endtag(self.node['name'])
    else:
      _append(self.node, Comment(data))

  def handle_decl(self, data):
    _append(self.node, DocumentType(data))

  def unknown_decl(self, data):
    raise Exception(f"Unknown declaration: {data}")


def parse(content, xml=False):
  parser = DOMParser(xml)
  parser.feed(content)
  return parser.node
