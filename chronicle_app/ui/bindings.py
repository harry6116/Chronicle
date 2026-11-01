"""Helpers for binding named UI events without accidental eager multi-binding."""


def bind_named(widget, name, bindings):
    event, handler = bindings[name]
    widget.Bind(event, handler)


def defer_menu_action(owner, handler, *, call_after):
    """Let native menu tracking finish before an action can open a dialog."""
    def invoke():
        try:
            alive = bool(owner) and not owner.IsBeingDeleted()
        except RuntimeError:
            return
        if alive:
            handler(None)

    call_after(invoke)


def bind_menu_action(owner, menu_event, handler, *, item_id, call_after):
    def selected(_event):
        defer_menu_action(owner, handler, call_after=call_after)

    owner.Bind(menu_event, selected, id=item_id)
