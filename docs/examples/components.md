# Components

You often have a snippet of templating that you'd like to re-use.
Many existing templating systems have "macros" for this: units of templating that can be re-used and called from other templates.

The whole mechanism, though, is quite magical:

- Where do the macros come from?
  Multiple layers of context magic and specially named directories provide the answer.

- What macros are available at the cursor position I'm at in a template?
  It's hard for an editor or IDE to predict and provide autocomplete.

- What are the macros arguments and what is this template's special syntax for providing them?
  And can my editor help on autocomplete or tell me when I got it wrong (or the macro changed its signature)?

- How does my current scope interact with the macro's scope, and where does it get other parts of its scope from?

`tdom`, courtesy of `htm.py`, makes this more Pythonic through the use of "components."
Instead of some sorta-callable, a component is a normal Python callable—e.g., a function—with normal Python arguments and return values.

## Simple Heading

Here is a component callable -- a `Heading` function -- which returns a `Node`:

```{literalinclude} ../../examples/components/simple_heading/__init__.py
---
start-at: def Heading
---
```

## Simple Props

As expected, components can have props, passed in as what looks like HTML attributes.
Here we pass a `title` as an argument to `Heading`, using a simple HTML attribute string value:

```{literalinclude} ../../examples/components/simple_props/__init__.py
---
start-at: def Heading
---
```

## Children As Props

If your template has children inside the component element, your component can ask for them as an argument:

```{literalinclude} ../../examples/components/children_props/__init__.py
---
start-at: def Heading
---
```

`children` is a keyword parameter that is available to components.
Note how the component closes with `<//>` when it contains nested children, as opposed to the self-closing form in the first example.

## Expressions as Prop Values

The "prop" can also be a Python symbol, using curly braces as the attribute value:

```{literalinclude} ../../examples/components/expression_props/__init__.py
---
start-at: def Heading
---
```

## Prop Values from Scope Variables

That prop value can also be an in-scope variable:

```{literalinclude} ../../examples/components/scope_values/__init__.py
---
start-at: def Heading
---
```

## Optional Props

Since this is typical function-argument stuff, you can have optional props through argument defaults:

```{literalinclude} ../../examples/components/optional_props/__init__.py
---
start-at: def Heading
---
```

## Pass Component as Prop

Here's a useful pattern: you can pass a component as a "prop" to another component.
This lets the caller -- in this case, the `result` line -- do the driving:

```{literalinclude} ../../examples/components/pass_component/__init__.py
---
start-at: def DefaultHeading
---
```

## Default Component for Prop

As a variation, let the caller do the driving but make the prop default to a default component if none was provided:

```{literalinclude} ../../examples/components/default_component/__init__.py
---
start-at: def DefaultHeading
---
```

## Conditional Default

One final variation for passing a component as a prop... move the "default or passed-in" decision into the template itself:

```{literalinclude} ../../examples/components/conditional_default/__init__.py
---
start-at: def DefaultHeading
---
```

## Children as Prop

You can combine different props and arguments.
In this case, `title` is a prop.
`children` is another argument, but is provided automatically by `tdom`.

```{literalinclude} ../../examples/components/children_props/__init__.py
---
start-at: def Heading
---
```

## Generators as Components

You can also have components that act as generators.
For example, imagine you have a todo list.
There might be a lot of todos, so you want to generate them in a memory-efficient way:

```{literalinclude} ../../examples/components/generators/__init__.py
---
start-at: def Todos
---
```

## Subcomponents

Subcomponents are also supported:

```{literalinclude} ../../examples/components/subcomponents/__init__.py
---
start-at: def Todo
---
```
