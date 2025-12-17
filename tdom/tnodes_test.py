import pytest

from .template_utils import TemplateRef
from .tnodes import TComment, TNode, TText


def test_tnode_abstract_methods() -> None:
    node = TNode()
    with pytest.raises(NotImplementedError):
        _ = node.__html__()
    with pytest.raises(NotImplementedError):
        _ = node.__str__()


def test_ttext_literal() -> None:
    text = "Hello, World!"
    ttext = TText.literal(text)
    assert ttext.ref == TemplateRef.literal(text)


def test_ttext_empty() -> None:
    ttext = TText.empty()
    assert ttext.ref == TemplateRef.empty()


def test_tcomment_literal() -> None:
    comment = "This is a comment"
    tcomment = TComment.literal(comment)
    assert tcomment.ref == TemplateRef.literal(comment)
