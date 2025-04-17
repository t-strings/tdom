from .dom import VOID_ELEMENTS, _prefix
import re


_elements = re.compile(
  '<(\x01|[a-zA-Z0-9]+[a-zA-Z0-9:._-]*)([^>]*?)(/?)>',
)

_attributes = re.compile(
  r'([^\s\\>\'"=]+)\s*=\s*([\'"]?)' + '\x01',
)

_holes = re.compile(
  '[\x01\x02]',
)


def _as_attribute(match):
  return f'\x02={match.group(2)}{match.group(1)}'


def _as_closing(name, xml, self_closing):
  if len(self_closing) > 0:
    if xml or name.lower() in VOID_ELEMENTS:
      return ' /'
    else:
      return f'></{name}'
  return ''

# \x01 Node.ELEMENT_NODE
# \x02 Node.ATTRIBUTE_NODE

def _instrument(template, xml):
  def pin(match):
    name = match.group(1)
    if name == '\x01':
      name = _prefix
    attrs = match.group(2)
    self_closing = match.group(3)
    return f'<{
      name
    }{
      re.sub(_attributes, _as_attribute, attrs).rstrip()
    }{
      _as_closing(name, xml, self_closing)
    }>'

  def point():
    nonlocal i
    i += 1
    return _prefix + str(i - 1)

  i = 0
  return re.sub(
    _holes,
    lambda match: f'<!--{_prefix}-->' if match.group(0) == '\x01' else point(),
    re.sub(
      _elements,
      pin,
      '\x01'.join(template).strip().replace('</>', '<//>')
    )
  )
