#!/usr/bin/env python
"""Profile the processor module to identify performance bottlenecks.

Uses cProfile for CPU profiling and provides detailed stats.
"""

import cProfile
import pstats
from io import StringIO

from tdom import html


def create_large_template():
    """Create a large template for profiling."""
    # Pre-generate HTML components
    nav_links = "".join(f'<a href="/page{i}">Link {i}</a>' for i in range(100))

    sections = "".join(
        f"<section><h2>Section {i}</h2><p>Content {i}</p></section>" for i in range(200)
    )

    form_inputs = "".join(
        f"""<div class="form-group">
            <label for="input{i}">Label {i}</label>
            <input type="text" id="input{i}" data-testid="test-{i}" />
        </div>"""
        for i in range(100)
    )

    footer_items = "".join(
        f'<li class="footer-item">Footer item {i}</li>' for i in range(50)
    )

    return t"""<html>
        <head>
            <title>Large Test Page</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        </head>
        <body>
            <header role="banner">
                <h1>Main Title</h1>
                <nav>{nav_links}</nav>
            </header>
            <main>
                <article>
                    <h2>Article Title</h2>
                    {sections}
                </article>
                <aside>
                    <h3>Sidebar</h3>
                    <form>
                        {form_inputs}
                        <button type="submit">Submit</button>
                        <button type="reset">Reset</button>
                    </form>
                </aside>
            </main>
            <footer role="contentinfo">
                <ul>{footer_items}</ul>
                <p>Copyright 2025</p>
            </footer>
        </body>
    </html>"""


def benchmark_processor(template):
    """Run processor operations repeatedly."""
    # Full pipeline: parse + process + serialize
    for _ in range(100):
        dom = html(template)
        _ = str(dom)


def profile_processor():
    """Profile processor operations."""
    print("=" * 80)
    print("Creating test template...")
    print("=" * 80)

    template = create_large_template()
    print("Template created successfully")
    print(f"Template has {len(template.strings)} string parts")
    print(f"Template has {len(template.interpolations)} interpolations")

    print("\n" + "=" * 80)
    print("Starting profiling of full processor pipeline...")
    print("=" * 80)

    profiler = cProfile.Profile()
    profiler.enable()
    benchmark_processor(template)
    profiler.disable()

    # Create stats object
    stats = pstats.Stats(profiler)

    # Sort by cumulative time
    print("\n" + "=" * 80)
    print("TOP 40 FUNCTIONS BY CUMULATIVE TIME")
    print("=" * 80)
    stats.sort_stats(pstats.SortKey.CUMULATIVE)
    stats.print_stats(40)

    # Sort by time spent in function (not including subcalls)
    print("\n" + "=" * 80)
    print("TOP 40 FUNCTIONS BY INTERNAL TIME")
    print("=" * 80)
    stats.sort_stats(pstats.SortKey.TIME)
    stats.print_stats(40)

    # Show functions from tdom module only
    print("\n" + "=" * 80)
    print("TDOM MODULE FUNCTIONS")
    print("=" * 80)
    stats.sort_stats(pstats.SortKey.CUMULATIVE)
    stats.print_stats("tdom")

    # Save stats
    output_file = "profile_processor_stats.txt"
    with open(output_file, "w") as f:
        stream = StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats(pstats.SortKey.CUMULATIVE)
        stats.print_stats()
        f.write(stream.getvalue())

    print(f"\n\nDetailed stats saved to: {output_file}")

    profiler.dump_stats("profile_processor_data.prof")
    print("Profile data saved to: profile_processor_data.prof")
    print("\nVisualize with: snakeviz profile_processor_data.prof")
    print("(Install with: uv pip install snakeviz)")


if __name__ == "__main__":
    profile_processor()
