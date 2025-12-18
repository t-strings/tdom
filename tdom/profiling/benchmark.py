#!/usr/bin/env python
"""Quick performance benchmark for regression testing.

Run this before and after optimizations to measure improvements.
"""

import time

from tdom import html


def create_test_template():
    """Create a medium-sized template for benchmarking."""
    # Generate components for a realistic DOM structure
    nav_links = "".join(f'<a href="/page{i}">Link {i}</a>' for i in range(50))

    sections = "".join(
        f"<section><h2>Section {i}</h2><p>Content for section {i}</p></section>"
        for i in range(100)
    )

    form_fields = "".join(
        f"""<div class="field">
            <label for="input{i}">Field {i}</label>
            <input type="text" id="input{i}" name="field{i}" />
        </div>"""
        for i in range(50)
    )

    list_items = "".join(f'<li class="item">Item {i}</li>' for i in range(50))

    return t"""<html>
        <head>
            <title>Test Page</title>
            <meta charset="utf-8" />
        </head>
        <body>
            <header>
                <h1>Performance Benchmark</h1>
                <nav>{nav_links}</nav>
            </header>
            <main>
                <article>
                    {sections}
                </article>
                <aside>
                    <form>
                        {form_fields}
                        <button type="submit">Submit</button>
                    </form>
                </aside>
            </main>
            <footer>
                <ul>{list_items}</ul>
                <p>Copyright 2025</p>
            </footer>
        </body>
    </html>"""


def create_interpolation_heavy_template():
    """Create a template with heavy interpolation for benchmarking."""
    name = "Alice"
    age = 30
    items = ["apple", "banana", "cherry"]

    return t"""<div>
        <h1>Hello, {name}!</h1>
        <p>You are {age} years old.</p>
        <ul>
            {"".join(f"<li>{item}</li>" for item in items)}
        </ul>
    </div>"""


def benchmark_operation(name: str, operation, iterations: int = 100):
    """Benchmark a single operation."""
    # Warmup to ensure JIT compilation, etc.
    for _ in range(10):
        result = operation()

    start = time.perf_counter()
    for _ in range(iterations):
        result = operation()
        # Prevent optimization by accessing result
        _ = str(result) if hasattr(result, "__str__") else result
    end = time.perf_counter()

    total_time = (end - start) * 1_000_000  # Convert to microseconds
    avg_time = total_time / iterations

    print(f"  {name:<40} {avg_time:>10.3f}μs/op  ({iterations} iterations)")
    return avg_time


def run_benchmark():
    """Run all benchmarks."""
    print("=" * 80)
    print("TDOM PERFORMANCE BENCHMARK")
    print("=" * 80)

    print("\nCreating test templates...")
    template = create_test_template()
    interpolation_template = create_interpolation_heavy_template()
    print("✓ Templates created\n")

    print("Running benchmarks...")
    print("-" * 80)

    results = {}

    # End-to-end: Template -> DOM -> String
    results["full_pipeline"] = benchmark_operation(
        "Full pipeline (template → DOM → HTML)", lambda: str(html(template))
    )

    # Just parsing: Template -> DOM
    results["parse_only"] = benchmark_operation(
        "Parse only (template → DOM)", lambda: html(template)
    )

    # Just serialization: DOM -> String
    dom = html(template)
    results["serialize_only"] = benchmark_operation(
        "Serialize only (DOM → HTML)", lambda: str(dom)
    )

    # Small template (overhead measurement)
    small_template = t"<div><p>Hello</p></div>"
    results["small_template"] = benchmark_operation(
        "Small template (overhead baseline)", lambda: str(html(small_template))
    )

    # Heavy interpolation
    results["interpolation"] = benchmark_operation(
        "Heavy interpolation", lambda: str(html(interpolation_template))
    )

    # Component rendering (nested elements)
    nested_template = t"<div><div><div><p>Nested</p></div></div></div>"
    results["nested"] = benchmark_operation(
        "Nested elements", lambda: str(html(nested_template))
    )

    # Attribute handling
    attr_template = t'<div id="test" class="foo bar" data-value="123">Content</div>'
    results["attributes"] = benchmark_operation(
        "Attribute handling", lambda: str(html(attr_template))
    )

    print("-" * 80)
    print(f"\nAverage time per operation: {sum(results.values()) / len(results):.3f}μs")
    print("\n" + "=" * 80)
    print("Benchmark complete!")
    print("=" * 80)

    # Performance targets
    print("\nPerformance Targets:")
    avg_time = sum(results.values()) / len(results)
    if avg_time < 50:
        print("  ✓ EXCELLENT - Operations are very fast")
    elif avg_time < 100:
        print("  ✓ GOOD - Performance is acceptable")
    elif avg_time < 200:
        print("  ⚠ FAIR - Consider optimization")
    else:
        print("  ✗ SLOW - Optimization recommended")

    print(f"\n  Current: {avg_time:.1f}μs/op | Target: <100μs/op | Best: <50μs/op")

    # Detailed breakdown
    print("\n" + "=" * 80)
    print("PERFORMANCE BREAKDOWN")
    print("=" * 80)

    parse_time = results["parse_only"]
    serialize_time = results["serialize_only"]
    full_time = results["full_pipeline"]
    overhead = full_time - (parse_time + serialize_time)

    print(
        f"\nParsing:        {parse_time:>8.3f}μs ({parse_time / full_time * 100:.1f}%)"
    )
    print(
        f"Serialization:  {serialize_time:>8.3f}μs ({serialize_time / full_time * 100:.1f}%)"
    )
    print(f"Overhead:       {overhead:>8.3f}μs ({overhead / full_time * 100:.1f}%)")
    print(f"Total:          {full_time:>8.3f}μs (100.0%)")


def main():
    """CLI entry point."""
    run_benchmark()


if __name__ == "__main__":
    main()
