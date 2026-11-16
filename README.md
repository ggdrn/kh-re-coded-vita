# Kingdom Hearts Re:coded — PS Vita

Port nativo em desenvolvimento, iniciado a partir da infraestrutura local do
`khdays-vita`. **O VPK atual é um diagnóstico; ainda não inicia o jogo.**
A decompilação ARM9 do Re:coded precisa ser ligada e adaptada ao runtime Vita.

## Estado desta base

- Executável Vita, identidade própria `KHRC00001`, verificação da ROM europeia.
- Menu `L+R+Select`, remapeamento, filtros, resolução e disposição das duas telas.
- Tela única desabilitada, inclusive via config.ini. Opções específicas de
  parceiros, Roxas, Mission Mode, HUD e ícones do Days não são oferecidas.
- Renderizadores e áudio do Days preservados; integração com o Re:coded pendente.
- No diagnóstico, controles/touch, layout e menu podem ser exercitados. Resolução
  3D, áudio e velocidade só terão efeito no jogo quando o runtime estiver ligado.
- Nenhuma execução no aparelho foi validada nesta etapa.

## Compilar o diagnóstico

VitaSDK e as bibliotecas já usadas no Days: vitaGL, vitaShaRK, mathneon,
SceShaccCgExt, kubridge/taihen; Python 3 e Ninja.

```sh
python3 configure_vita.py
ninja
```

Saída: `build/VPK/khrecoded-vita-0.1.0.vpk`.
Instale com VitaShell e copie sua ROM para `ux0:data/khrecoded/coded.nds`.
O aparelho precisa do `libshacccg.suprx` usado pelo port do Days.
Configurações e logs ficam em `ux0:data/khrecoded/`; não usam os arquivos do Days.

ROM: EU **BK9P**, 268435456 bytes,
SHA-1 `b9d45dcd654265fc7b8ba83f1bb3c15f011d6acf`.
Confirmado contra `eu/CONTRIBUTING.md` da decompilação e o dump local.

## Trabalhar na integração

```sh
python3 tools/inspect_rom.py ../coded.nds
python3 tools/setup_decomp.py
python3 tools/audit_recoded.py --decomp build/decomp
python3 tools/audit_recoded.py --decomp build/decomp --probe --jobs 6
```

O setup extrai o commit de `DECOMP_COMMIT` do Git local para uma cópia isolada.
Não sobrescreve uma cópia existente. A auditoria usa os `delinks.txt` europeus,
respeitando a propriedade nativa dos fontes e os wrappers regionais.
O probe compila unidades isoladas: não testa link, ABI entre chamadas ou gameplay.
`--with-game` falha explicitamente enquanto essa integração não estiver pronta.

Ver [análise e plano](docs/PORTING_ANALYSIS.md) e [validação](docs/VALIDATION.md).
`reference/days/` preserva documentação, patch e ferramentas específicas do Days
para consulta; **não aplicar esse patch ao Re:coded**.
O manifesto em `docs/days-source-manifest.json` registra hashes dos arquivos locais
usados como origem, incluindo alterações locais, além do commit do Days.

Não há ROM, assets do jogo ou módulos Sony versionados. Fontes e ferramentas
herdados mantêm suas atribuições; veja `THIRD_PARTY_NOTICES.md`.
