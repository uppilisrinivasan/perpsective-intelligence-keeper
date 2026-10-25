from lamina.model import Document, Entry, Section


def test_set_existing_keeps_position():
    s = Section("a", [Entry("x", "1"), Entry("y", "2")])
    s.set("x", "9")
    assert s.keys() == ["x", "y"]
    assert s.get("x") == "9"


def test_set_new_appends():
    s = Section("a", [Entry("x", "1")])
    s.set("z", "3")
    assert s.keys() == ["x", "z"]


def test_remove():
    s = Section("a", [Entry("x", "1")])
    assert s.remove("x") is True
    assert s.remove("x") is False


def test_section_create():
    doc = Document()
    assert doc.section("new") is None
    assert doc.section("new", create=True).name == "new"


def test_to_dict():
    doc = Document(sections_=[Section("a", [Entry("x", "1")])])
    assert doc.to_dict() == {"a": {"x": "1"}}


def test_copy_is_deep():
    doc = Document(sections_=[Section("a", [Entry("x", "1")])])
    other = doc.copy()
    other.section("a").set("x", "2")
    assert doc.get("a.x") == "1"
