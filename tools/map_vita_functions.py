#!/usr/bin/env python3
"""Compare EU ARM9 function symbols with the final Vita ELF from the same build."""
from collections import Counter, defaultdict
import hashlib
import json
import re
import subprocess

from audit_recoded import ROOT, inventory
from configure_vita import BIN

NATIVE = ROOT / 'build/native'
DECOMP = ROOT / 'build/decomp'
TEXT_SPAN = re.compile(r'\.text\s+start:(0x[0-9a-f]+)\s+end:(0x[0-9a-f]+)')
RELOC = re.compile(r'from:(0x[0-9a-f]+) kind:(\S+) to:(0x[0-9a-f]+) module:(\S+)')
OBJECT_LABELS = {'gMovieDecodeTableBlob', 'gMovieDecoderLookupTable'}


def symbol_table(path):
    table = defaultdict(list)
    output = subprocess.check_output([BIN / 'arm-vita-eabi-objdump', '-t', path], text=True)
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 5 or not re.fullmatch(r'[0-9a-f]{8}', fields[0]):
            continue
        section, size, name = fields[-3:]
        flags = set(fields[1:-3])
        if section.startswith('.') and flags & {'F', 'O'}:
            table[name].append({
                'name': name, 'address': f'0x{fields[0]}', 'section': section,
                'size': int(size, 16), 'type': 'function' if 'F' in flags else 'object',
            })
    if not table:
        raise SystemExit(f'Empty symbol table: {path}')
    return table


def original_references():
    references = defaultdict(list)
    for path in sorted((DECOMP / 'eu/config/arm9').rglob('relocs.txt')):
        source = 'main' if path.parent.name == 'arm9' else path.parent.name
        for origin, kind, destination, target in RELOC.findall(path.read_text()):
            if target.startswith(('overlay(', 'overlays(')):
                modules = [f'ov{int(number):03d}' for number in re.findall(r'\d+', target)]
            else:
                modules = [target]
            for module in modules:
                references[module, int(destination, 16) & ~1].append({
                    'module': source, 'address': origin, 'kind': kind,
                    'multiple_targets': len(modules) > 1,
                })
    return references


def source_owners():
    compile_units = {
        (unit['module'], unit['source']): unit
        for unit in json.loads((NATIVE / 'compile.json').read_text())['units']
    }
    owners = defaultdict(list)
    for entry in inventory(DECOMP):
        module, source = entry['module'], entry['source']
        unit = compile_units.get((module, source), {})
        for section in entry['sections']:
            span = TEXT_SPAN.match(section)
            if span:
                start, end = (int(value, 16) for value in span.groups())
                owners[module].append((start, end, {
                    'source': source, 'compile_status': unit.get('status'),
                    'reason': unit.get('reason'), 'provider': unit.get('provider'),
                }))
    return owners


def function_map(elf):
    layout = json.loads((NATIVE / 'gen/layout.json').read_text())['modules']
    linked = symbol_table(elf)
    before_gc = symbol_table(NATIVE / 'recoded.sdk.o')
    references = original_references()
    owners = source_owners()
    seen = set()
    for module, metadata in layout.items():
        for symbol in metadata['symbols']:
            name, address = symbol['name'], symbol['address']
            key = (module, address, name)
            if not symbol['kind'].startswith('function(') or key in seen:
                continue
            seen.add(key)
            source = [owner for start, end, owner in owners[module] if start <= address < end]
            vita_name = 'NitroMain' if module == 'main' and name == 'main' else name
            matches = [match for match in linked[vita_name] if match['type'] == 'function']
            objects = [match for match in linked[vita_name] if match['type'] == 'object']
            # LoadStageModels is emitted as a weak inline definition in .text.
            if module.startswith('ov') and name != 'LoadStageModels':
                matches = [match for match in matches if match['section'] == f'.kh_{module}_text']
            pre_link = [match for match in before_gc[vita_name] if match['type'] == 'function']
            if len(matches) == 1:
                status = 'ligada'
            elif len(matches) > 1:
                status = 'correspondência ambígua'
            elif objects and module == 'ov022' and name in OBJECT_LABELS:
                status = 'dado no Vita'
                matches = objects
            elif pre_link:
                status = 'ausente após link final'
            elif any(owner['compile_status'] == 'replaced' for owner in source):
                status = 'omitida pelo port'
            else:
                status = 'sem símbolo correspondente'
            yield {
                'module': module, 'ds_address': f'0x{address:08x}', 'ds_name': name,
                'ds_kind': symbol['kind'], 'status': status, 'vita_symbols': matches,
                'pre_link_symbols': pre_link if status == 'ausente após link final' else [],
                'source': source, 'ds_references': references[module, address & ~1],
            }


def write_summary(path, rows, metadata):
    counts = Counter(row['status'] for row in rows)
    exceptions = [row for row in rows if row['status'] != 'ligada']
    lines = [
        f"# Mapa do Re:coded Vita {metadata['version']}", '',
        f"Inventário ARM9 EU da decompilação {metadata['decomp_commit']}.",
        f"ELF analisado {metadata['elf']}.",
        f"SHA-256 do ELF: {metadata['elf_sha256']}.", '',
        f'**{len(rows)} entradas únicas** por módulo, endereço e nome no DS.', '',
        '| Resultado | Entradas |', '| --- | ---: |',
    ]
    lines.extend(f'| {status} | {count} |' for status, count in counts.most_common())
    lines.extend([
        '', 'O arquivo mapa-funcoes-vita.json traz todos os endereços DS e Vita,',
        'as fontes por faixa de delink e as relocações registradas no DS.',
        'Os endereços Vita vêm do ELF. Um log do aparelho pode incluir o deslocamento de carga.',
        '', 'A ausência de um símbolo isolado pode decorrer de inlining, remoção de código',
        'pelo linker ou substituição pela plataforma. Uma referência registrada no DS',
        'também pode pertencer a código que o port já substituiu.',
        'O estado do build vem da unidade de origem. Uma unidade compilada pode',
        'conter várias funções e dados.',
        'Para verificar a execução e a ABI de uma chamada, use o binário e, quando',
        'necessário, os registros do aparelho.', '',
        '## Entradas fora da correspondência direta', '',
        '| Módulo | Endereço DS | Nome DS | Resultado | Build da fonte | Relocações DS¹ |',
        '| --- | --- | --- | --- | --- | ---: |',
    ])
    for row in sorted(exceptions, key=lambda r: (r['module'], r['ds_address'], r['ds_name'])):
        states = ', '.join(sorted({owner['compile_status'] or '—' for owner in row['source']}))
        lines.append(
            f"| {row['module']} | {row['ds_address']} | {row['ds_name']} | "
            f"{row['status']} | {states or '—'} | {len(row['ds_references'])} |"
        )
    lines.extend(['', '¹ Inclui candidatos de relocações com mais de um overlay possível.', ''])
    path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    elf = NATIVE / 'khrecoded.elf'
    metadata = {
        'elf': str(elf.relative_to(ROOT)), 'version': (ROOT / 'VERSION').read_text().strip(),
        'elf_sha256': hashlib.sha256(elf.read_bytes()).hexdigest(),
        'decomp_commit': (DECOMP / '.port-source-commit').read_text().strip(),
    }
    rows = list(function_map(elf))
    output = ROOT / 'build/audit/vita-functions'
    output.mkdir(parents=True, exist_ok=True)
    data = {'build': metadata, 'functions': rows}
    (output / 'mapa-funcoes-vita.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )
    write_summary(output / 'lacunas-funcoes-vita.md', rows, metadata)
    print(Counter(row['status'] for row in rows))


if __name__ == '__main__':
    main()
