from .utils import _Attribute, _Comment, _parse
from .dom import COMMENT, DOCUMENT_TYPE, TEXT, ELEMENT, FRAGMENT
from .dom import Props, Node, Comment, DocumentType, Text, Element, Fragment, DOMParser, parse, _clone


_parsed = {}
_listeners = []


def _util(svg):
  def fn(t):
    strings = t.strings

    values = [entry.value for entry in t.interpolations]

    length = len(values)

    if not strings in _parsed:
      _parsed[strings] = _parse(strings, length, svg)

    content, updates = _parsed[strings]

    node = _clone(content)
    changes = []
    path = None
    child = None
    i = 0

    for update in updates:
      if path != update.path:
        path = update.path
        child = node
        for index in path:
          child = child['children'][index]

      if isinstance(update.value, _Attribute):
        changes.append(update.value(child, _listeners))
      elif isinstance(update.value, _Comment):
        changes.append(update.value(child))
      else:
        changes.append(update.value(child, changes))

    for i in range(length):
      changes[i](values[i])

    for i in range(len(changes) - 1, length - 1, -1):
      changes[i]()

    return node

  return fn


def render(where, what):
  result = where(what() if callable(what) else what, _listeners)
  _listeners.clear()
  return result

html = _util(False)
svg = _util(True)


__all__ = [
  'render', 'html', 'svg',
  'DOMParser', 'parse',
  'Props', 'Node', 'Comment', 'DocumentType', 'Text', 'Element', 'Fragment',
  'COMMENT', 'DOCUMENT_TYPE', 'TEXT', 'ELEMENT', 'FRAGMENT',
]
