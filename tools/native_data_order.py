"""Generate native bank sections using the DS owner order (ported from Days)."""
def section_script(modules, ordered):
    lines=['/* Native sections in EU data-owner order; not DS virtual addresses. */','SECTIONS {']
    for module in modules:
        kinds=['.text','.rodata','.data','.bss'] if module.startswith('ov') else ['.rodata','.data']
        for kind in kinds:
            tag=kind[1:]
            lines.append(f' .kh_{module}_{tag} : ALIGN(32) {{ kh_{module}_{tag}_start = .;')
            for item in sorted(ordered.get((module,kind),[])):
                address,member=item[:2]
                inputs=item[2] if len(item)>2 else f"{kind} {kind}.*"
                align=4 if address%4==0 else 2 if address%2==0 else 1
                lines.append(f' . = ALIGN({align}); KEEP(*{module}.a:{member}({inputs}))')
            lines.append(f' *{module}.a:*({kind} {kind}.*) kh_{module}_{tag}_end = .; }}')
    lines += ['}', 'INSERT BEFORE .text;']
    return '\n'.join(lines)+'\n'
