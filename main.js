const {loadMicroPython} = await import('./static/micropython.mjs');
window.runExample = async function (modulePath, thisCode) {
    let stdout;
    let stderr;

    const mp = await loadMicroPython({
        stdout: (text) => stdout = text,
        stderr: (text) => stderr = text
    });
    mp.runPython(thisCode)

    const target = document.getElementById(modulePath);
    const output = target.querySelector("div.output");
    console.log(stdout);
    output.innerHTML = stdout;
    return stdout;
}

// -------------------

// let mp;

async function initMicroPython2() {
    try {
        // Import MicroPython module
        const {loadMicroPython} = await import('./static/micropython.mjs');

        // Load MicroPython
        mp = await loadMicroPython({
            stdout: (text) => console.log(text),
            stderr: (text) => console.error(text)
        });

        // Debug: Check MicroPython API
        console.log('MicroPython instance:', mp);
        console.log('Available methods:', Object.keys(mp));

    } catch (error) {
        console.error('Failed to initialize MicroPython:', error);
    }
}

// await initMicroPython();
window.runExample2 = function () {
    console.log(1);
    if (!mp) return;
    console.log(2);

    const code = "print(3+3)"
    try {
        // Approach: Use globals() to store and retrieve output
        mp.runPython(`
# Clear any previous output
if '_example_output' in globals():
    del globals()['_example_output']

# Set up capture
globals()['_example_output'] = []
globals()['_original_print'] = print

def _capture_print(*args, **kwargs):
    output = ' '.join(str(arg) for arg in args)
    globals()['_example_output'].append(output)
    globals()['_original_print'](*args, **kwargs)

print = _capture_print
`);

        // Run the example code
        mp.runPython(code);

        // Restore print
        mp.runPython("print = globals()['_original_print']");

        // Get output - try multiple methods
        let output = null;

        // Method 1: Direct access via globals
        try {
            mp.runPython("globals()['_captured_result'] = '\\n'.join(globals()['_example_output'])");

            // Now try to get it via property access if available
            if (mp.globals && typeof mp.globals.get === 'function') {
                output = mp.globals.get('_captured_result');
            }
        } catch (e) {
            console.log('Method 1 failed:', e);
        }

        // Method 2: Store in a simple variable and check
        if (!output) {
            mp.runPython("_simple_output = '\\n'.join(globals()['_example_output'])");

            // Check if we can access Python globals directly
            if (mp.pyodide && mp.pyodide.globals) {
                output = mp.pyodide.globals.get('_simple_output');
            } else if (mp.globals) {
                output = mp.globals._simple_output || mp.globals['_simple_output'];
            }
        }

        // Method 3: Use print to output and capture via stdout
        if (!output && window.exampleOutput) {
            output = window.exampleOutput.join('\n');
        }

        // Display the output
        console.log("------- ", output);

        // Clean up
        mp.runPython(`
if '_example_output' in globals():
    del globals()['_example_output']
if '_captured_result' in globals():
    del globals()['_captured_result']
if '_simple_output' in globals():
    del globals()['_simple_output']
`);
    } catch (error) {
        console.error('Full error:', error);
    }
}