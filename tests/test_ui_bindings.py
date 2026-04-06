import unittest

from chronicle_app.ui.bindings import bind_named


class _Widget:
    def __init__(self):
        self.bound = []

    def Bind(self, event, handler):
        self.bound.append((event, handler))


class BindNamedTest(unittest.TestCase):
    def test_binds_only_requested_handler(self):
        widget = _Widget()
        event_a = object()
        event_b = object()
        handler_a = object()
        handler_b = object()

        bindings = {
            'add_files': (event_a, handler_a),
            'add_folder': (event_b, handler_b),
        }

        bind_named(widget, 'add_files', bindings)

        self.assertEqual(widget.bound, [(event_a, handler_a)])

    def test_raises_for_unknown_binding_name(self):
        widget = _Widget()
        with self.assertRaises(KeyError):
            bind_named(widget, 'missing', {})
        self.assertEqual(widget.bound, [])


if __name__ == '__main__':
    unittest.main()
