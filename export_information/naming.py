# -*- coding: utf-8 -*-
"""SUB BOX naming parser and natural sort helpers (pure Python)."""

import re

_NAME_RE = re.compile(r'^(?P<hub>.+?HB\d+)L(?P<link>\d+)S(?P<seq>\d+)$', re.IGNORECASE)


def parse_subbox_name(value):
    """Return (HUB name, L number, S number) from e.g. KIM-HB09L4S4."""
    match = _NAME_RE.match(str(value or '').strip())
    if not match:
        return None
    return match.group('hub'), int(match.group('link')), int(match.group('seq'))


def natural_hub_key(value):
    value = str(value or '').strip().upper()
    match = re.match(r'^(.*?HB)(\d+)$', value)
    if match:
        return match.group(1), int(match.group(2)), value
    return value, -1, value


def subbox_sort_key(value):
    parsed = parse_subbox_name(value)
    if not parsed:
        return (('~', 999999, str(value).upper()), 999999, 999999, str(value).upper())
    hub, link, seq = parsed
    return (natural_hub_key(hub), link, seq, str(value).upper())
