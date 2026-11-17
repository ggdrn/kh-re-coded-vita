"""Recognize data-only absolute aliases; never emit DS addresses as native pointers."""
import re


def parse_alias(text, symbols):
    match = re.fullmatch(r'\s*\.global\s+(\w+)\s+\.equ\s+\1\s*,\s*(0x[0-9a-fA-F]+)\s*', text)
    if not match:
        return None
    name, address = match[1], int(match[2], 16)
    declared = [s for s in symbols if s['name'] == name and s['address'] == address
                and s['kind'].startswith(('data', 'label'))]
    if len(declared) != 1:
        return None
    return {'name': name, 'address': address}


def bind_alias(alias, symbols, section_objects, spans):
    """Find an actual initialized object at the alias address in its owning unit."""
    matches = []
    for offset, section, name in section_objects:
        target = symbols.get(name)
        if name == alias['name'] or not target or target['address'] != alias['address']:
            continue
        if not target['kind'].startswith(('data', 'label')):
            continue
        kind = '.rodata' if section.startswith('.rodata') else '.data'
        if any(k == kind and lo <= alias['address'] < hi for k, lo, hi in spans):
            matches.append((section, offset, name))
    if len(matches) > 1:
        raise ValueError('Ambiguous native alias owner: ' + alias['name'])
    return matches[0] if matches else None
