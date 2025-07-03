"""The part of the webapp that integrates with the DOM."""

from js import document, cm6, DOMParser

from examples.webapp import main

loader = document.getElementById("loader")
output = document.getElementById("output")
loader.textContent = "Loading"
try:
    stories = main()
    loader.textContent = "Loaded"

    for story in stories:
        module_path = story["module_path"]
        new_example = document.createElement("div")
        new_example.innerHTML = story["rendered"]
        output.append(new_example)

        # Make the node into an editor
        div_editor = new_example.querySelector(".editor")
        initialState = cm6.createEditorState(story["code"])
        view = cm6.createEditorView(initialState, div_editor);

        # Attach an event handler with closure information
        def runThisCode():
            # Use a closure to get these variables into an event handler
            this_story = story
            this_example = new_example
            this_editor = view
            this_module_path = story["module_path"]
            # Get a selector pointing to the correct result output
            selector = f'section[title="{module_path}"] div.result'
            def _runThisCode(event):
                this_code = this_editor.state.doc.toString()
                this_addendum = f'''\
from js import document
result = str(main())
target = document.querySelector('{selector}')
target.innerHTML = result;
'''
                exec(this_code + this_addendum)

            return _runThisCode

        new_example.querySelector("button").addEventListener("click", runThisCode(), False);

except IndexError as e:
    loader.textContent = str(e)