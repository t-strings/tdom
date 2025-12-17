from .utils import CachableTemplate, LastUpdatedOrderedDict


def test_last_updated_ordered_dict() -> None:
    loudict: dict[int, str] = LastUpdatedOrderedDict()
    loudict[1] = "one"
    loudict[2] = "two"
    loudict[3] = "three"
    assert list(loudict.keys()) == [1, 2, 3]

    loudict[2] = "TWO"
    assert list(loudict.keys()) == [1, 3, 2]

    loudict[1] = "ONE"
    assert list(loudict.keys()) == [3, 2, 1]

    loudict[4] = "four"
    assert list(loudict.keys()) == [3, 2, 1, 4]


def test_cachable_template_eq() -> None:
    t1 = CachableTemplate(t"Hello {'name'}!")
    t2 = CachableTemplate(t"Hello {'name'}!")
    t3 = CachableTemplate(t"Goodbye {'name'}!")

    assert t1 == t2
    assert t1 != t3


def test_cachable_template_hash() -> None:
    t1 = CachableTemplate(t"Hello {'name'}!")
    t2 = CachableTemplate(t"Hello {'name'}!")

    assert hash(t1) == hash(t2)
