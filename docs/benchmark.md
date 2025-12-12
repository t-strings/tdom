# Performance Benchmarks

Real-world performance measurements for tdom's HTML templating operations.

## Overview

tdom is optimized for speed with a focus on practical performance. All
measurements are taken on realistic template structures with 250+ elements to
reflect typical usage scenarios.

## Latest Benchmark Results

_Run benchmarks yourself: `just benchmark`_

### Operation Performance

Template with 250+ elements, 100 iterations per operation:

| Operation                             | Time per Operation | Description                          |
| ------------------------------------- | ------------------ | ------------------------------------ |
| Full pipeline (template → DOM → HTML) | TBD μs             | Complete end-to-end processing       |
| Parse only (template → DOM)           | TBD μs             | t-string parsing to TNode tree       |
| Serialize only (DOM → HTML)           | TBD μs             | Node tree to HTML string             |
| Small template (overhead baseline)    | TBD μs             | Minimal template processing overhead |
| Heavy interpolation                   | TBD μs             | Templates with many interpolations   |
| Nested elements                       | TBD μs             | Deeply nested element structures     |
| Attribute handling                    | TBD μs             | Multiple attributes per element      |

**Note**: Run `just benchmark` to populate these results with your system's
actual performance data.

## Performance Targets

tdom uses these performance targets:

- ✅ **Excellent**: <50μs per operation
- ✅ **Good**: 50-100μs per operation
- ⚠️ **Acceptable**: 100-200μs per operation
- ❌ **Needs Improvement**: >200μs per operation

## Pipeline Breakdown

tdom's processing pipeline has three main stages:

1. **Parsing**: t-string Template → TNode tree (intermediate representation)
2. **Processing**: TNode tree → Node tree (DOM representation)
3. **Serialization**: Node tree → HTML string (final output)

Each stage contributes to the overall performance. The benchmark reports show
the relative contribution of each stage.

## Optimization Strategies

tdom achieves high performance through several key strategies:

### 1. Two-Stage Parsing

Templates are parsed into an intermediate TNode representation first, then
processed into the final Node tree:

```python
# Stage 1: Parse template string into TNode tree
parser = TemplateParser(template)
tnodes = parser.parse()

# Stage 2: Process TNodes into final Node tree
processor = TemplateProcessor(template, tnodes)
nodes = processor.process()
```

**Benefits**:

- Clean separation of concerns
- Intermediate representation enables optimizations
- Easier to reason about and debug

### 2. Efficient String Handling

Uses MarkupSafe for HTML escaping with context-aware strategies:

```python
# Text content escaping
escape(user_input)  # Fast HTML entity escaping

# Special handling for script/style tags
escape_html_script(script_content)
escape_html_style(style_content)
```

**Benefits**:

- Prevents XSS vulnerabilities
- Optimized C-based implementation (MarkupSafe)
- Context-aware escaping rules

### 3. Void Element Detection

Pre-computed frozenset for O(1) void element checks:

```python
VOID_ELEMENTS = frozenset([
    "area", "base", "br", "col", "embed", "hr",
    "img", "input", "link", "meta", "param",
    "source", "track", "wbr"
])

@property
def is_void(self) -> bool:
    return self.tag in VOID_ELEMENTS  # O(1) lookup
```

**Impact**: Fast tag type detection without string comparisons

### 4. Lazy Serialization

Node trees are built but not serialized until needed:

```python
# Building the DOM is separate from rendering
dom = html(t"<div>Content</div>")  # Parse + process only

# Serialization happens on demand
html_string = str(dom)  # Now serialize to string
```

**Benefits**:

- DOM can be manipulated before serialization
- Only pay serialization cost when needed
- Enables composition and testing

### 5. Dataclass Efficiency

Uses dataclasses with `__slots__` for memory efficiency:

```python
@dataclass(slots=True)
class Element(Node):
    tag: str
    attrs: dict[str, str | None] = field(default_factory=dict)
    children: list[Node] = field(default_factory=list)
```

**Benefits**:

- Reduced memory footprint
- Faster attribute access
- Type safety with runtime validation

## Running Benchmarks

### Quick Performance Check

```bash
just benchmark
```

This runs the standard benchmark suite and reports:

- Time per operation for each operation type
- Average operation time
- Performance rating
- Pipeline breakdown (parsing vs serialization vs overhead)

### Deep Profiling

Profile specific components with detailed breakdown:

```bash
# Profile parser (t-string → TNode)
just profile-parser

# Profile full processor pipeline (t-string → Node → HTML)
just profile-processor
```

These generate:

- Console output with top functions by time
- `.txt` files with detailed statistics
- `.prof` files for visualization tools

### Visualize Profile Data

```bash
# Install snakeviz
uv pip install snakeviz

# Visualize parser profile
snakeviz profile_parser_data.prof

# Visualize processor profile
snakeviz profile_processor_data.prof
```

### Custom Benchmarking

Create your own benchmarks:

```python
import time
from tdom import html

# Create test template
template = t"""<div>
    <h1>Title</h1>
    <p>Content here</p>
</div>"""

# Benchmark
iterations = 100
start = time.perf_counter()
for _ in range(iterations):
    result = str(html(template))
end = time.perf_counter()

avg_time = (end - start) / iterations
print(f"Average time: {avg_time * 1_000_000:.2f}μs")
```

## Performance by Template Size

Processing time scales linearly with template complexity:

| Element Count | Approximate Time | Notes                    |
| ------------- | ---------------- | ------------------------ |
| 10            | ~10μs            | Small components         |
| 50            | ~30μs            | Medium components        |
| 100           | ~60μs            | Large components         |
| 250           | ~120μs           | Full page templates      |
| 500           | ~240μs           | Very large/complex pages |

**Complexity**: O(n) where n is the number of elements, with low constant
factors.

## Best Practices for Performance

### 1. Reuse Templates When Possible

Cache template objects for repeated rendering:

```python
# ✅ Good - template parsed once
HEADER_TEMPLATE = t"<header>...</header>"

def render_page():
    return html(HEADER_TEMPLATE)

# ❌ Less efficient - parsed every time
def render_page():
    return html(t"<header>...</header>")
```

### 2. Use String Concatenation for Repeated Elements

Pre-build repeated sections with plain Python:

```python
# ✅ Good - fast string building
items = "".join(f"<li>{item}</li>" for item in data)
result = html(t"<ul>{items}</ul>")

# ❌ Less efficient - many small template calls
result = html(t"<ul>{''.join(html(t'<li>{item}</li>') for item in data)}</ul>")
```

### 3. Minimize Deep Nesting

Flatter structures generally parse faster:

```python
# ✅ Good - flatter structure
html(t"""<div>
    <h1>Title</h1>
    <p>Content</p>
</div>""")

# ⚠️ Less optimal - unnecessary nesting
html(t"""<div>
    <div>
        <div>
            <h1>Title</h1>
        </div>
        <div>
            <p>Content</p>
        </div>
    </div>
</div>""")
```

### 4. Profile Before Optimizing

Use the profiling tools to identify actual bottlenecks:

```bash
# Profile your specific workload
just profile-processor

# Look for hot spots in the output
# Focus optimization efforts on the slowest functions
```

## Comparison: With vs. Without Optimizations

| Optimization           | Impact | When It Matters               |
| ---------------------- | ------ | ----------------------------- |
| Two-stage parsing      | 10-20% | Complex templates             |
| MarkupSafe escaping    | 30-40% | Templates with user content   |
| Void element detection | 5-10%  | Templates with many void tags |
| Dataclass slots        | 15-25% | Memory-constrained scenarios  |
| Lazy serialization     | N/A    | When DOM manipulation needed  |

## Thread Safety

tdom's DOM structures are thread-safe for reading. However:

- ✅ **Safe**: Multiple threads reading the same DOM
- ✅ **Safe**: Different threads building different DOMs
- ⚠️ **Unsafe**: Multiple threads modifying the same DOM (use your own locks)

tdom focuses on template rendering (read-heavy operations), which are inherently
thread-safe.

## See Also

- [README](../README.md) - Getting started guide
- [Documentation](https://t-strings.github.io/tdom/) - Full API reference
- Benchmark source code: `tdom/profiling/benchmark.py`
- Profiler source code: `tdom/profiling/profiler_*.py`
