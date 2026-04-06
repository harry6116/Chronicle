"""Helpers for binding named UI events without accidental eager multi-binding."""


def bind_named(widget, name, bindings):
    event, handler = bindings[name]
    widget.Bind(event, handler)
