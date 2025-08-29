"""Confirm the MicroPython example builder works."""

# from examples.webapp import main, get_story_data
# from examples.static_string import string_literal
#
# def test_get_story_data():
#     story = get_story_data(string_literal)
#     assert story["module_path"] == "examples.static_string.string_literal"
#     assert story["file_path"].endswith("__init__.py")
#     assert story["docstring"] == string_literal.__doc__
#     assert "def main" in story["code"]
#     assert story["result"] == "Hello World"
#     assert "<section" in story["rendered"]
#
# def test_main():
#     """Run main and test the results."""
#
#     stories = main()
#     assert stories[0]["result"] == "Hello World"
