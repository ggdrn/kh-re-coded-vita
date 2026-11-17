"""Text-only adaptation of the proven Days geometry-command rewrite pass."""
import re

def gx_commands(text,legacy):
    original=text;extra=[]
    for m in legacy.GX_ALIAS_MACRO.finditer(text):extra.append(r'\b'+m[1]+r'\b')
    for m in legacy.GX_ALIAS_PTR.finditer(text):
        n=m[1];extra += [r'\*\s*'+n+r'\b(?!\s*\[)',r'\b'+n+r'\s*->\s*\w+',r'\b'+n+r'\s*\[[^\]]+\]']
    if extra:
        alias=re.compile(r'^(?P<ind>[ \t]*)(?P<lv>'+ '|'.join(extra)+r')\s*=(?!=)\s*(?P<v>[^;{}]+);',re.M)
        text=alias.sub(lambda m:f"{m['ind']}KH_GX_CMD({m['lv']}, {m['v'].strip()});",text)
    def sub(m):
        bol=text.rfind('\n',0,m.start())+1
        if text[bol:m.start()].lstrip().startswith(('/*','*','//')):return m[0]
        return f"KH_GX_CMD({m['lv']}, {m['v'].strip()});"
    text=legacy.GX_LVALUE.sub(sub,text)
    if text!=original and legacy.HW_INCLUDE not in text:text=legacy.HW_INCLUDE+'\n'+text
    return text

def vram_sync(text,legacy):
    if 'KH_VRAM_SYNC_ON_EXIT' in text:return text
    for at in reversed(legacy.function_bodies(text,legacy.code_mask(text))):
        text=text[:at]+'\n'+legacy.SYNC_BLOCK+text[at:].lstrip('\n')
    if legacy.HW_INCLUDE not in text:text=legacy.HW_INCLUDE+'\n'+text
    return text
