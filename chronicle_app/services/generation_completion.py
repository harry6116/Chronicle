"""Reject provider responses that ended before the extraction was complete."""


class IncompleteGenerationError(RuntimeError):
    def __init__(self, reason):
        self.reason = str(reason).upper()
        super().__init__('The model response is incomplete. Review the source page and retry with a smaller page region or another reading engine.')


def _field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def require_complete_generation(response):
    if response is None or isinstance(response, str):
        return
    reasons = [_field(response, 'stop_reason')]
    delta = _field(response, 'delta')
    if delta is not None:
        reasons.append(_field(delta, 'stop_reason'))
    for collection in ('candidates', 'choices'):
        items = _field(response, collection)
        if isinstance(items, (list, tuple)):
            for item in items:
                reasons.extend((_field(item, 'finish_reason'), _field(item, 'finishReason')))
    incomplete = {'MAX_TOKENS', 'LENGTH', 'MAX_OUTPUT_TOKENS', 'MODEL_CONTEXT_WINDOW_EXCEEDED',
                  'SAFETY', 'RECITATION', 'CONTENT_FILTER', 'BLOCKLIST', 'PROHIBITED_CONTENT'}
    for reason in reasons:
        if reason is None:
            continue
        name = str(getattr(reason, 'name', reason)).rsplit('.', 1)[-1].upper()
        if name in incomplete:
            raise IncompleteGenerationError(name)
