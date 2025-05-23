from .utils import _Attribute, _Comment, _parse
from .dom import COMMENT, DOCUMENT_TYPE, TEXT, ELEMENT, FRAGMENT
from .dom import Node, Comment, DocumentType, Text, Element, Fragment, parse, unsafe, _clone


_parsed = {}
_listeners = []

# T = (t'').__class__
# Let's just use the imported class
try:
  # Temporary hack because pytest-playwright has to run under 3.13
  # in CI due to greenlet not compiling there under 3.14.
  from string.templatelib import Template
except ImportError:
  pass

def _util(svg):
  def fn(t):
    if not isinstance(t, Template):
      raise ValueError('Argument is not a Template instance')

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
  'render', 'html', 'svg', 'parse', 'unsafe',
  'Node', 'Comment', 'DocumentType', 'Text', 'Element', 'Fragment',
  'COMMENT', 'DOCUMENT_TYPE', 'TEXT', 'ELEMENT', 'FRAGMENT',
]
