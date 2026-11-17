# ABI, dados, overlays e boot — segunda etapa

## Resultado observado no aparelho

Os arquivos fornecidos pelo usuário estão preservados em `device-tests/`.
`boot-0.1.0.txt` chegou a main → system → log → fault → video → rom → diagnostic.
`rom-0.1.0.verified` registra BK9P com o SHA-1 esperado e a impressão digital do
cache. Isso confirma a inicialização diagnóstica e a aceitação da ROM; não prova
renderização do jogo, gameplay, áudio ou save.

## Implementação

- ABI de interrupções: callers C passam a usar o retorno escalar r0 do backend.
  O retorno `value_in_regs` de três palavras do CodeWarrior não foi convertido
  silenciosamente em retorno struct AAPCS. Helpers locais que salvam IME foram
  renomeados, mantendo seu comportamento distinto do CPSR.
- `u64`/`s64` mantêm alinhamento de 4 bytes. Asserts ARM32 cobrem ponteiros, char,
  enums, campos do scheduler/OSThread e fila de transferência de VRAM. Isso não
  certifica todas as estruturas nem todas as interfaces do jogo.
- Headers FND/G2D/GFD necessários foram recuperados da base Days; interfaces
  incompletas restantes continuam como falhas explícitas de compilação.
- Callbacks de IRQ recuperados do header original: stride de 12 bytes, quatro
  slots DMA seguidos de quatro slots de timer; offsets conferidos contra BSS EU.
- CPU, PXI, cartão, timer e arena agora usam símbolos/limites da EU Re:coded.
  MAIN inicia em 0x020d9c40, ITCM em 0x01fffec0, DTCM livre em 0x027e0280.
- BSS gerado por módulo, sem fundir overlays que compartilham endereço DS.
  Aliases de campos comprovados do scheduler apontam para a mesma alocação.
- DTCM inicializada a partir dos quatro objetos C reconstruídos, com cópia por
  símbolo. A ordem das variáveis no arquivo C não é usada como ordem da memória.
- 105 overlays: entrypoints e tabelas de inicialização resolvidos dentro do banco
  correto; os cinco inicializadores não nulos pertencem ao ov104. Sua resolução
  simbólica não valida executar DS Protect no Vita; a fronteira permanece pendente.
- Carregador restaura DATA, limpa BSS, acompanha sobreposição, invoca inicialização
  e remove destrutores. Falha de alocação impede carregamento; unload limpa o estado.
- Espelhos 0x027ff000/0x02fff000 compartilham o mesmo bloco. A passagem KH_HW
  reaproveita o classificador do Days, sem suas exceções de endereços específicos.
  Literais ambíguos ficam em `build/native/adapted/hardware-review.txt`.
- `kh_recoded_prepare_memory()` prepara DTCM e snapshots e retorna erro em falta
  de memória. Compila e integra o link parcial, mas ainda não é chamado pelo VPK
  diagnóstico nem constitui conexão completa até NitroMain.

Todas as alterações da decompilação são overrides gerados em `build/native/adapted`.
A cópia fixada `build/decomp` e os dois projetos originais não são editados.

## Reproduzir

```sh
python3 tools/prepare_native_abi.py
python3 tools/compile_native.py --jobs 8
# O comando acima retorna erro enquanto houver unidades pendentes; preserva objetos/logs.
python3 tools/link_native.py
python3 tools/test_native_layout.py
bash tools/overlay_test/run.sh
bash tools/hw_map_test/run.sh
bash tools/irq_test/run.sh
```

Para repetir apenas falhas: `python3 tools/compile_native.py --retry-failed --jobs 8`.
Depois de mudar overrides: `--refresh-abi` também recompila os consumidores dos
arquivos listados no manifesto. Mudanças gerais de flags/headers requerem o build
completo. `configure_vita.py --native-objects` e `--native-link` expõem os dois passos.

`build/native/recoded.partial.o` é um objeto relocável ARM32 de diagnóstico, não
um executável. Ele permite inspecionar os vínculos reais sem substituir funções
faltantes por stubs. Símbolos ainda pendentes permanecem em `link-report.json`.
O linker de diagnóstico agrupa seções de overlays; ainda falta validar os layouts
completos de DATA/RODATA e todos os aliases interiores antes de um link executável.

## Próximos bloqueios concretos

1. Unidades assembly/CodeWarrior e bibliotecas sem implementação host correspondente.
2. Tipos/protótipos Nitro/NNS restantes, retornos agregados de colisão e vídeo/MobiClip.
3. DATA/RODATA e aliases ainda não ligados, ownership dos statics e libc da decomp.
4. Escritas com efeito colateral em GX FIFO/DMA/VRAM; KH_HW sozinho não reproduz efeitos.
5. Substituir heurísticas de cenas do `platform/hw/game.c` herdado pelo runtime Re:coded,
   conectar preparação → scheduler → NitroMain → loop de vídeo/IRQ e validar no aparelho.

Não há novo VPK jogável nesta etapa. O bloqueio de `--with-game` permanece explícito.

## Resultado anterior — baseline do commit 120b8d9

11.685 unidades compiladas, 80 supridas por backends, 279 fontes BSS representadas
pelo layout gerado, 256 falhas C e 30 fontes não C pendentes. Nenhum backend falhou.
O link relocável terminou com 330 nomes ainda indefinidos (inclui provedores Vita/libc).
`native-integration-summary.json` preserva a lista completa e as falhas por fonte.
As contagens medem unidades, não porcentagem de conclusão ou jogabilidade.

## Continuação validada em 17/11/2026

O estado atual é **11.789 compiladas, 149 falhas, 89 backends, 279 fontes BSS
representadas pelo layout gerado e 24 fontes assembly pendentes**. As seis fontes
C++ ativas agora compilam. O link relocável termina com **235 nomes indefinidos**,
incluindo provedores da plataforma/libc. Nenhum backend falhou. Houve build
completo após as mudanças gerais de headers, seguido de recompilação dos
consumidores dos overrides, rastreados pelos arquivos `.d`.

Foram resolvidos:

- Declarações de seções CodeWarrior convertidas em seções de dados nativas;
  `value_in_regs` continua fora dessa conversão. Includes recursivos corrigidos.
- Temporários de structs materializados com duração de bloco e avaliação única,
  incluindo chamadas aninhadas. Incrementos MSL preservam avanço por palavra.
- Tipos de stream e views FAT/INFO recuperados da árvore EU; correções locais de
  declarações inline, enum e nomes de campos. As views foram testadas nos getters
  originais e verificadas em ARM32, sem substituir os headers completos do SDK.
- `OS_WaitIrq` usa a flag real em DTCM+0x3ff8; `OS_SetTick` e `OS_GetTick`
  compartilham o relógio nativo. CRC16 e Sqrt da BIOS têm implementações C testadas.
- `fsi_rom_archive_state` compartilha a BSS de DMA/lock/archive; quatro aliases
  das strings e o separador possuem dados reais e símbolos relocáveis. Os offsets
  e bytes foram verificados. Nenhum símbolo `fsi_*` ficou indefinido no link.
- Link ordenado por seção/owner/endereço EU, incluindo labels em áreas de dados,
  nomes numéricos e alinhamentos comprovados. Objetos originais ficam preservados;
  objcopy modifica apenas cópias de staging. Os **1.608 pares entre âncoras
  disponíveis** mantêm as distâncias DS. Restam **80 nomes ausentes**, inclusive
  aliases interiores; isso não certifica todos os layouts nem todos os ponteiros.
- Reescrita GX do Days aplicada a 23 arquivos; integração VRAM em 26 arquivos
  (inclui wrappers/headers). Stores viram chamadas ao backend e o cleanup executa
  também em retornos antecipados. C e C++ compartilham o linkage C dos backends.
- Views DIV/SQRT acionam os registradores calculados do Days. A normalização
  vetorial original foi testada com zero, vetor 3/4/5, sinal e alias source/dest.

Comandos adicionais de validação:

```sh
python3 tools/test_portable_rewrites.py
bash tools/msl_strings_test/run.sh
bash tools/tick_test/run.sh
bash tools/bios_math_test/run.sh
bash tools/archive_view_test/run.sh
python3 tools/fs_bindings_test/run.py
python3 tools/test_native_data_order.py
python3 tools/test_graphics_rewrites.py
bash tools/fx_register_test/run.sh
bash tools/gx3d_test/run.sh
python3 tools/audit_native_data.py
```

O refresh agora considera tanto caminhos originais quanto caminhos adaptados nos
`.d`. O script de link efetivamente usado é `build/native/gen/ordered-overlays.ld`.
A auditoria DATA/RODATA é um relatório de cobertura: não transforma nomes ausentes
em aprovação de layout. Seus resultados e a lista de falhas estão no resumo JSON.

### Bloqueios que continuam abertos

1. Wrappers BIOS/assembly restantes, helpers de runtime MSL e interfaces especiais
   de retorno; SDK/NNS ainda incompletos. As 149 falhas permanecem explícitas.
2. Aliases interiores/owners restantes e confirmação de ponteiros em dados,
   incluindo tabelas que não são cobertas pela comparação entre âncoras disponíveis.
3. MobiClip e DS Protect: C++ compilável não implica decoder nem dispatch executável.
4. Completar acessos dinâmicos a VRAM/texturas, DMA e outros efeitos de hardware;
   validar os caminhos reais do jogo, além dos testes sintéticos.
5. Runtime específico Re:coded, preparação/scheduler/NitroMain/loop de vídeo e
   validação no Vita. O diagnóstico 0.1.0 continua sendo a única evidência no aparelho.

**Não há VPK jogável novo e o boot de NitroMain ainda não foi validado/conectado.**


### Continuação: memória, matemática e animação 2D

Mais 19 falhas foram resolvidas: 13 unidades passaram a compilar e seis passaram
para backends nativos. O refresh recompilou 1.182 unidades; o link parcial passou.

- `MIi_CpuClear32` mantém o arredondamento para cima do loop ARM para tamanhos
  parciais; `MTX_Copy33To43` mantém a leitura por linha e o comportamento de overlap.
- SHA-1 reaproveita o núcleo Days com a disposição de contexto Re:coded. O sort
  usa o workspace fornecido e trata largura zero antes de calcular `clz`.
- Views locais de animação/células/SRT recuperam tipos da decompilação; os corpos
  originais continuam responsáveis pelas operações. Layouts ARM32 e set/get de
  frame, incluindo índice inválido e frame inativo, foram testados.
- Os 105 IDs de overlay são constantes numéricas. A tabela vazia de construtores
  main possui terminador nulo nativo; o gerador rejeita uma tabela não vazia até
  que seus construtores sejam resolvidos explicitamente.
- `DC_FlushRange` segue o modelo de memória nativa do backend Days; isso não
  substitui a gestão de cache de GPU/DMA pelos backends Vita.

```sh
bash tools/recoded_memory_test/run.sh
python3 tools/sdk_math_test/run.py
python3 tools/animation_view_test/run.py
python3 tools/test_native_layout.py
```

Todos passaram. A auditoria de dados continua com 1.608/1.608 pares correspondentes
e 80 nomes ausentes. O resultado permanece parcial, sem novo boot no hardware.
