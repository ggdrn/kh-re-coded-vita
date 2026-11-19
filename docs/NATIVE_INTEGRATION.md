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

O estado atual é **11.800 compiladas, 138 falhas, 89 backends, 279 fontes BSS
representadas pelo layout gerado e 24 fontes assembly pendentes**. As seis fontes
C++ ativas agora compilam. O link relocável termina com **225 nomes indefinidos**,
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
  objcopy modifica apenas cópias de staging. Os **1.609 pares entre âncoras
  disponíveis** mantêm as distâncias DS. Restam **79 nomes ausentes**, inclusive
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
   de retorno; SDK/NNS ainda incompletos. As 138 falhas permanecem explícitas.
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


### Continuação: alias da câmera e carregamento de imagem

`gCameraLayerIdsByMode` agora é um alias relocável da tabela `gCameraLayerIds`
do ov046. O linker reconhece somente arquivos contendo `.global` e `.equ`, exige
metadados de dados no mesmo módulo/endereço e encontra a seção real do proprietário.
O endereço DS serve apenas à identificação; não é emitido como ponteiro nativo.
A modificação por objcopy ocorre em cópia de staging, preservando o objeto original.
O relatório de link registra `resolved_data_aliases`. A entrada assembly continua
contada entre as 24 fontes não compiladas, mas seu alias está resolvido pelo linker.

Foi corrigida também a declaração antecipada de `GXS_SetOBJVRamModeChar` para
coincidir com sua definição inline local, permitindo compilar
`NNS_G2dLoadImage1DMapping` sem alterar seu corpo.

Validação: `python3 tools/test_native_data_alias.py` verifica sintaxe restrita,
proprietário, seção, offset não nulo em ELF ARM e igualdade dos símbolos reais da
câmera após o link. `python3 tools/test_graphics_rewrites.py` passou novamente.
O refresh recompilou 1.182 unidades. A cobertura de dados passou a 1.609 pares,
com 79 nomes ausentes. O boot e o VPK jogável continuam pendentes.


### Continuação: células com limites e atributos estendidos

A view de animação recupera da decompilação os tipos `NNSG2dCellDataWithBR`,
`NNSG2dCellBoundingRectS16`, `NNSG2dUserExDataBlock` e os atributos de célula.
As funções originais de seleção do início de OAM e encaminhamento de atributos
estendidos recebem esses tipos por overrides locais. O wrapper de nome semelhante
no ov021 também compila, preservando sua chamada original.

O teste de animação executa a seleção OAM para zero a quatro células, com e sem
retângulos de limite. Test spies verificam o endereço recebido pelas rotinas de
unpack chamada pelo main e `ReleaseResourceAndDetach` chamada pelo ov021. O nome
`UnpackExtendedData` do ov021 é enganoso: ele encaminha ponteiro +8 ao destrutor
de recursos, não à rotina de atributos. A relocação EU do ov021 de `0x020a825c`
para `0x0202eefc` (símbolo main `ReleaseResourceAndDetach`) confirma o alvo. Os spies não substituem funções no port e não
certificam o unpack completo. Asserts ARM32 verificam strides de 8/16 bytes para
células simples/com limites, bounds no offset 8 e header estendido de 8 bytes.

Validação: `python3 tools/animation_view_test/run.py`.

Resultado: 11.793 compiladas, 145 falhas e 230 nomes pendentes no link parcial.
Auditoria de dados: 1.609/1.609 pares correspondentes, 79 nomes ausentes.


### Continuação: controle de backgrounds 2D

A view local `nnsys/background_view.h` recupera os enums de backgrounds e GX dos
headers Re:coded. Cinco wrappers passam a compilar, preservando os corpos de
seleção de paleta estendida, configuração afim e configuração 256x16 cores.

`python3 tools/background_view_test/run.py` executa as duas rotinas originais de
controle com a tabela real `NNSiG2dBGCNTTable` adaptada por KH_HW. Verifica os oito
endereços de registradores nas duas telas. Para os BG2/BG3 de cada tela, cobre
os quatro tamanhos, os dois modos de repetição, as 32 bases de mapa e as 16 bases
de tiles com quatro padrões iniciais: 131.072 chamadas no total. Verifica seleção
de tabela/main/sub, bits de
prioridade e mosaico preservados e ausência de alterações nos demais BGs.
Os callbacks de troca de modo são spies do teste; renderização e efeitos completos
de vídeo ainda dependem dos backends e do teste no aparelho. Os seis enums têm
ABI de 4 bytes confirmada pelo compilador ARM32.

Reproduzir após `python3 tools/prepare_native_abi.py`. O refresh recompilou
1.182 unidades e deixou 11.798 compiladas e 140 falhas explícitas.

Link parcial aprovado: 227 nomes pendentes. Auditoria: 1609/1609 pares
correspondentes e 79 nomes ausentes. O boot continua pendente.


### Continuação: cabeçalhos de fontes e texto do menu

`nnsys/font_binary_view.h` recupera da decompilação os cabeçalhos de arquivo/bloco
NFTR e as constantes FINF/versão. O override é restrito ao carregador de fonte.
O menu de dicas usa as declarações canônicas de glyph e vtable; o adaptador exige
as duas definições locais esperadas antes de removê-las, preservando o corpo.

`python3 tools/font_binary_test/run.py` executa o carregador original: versões
1.0–1.3, limpeza das flags somente na versão antiga, bloco FINF ausente, assinatura
inválida, versão inválida e ponteiro nulo. Spies verificam ordem e argumentos das
chamadas de relocação/busca; não substituem essas funções no port nem validam a
relocação completa de uma fonte. O caminho fatal é observado com longjmp no teste.
Asserts ARM32 verificam headers 16/8 bytes, FINF de 20 bytes, ponteiro de glyph no
offset 8, flags no offset 7 e os layouts de glyph/vtable compartilhados pelo menu.

O runtime herdado agora chama kh_recoded_prepare_memory antes de criar a thread de NitroMain e encerra a inicialização se a preparação falhar. game.c compilou isoladamente com Vita GCC. A ligação desse runtime ao VPK e o primeiro frame no aparelho seguem pendentes.

O link parcial passou a incluir main do Vita com KH_WITH_GAME e os objetos de hardware, áudio e core. O ELF define main, kh_game_run, kh_recoded_prepare_memory e NitroMain. As chamadas entre esses componentes têm relocações R_ARM_CALL. O escopo ampliado do link agora expõe 338 nomes indefinidos, incluindo bibliotecas da plataforma. PauseMenu_GetMode continua sendo uma dependência herdada do Days.


### Continuação: primeiro VPK nativo

`OSi_DoResetSystem` (ITCM) passa a ser backend em `asm_replacements.c`: lê o parâmetro
deixado em `HW_RESET_PARAMETER` e reinicia o eboot pelo mesmo caminho de
`OS_ResetSystem`, eliminando `OSi_DoBoot` e `OSi_ReloadRomData`. O HUD one-screen
herdado do Days (`platform/hw/fieldhud.c`) foi removido; ele trazia os três dados
`data_0204c240`, `data_ov002_0207f614` e `data_ov023_0208a784`.

A tabela `.ctor` do ov104 (`gDSProtInitializers`) é emitida pelo GCC em `.data`;
`link_native.py` reconhece a posse pela seção `.ctor` do delink EU em vez de
enfraquecê-la. Os inicializadores continuam chamados por `kh_init_ov104`.

Resultado: 11.879 compiladas, 61 falhas, 94 backends. Link SDK sem nenhum nome
original pendente (os 23 restantes são runtime C/C++ resolvidos no link final).
`check_elf.py` aprovado. `python3 configure_vita.py --with-game && ninja -f
build/native-vpk.ninja` gera `build/VPK/khrecoded-vita-0.1.0-native.vpk`.
O boot no aparelho ainda não foi testado.


### Continuação: primeiro boot no aparelho e endereços DS crus

Primeiro teste no Vita: tela branca. O log mostrou data abort logo após
`NitroMain`, em `far=02fffc40`: `NitroMain → InitEngine → OS_Init →
OS_InitArenaEx → OS_GetConsoleType → OSi_DetectDeviceType → OS_GetBootType`,
que lê o ponteiro devolvido por `OS_GetBootInfo`. Esse corpo `leaf_research` guarda
o endereço numa variável (`u32 value0 = 0x2fffc40U`), padrão que o classificador
herdado do Days não reconhece como endereço.

`prepare_native_abi.py` passa a usar `RECODED_HW_SITES`: a lista revisada dos
literais da `hardware-review.txt` que são endereços fora de cast. Inclui
corpos leaf (boot info, cabeçalhos de ROM, DISPCNT/BGxCNT/BLDCNT), os helpers
`GXx_SetMasterBrightness_`, `GXx_GetMasterBrightness_` e
`G2x_SetBlendBrightness[Ext]_` (chamados pelos aliases `func_`), destinos de DMA
(GX_Init, G3X_InitTable, FIFO GX), bases de VRAM/paleta/OAM dos loaders e a pilha
do launcher em DTCM (`OS_InitThread`, `0x027e0280`). O restante da lista são
máscaras, flags, palavras de controle de DMA, tabelas de ponto fixo ou código não
compilado. Verificado no ELF: `OS_GetBootInfo` relocado para
`kh_ds_shared_area+0xc40`.

`compile_native.py` agora classifica as falhas conhecidas em vez de contá-las:
`cw-asm` (48 corpos CodeWarrior `asm`, substituídos por backend ou sem
referência), `sdk-unit` (9 compiladas por `link_native_sdk.py` com views locais)
e `replaced` (tick do timer 0, releitura de ROM do reset e as duas rotinas RC4 do
DSProt). Resultado: 0 falhas. O link SDK continua sem nenhum nome original pendente.


### Continuação: protection unit do ARM946E

Segundo teste no aparelho: undefined instruction em
`OS_Init → CTRDG_Enable → OS_EnableICacheForProtectionRegion` (`mrc p15`).
O Days só tinha alguns `OS_SetProtectionRegion*` como no-op; no Re:coded a família
inteira compilava do decomp com `__builtin_arm_mrc/mcr`. `asm_replacements.c` agora
mantém um shadow do CP15 (regiões 0–7, cache I/D, write buffer e permissões D),
iniciado com os valores de `INITi_InitCp15`: os setters guardam, os getters
devolvem, nada é aplicado. Uma varredura do ELF confirma que não sobra MRC/MCR
p15 nem outra instrução privilegiada no código do jogo.

Os `udf #0` restantes (82 funções) são traps que o GCC insere após uma leitura de
NULL comprovada em caminhos de erro (ex.: material inexistente em
`NNS_G3dMdlGetMdlAlpha`). A leitura de NULL já falha no Vita antes do trap; no DS ela
leria o ITCM. Ficam como estão até um caso real aparecer no log.


### Continuação: boot emulado no host e argumentos perdidos

`tools/boot_emu/run.py` roda o ELF final do Vita no Unicorn (Cortex-A9): carrega os
segmentos, responde às 267 importações SCE (blocos de memória, mspaces e
`sceClib*` do newlib, I/O do log, TLS, IDs; o resto retorna 0), serve `rom_read` e
`rom_header` do dump, executa `_start` até `main`, o `boot_state` sem vídeo/áudio e
então `NitroMain`. Para no primeiro acesso inválido ou instrução indefinida, com
pilha simbolizada e o log do port. `--trace f,g` mostra argumentos e retornos;
`--vblank N` gera uma VBlank virtual a cada N esperas. Threads Vita criadas pelo
jogo não são executadas.

Achados e correções:

- `OS_GetBootType` lia 0: ninguém preenchia o `bootType` de `HW_WM_BOOT_BUF`, que o
  firmware do DS grava. `FSi_InitRomArchive` só monta o arquivo `rom` com
  `OS_BOOTTYPE_ROM`; com 0 nenhum caminho resolvia e `SoundMgr_Init` escrevia em
  `NULL+0x9c` (próximo crash do aparelho). `boot_state` agora grava 1.
- Com o arquivo montado, `CARD_Init → CARDi_InitRom` lê pela CPU
  (`CARDi_ReadRomWithCPU`, polling de MCCNT1). Agora é backend em `card.c`, lendo do
  dump como `CARDi_ReadRom`.
- `NNS_SndArcInit`: o decomp chamava `FS_ConvertPathToFileID(&fileId)` sem o
  caminho, que o mwcc deixava em r1 (confirmado no código EU). Corrigido em
  `reviewed_source_fixes.py`.

`tools/check_call_arity.py` procura essa classe de erro em todo o código compilado:
protótipos com menos parâmetros do que a definição usa, filtrados pelo código de
máquina EU (registradores r0–r3 lidos antes de escritos, ignorando `push` de
alinhamento e contando o ponteiro oculto de retorno de struct). `tools/ds_disasm.py`
extrai ARM9/overlays da ROM do usuário (BLZ) e desmonta por símbolo EU. Restam 79
chamadas em 72 arquivos para revisão (`build/native/arity.json`), cada uma com a
origem do valor no chamador original (argumento do chamador, campo lido antes ou
retorno da chamada anterior).


### Continuação: argumentos perdidos corrigidos

`tools/check_call_arity.py` agora calcula os argumentos reais por liveness sobre o
grafo de fluxo do código EU (blocos básicos; `bl` destrói r0–r3; escrita condicional
não mata; `push` de alinhamento não é uso), inclui o ITCM (autoloads extraídos por
`tools/ds_disasm.py`, cujos parâmetros de módulo estavam deslocados em 4 bytes),
resolve o nome EU pelos wrappers que incluem o arquivo do chamador e ignora
`return f(...)`. A lista caiu de 79 para 59 chamadas reais; todas estão corrigidas em
`tools/arity_fixes.py` (aplicado por `reviewed_source_fixes.py`, falha se o texto
esperado mudar), cada uma com a origem do valor no EU. Resultado: 0 protótipos
curtos. Ferramentas de apoio: `tools/arity_context.py` (chamada C, entrada do callee e
código do chamador antes do `bl`) e `tools/ds_callers.py` (todos os pontos de chamada
EU de uma rotina e o que cada um põe em r0–r3).

Os que mudam comportamento visível:

- `CARDi_CheckPulledOutCore()` sem o ID de `CARDi_ReadRomIDCore`: a checagem de
  cartão removido comparava lixo com o ID real (tela de erro de cartão no DS).
- `ComputeOneMinusSquareFraction` era `void`, mas o original devolve o `FX_Sqrt`
  final; `ApplyCurrentFieldMode(entry)` devolve o resultado de `AddStageCaptionLine`
  (o `menuDepth` do comando de estágio).
- Repasses: `StopSeqArcOrDefault(arc, índice, fade)`,
  `RenderMovieFrameIfPresent(decoder, a, b, c)` e
  `MenuScreen_RefreshMarker(screen, dialog, w, h)`.
- `IsSoundParamStale` recebe o modo (≠ 8) ou o `flag` testado (0), conforme o caminho.

Overlays que dividem endereço: a relocação EU lista os dois
(`module:overlays(a,b)`) e o wrapper escolheu o errado em sete chamadas, já
corrigidas: os quatro menus ov075–ov078 chamam `SetupMainBgLayers` do ov039 (não o
`InitBattleGaugeContext` do ov045, que alocaria 0x1a4c bytes a cada fechamento), e a
tela de itens ov077 abre o `OpenStatusRecordList` do ov073 (não a comparação do ov041).
No EU há 198 chamadas com relocação ambígua: 178 têm um único candidato que o overlay
chamador referencia sem ambiguidade em outro ponto; 20 seguem ambíguas. A auditoria
dos wrappers contra essa escolha ainda não foi feita.


### Continuação: divisor e raiz quadrada de hardware (CP)

O cálculo em `platform/hw/memmap.c` confere com o GBATEK. Ele cobre os modos 32/32,
64/32 (e o 3, igual ao 1) e 64/64. Na divisão por zero, o quociente é ±1, com a palavra
alta invertida no modo 32, e o resto é o numerador. O overflow `MIN/-1` também está
tratado, o bit 14 testa o denominador inteiro de 64 bits, e a raiz é calculada em 32 ou
64 bits. Os resultados são calculados quando lidos via `KH_HW`. Nenhuma unidade
compilada acessa esses registradores por símbolo de linker. As rotinas FX do ITCM leem
o resultado sempre via `KH_HW`, inclusive as que guardam um ponteiro-base para `DIVCNT`.

Mudanças:

- `DIVCNT` e `SQRTCNT` também sincronizam ao serem lidos (`kh_hw_map.h`). No DS, o
  flag de divisão por zero muda assim que o denominador é escrito. Antes, ele só era
  atualizado quando alguém lia o resultado.
- `CP_SaveContext` e `CPi_RestoreContext` saíram de `asm_replacements.c` e foram para
  `platform/nitro/cp.c`. O restore recalcula as duas unidades na hora, como o DS faz
  ao reiniciá-las com os parâmetros restaurados. O `TODO(cp)` antigo foi resolvido.

`tools/cp_register_test/run.sh` usa uma referência escrita a partir do GBATEK,
independente do código do port. São 400 mil divisões aleatórias com valores-limite em
todos os modos, 200 mil raízes, os casos do GBATEK escritos um a um e o flag lido logo
após a escrita. O teste também roda as rotinas FX reais do decomp (`FX_Div`, `FX_Inv`,
`FX_DivFx64c`, `FX_InvFx64c`, `FX_Sqrt`, `FX_DivAsync`/`FX_InvAsync` com
`FX_GetDivResult[Fx64c]`) e uma troca de contexto no meio de uma divisão. Resultado:
2.650.142 verificações, 0 falhas.


### Continuação: primeira VBlank e handles empacotados

Terceiro teste no aparelho: o jogo desenhou quadros (motor 2D ativo, DISPCNT ligado) e
falhou na primeira VBlank: prefetch abort em `pc=0x01ff8000` na thread de IRQ.
`InitVBlankInterrupt` registrava `OS_SetIrqFunction(1, (void *)0x1ff8000)`, o endereço
do `OSi_VBlankInterruptHandler` no ITCM. Agora passa o símbolo
(`tools/pointer_fixes.py`). Uma varredura das unidades compiladas por literais na faixa
do ITCM achou mais três: `CARDi_IsRomDmaAvailable`, que só testa faixa e é inofensivo,
e os dois decodificadores de handle abaixo.

Handles de arquivo: o jogo empacota ponteiros como
`0x80000000 | ((ptr + 0x8000) & 0xfffffc) << 7 | índice` em 328 pontos e os
desempacota somando `0x01ff8000`. Os carregadores (`FileLoader_LoadAlloc`,
`RequestFileLoad`, `LoadFileIntoBuffer`, `OpenAndClassifyFile`) distinguem handle de
caminho pelo bit 31, que todo ponteiro do Vita tem. O runtime herdado do Days já
posiciona a arena principal numa janela de 16 MiB (`os.c`) e oferece
`kh_ds_unpack_ptr` e `kh_is_packed_handle`; no Days a ligação vinha de um patch no
decomp. No Re:coded, `pointer_fixes.py` liga os dois decodificadores e os quatro testes.

Build: `tools/build_vpk.py` sobe o patch de `VERSION` e gera
`build/VPK/recoded_v<versão>.vpk`. O título e o STITLE do `param.sfo` incluem a versão,
e o TITLE_ID fica fixo, então a bolha é sempre a mesma.


### Continuação: tela de título (v0.0.1 → v0.0.2)

A v0.0.1 chegou à tela de título: carregou o ov000, o ov104 e o ov027, criou o save e
registrou os marcos `title update completed`, `title frame presented` e `title VBlank
advancing`. Depois falhou com data abort em `far=0x06833c00` (VRAM LCDC, banco B),
pela cadeia `Tex_LoadVram → Gfd_LoadTex → GX_LoadTex → MIi_DmaSetParameters`.
`GX_BeginLoadTex` e `GX_BeginLoadTexPltt` calculam em tempo de execução o endereço LCDC
dos bancos (`tabela << 12`), e o DMA recebia esse número. Agora passam por `KH_HW` no
cálculo, como nos `HW_EDITS` do Days. `KH_HW(0)` continua 0, então o teste de "sem
segundo bloco" do `GX_LoadTex` segue igual. Os carregadores de paleta estendida já
usavam endereços com `KH_HW`.


### Continuação: New Game e referências entre overlays (v0.0.3 → v0.0.4)

A v0.0.3 já mostrava a tela de título com áudio e texturas. No New Game, carregou o
ov003 e falhou em `Obj_Construct`, lendo `0xeb000573` (uma instrução ARM) como
ponteiro. `UpdateTitleOverlayLoad` criava a tarefa da cena com
`UpdateMenuTouchSelect`, uma função do ov002. O alvo certo é `gMovieSceneTaskClass`,
dados do ov003 no mesmo endereço; a relocação EU é `module:overlays(2,3)`.

`tools/check_overlay_targets.py` audita as referências com relocação ambígua.
Escolhe o candidato pelos overlays que o módulo chamador alcança sem ambiguidade em
outros pontos, e só depois pelo tipo (chamada exige função). Depois compara com o
nome que o C usa, via wrapper EU e `#define`. Resultado:

- 46 referências no código nomeavam o overlay errado, corrigidas em
  `tools/overlay_target_fixes.py` (tabela revisada). Nos menus ov073–ov085, havia 18
  chamadas a `SetupStageParams` (ov034) no lugar de `SetupScrollList` (ov039), além
  de `SetScreenBrightness`, `UpdateScrollListInput`, `LoadSlotBgCharacters` e
  `InitScrollListWidgets`. No campo, `GetCameraFollowFlags`, `GetCameraFlag800` e
  outros do ov042/ov043. Em quase todos, o candidato do decomp tem 0 referências
  inequívocas a partir do módulo chamador, e o escolhido tem de 2 a 50.
  `InstallSessionOv029Handlers` ficou como está (o nome indica ov029).
- `LoadPanelOverlay14/15` chamavam o init do ov013. Agora chamam o do próprio overlay.
- Registros de menu do ov039 (`gSecondaryMenuRegistryTail`, `gPrimaryMenuRegistryTail`):
  são pares `{id do overlay, descritor}`, e o decomp nomeou todos os descritores com
  nomes de outros overlays. Foram reconstruídos pelo id de cada par
  (`pointer_fixes.MENU_REGISTRIES`): 12 + 19 descritores.
- Ficam como estão os casos "assumed" (o nome ou o contexto confirma a escolha do C).


### Continuação: após as CGs (v0.0.7 → v0.0.8)

A v0.0.7 passou pelas duas primeiras CGs (ov003 e ov022/MobiClip) e falhou ao montar
o primeiro campo. O caminho foi `InitFieldManager → CreateFieldHudWidgets →
InitFieldPanelScene → FS_LoadOverlayImageAsync`, que terminou numa leitura de
0xbfa00 bytes para `0x020b5820`, o endereço de RAM DS do overlay. O backend cobria
`FS_LoadOverlayImage` e `FS_StartOverlay`, mas não a versão assíncrona do SDK
(`InitOverlayFromPair`). `overlay.c` agora a implementa: abre o arquivo do overlay
como o SDK, para que `FS_WaitAsync`/`FS_CloseFile`/`FS_StartOverlay` do chamador
funcionem, e restaura o estado do overlay linkado sem gravar no endereço DS.

Auditoria da API gráfica, nas unidades compiladas de GX/G2D/G3D/GFD e do jogo:

- Endereços DS literais: todos passam por `KH_HW`. Revisado antes.
- Endereços calculados em tempo de execução: os únicos eram os bancos LCDC de
  `GX_BeginLoadTex[Pltt]`, já corrigidos. Os demais cálculos com deslocamento são
  valores (frações, máscaras, campos de registrador) ou offsets somados a bases já
  convertidas, como `G2_GetBGxCharPtr`/`ScrPtr` e `G2S_GetBG0ScrPtr() + …`.
- Referências entre overlays: auditadas na v0.0.4.
- Caminhos do SDK que escrevem no endereço DS de um overlay
  (`FS_LoadOverlayImage[Async]`, `FS_StartOverlay`): todos no backend.


### Continuação: chamadas sem argumento (v0.0.8 → v0.0.10)

- v0.0.8: o heap corrompeu em `FreeFieldObjectClassAnimationBuffers`, que chamava
  `NNSi_FndFreeFromDefaultHeap()` sem o buffer. `tools/check_call_sites.py` passou a
  verificar cada chamada nas unidades compiladas: arquivos só-EU, protótipos `()` e
  nomes já resolvidos por `#define`. Um caso só entra quando o chamador EU prepara o
  registrador antes do `bl`. As correções estão em `tools/zero_arg_fixes.py`, em três
  formas: o valor testado no `if`, o primeiro operando dos
  `ResolveTaggedValueRef(ctx, ops)` e alguns casos isolados.
- v0.0.9: a v0.0.9 travou em `UnloadSubsceneOverlayAndDestroyTask →
  DestroyRegisteredObject`, que saltou para dados do heap. `DestroyTaskObjectWrapper`
  é um trampolim (`ldr ip, =f; bx ip`), e a liveness o tratava como sem argumentos.
  Agora `check_call_arity.original_live_args` herda os argumentos do destino de cada
  veneer e de cada tail call, o que expôs essa função e outras. As 3 chamadas foram
  corrigidas, e o padrão do valor testado passou a aceitar também `!= -1`.
- Pendentes de revisão: cerca de 20 chamadas sem argumento com evidência ambígua (por
  exemplo `GetActiveMenuScene` em callbacks, `GetPrimaryMenuSubOverlayIndex` e
  `UpdateMenuTouch`), 22 protótipos curtos marcados depois da mudança na liveness (a
  maioria parece colisão de endereço entre overlays na análise) e as chamadas com
  argumentos parciais (pares de 64 bits geram ruído).


### Continuação: despachantes de overlay (v0.0.10 → v0.0.11)

A v0.0.10 jogou mais de 150 s: campo, troca de área e menu. Ao sair do menu, travou em
`ShutdownHandlersAndExit` (ov039) → `HasOv029ObjectField28` → `Obj_GetWord28(NULL)`.
A chamada do ov039 vai para `0x020baa60`, que é a função do ov029 (sessão) ou do ov033
(retomada), conforme o overlay carregado. No DS isso se resolve sozinho; uma escolha
estática erra em um dos contextos. Pelo mesmo motivo, `UpdateOverlayFrame` alterna
entre ov075, ov076 e ov080.

O runtime herdado do Days já tinha a solução: `tools/ovdisp.py` gera um despachante
por endereço compartilhado, e `kh_ovdisp_resolve` (`overlay.c`) desvia para a função
do candidato carregado por último. No Days isso vinha de um passo do reescritor do
decomp. No Re:coded esse passo não estava ligado. `prepare_native_abi.py` agora:

- gera `build/native/gen/ovdisp.S` (61 endereços, 111 candidatos), compilado e linkado
  por `link_native.py`;
- faz cada arquivo fora do overlay dono de um candidato referenciá-lo pelo
  despachante (`#define nome kh_ovd_nome`, 180 arquivos). A exceção são os nomes que o
  próprio arquivo define, seja como função ou com `#define`.

Isso cobre todas as chamadas e todos os ponteiros de função para endereços
compartilhados, inclusive os casos "assumed" e "undecided" da auditoria. As escolhas
estáticas de `overlay_target_fixes.py` continuam válidas para os casos de dados
(`gMovieSceneTaskClass` e os registros de menu).

Link final: `tools/link_vita_elf.py` mede a folga entre o fim do código e o início dos
dados. Quando ela fica abaixo de 8 KiB, refaz o link com um enchimento no código, para
que o `vita-elf-create` tenha onde gravar os dados SCE. Na v0.0.11 sobravam 0x620 bytes.

Em aberto:
- o 3D aparece com polígonos esticados ao infinito, enquanto o HUD 2D está correto;
- a arma não aparece;
- as falas pulam sozinhas. Nesses trechos, os canais 11/12 (PCM16 a 16 kHz, 2 KiB em
  anel) são reiniciados a cada 0,25–1 s, então a verificação de fim de stream de que o
  texto depende deve estar retornando "terminou" cedo demais.


### Continuação: containers de bitfield (v0.0.11 → v0.0.12)

Log da v0.0.11, ao apertar Start numa cena: `TryEnterFieldPause →
SuspendFieldForPause → SetTweenPaused` falhou por alinhamento (`fsr=0x801`), com um
`strd` do tick de 64 bits em `0x8245255e`. O ponteiro do `FieldManager` estava certo; o
layout não. No mwcc, um grupo de bitfields ocupa o tipo declarado inteiro: depois de
`u32 a:1 … :1` (10 bits em 0x480), o `u8 pad_484[]` começa em 0x484. O GCC (AAPCS)
coloca o membro `u8`/`u16` seguinte no primeiro byte livre (0x482), e todos os campos
depois dele ficam 2 bytes antes: o tween ia para 0x552 em vez de 0x554.

`portable_rewrites.bitfield_containers` (aplicado por `prepare_native_abi.py` em todo o
código) insere `TIPO : 0;` depois de cada grupo de bitfields seguido de um membro
comum, fechando o container como faz o mwcc. São 799 structs em 612 arquivos. Quando o
membro seguinte já está alinhado, o layout não muda. Verificado no ELF:
`SuspendFieldForPause` passa `manager + 0x550 + 4`.

Outros sintomas da v0.0.11 que podem vir do mesmo layout:
- crash ao pegar a arma: `ActorSlot_AddPriorityByIndex` encontrou o slot do ator nulo
  (`ScriptCmd_ReleaseOrDisableStageEvent`), embora o C confira com o original;
- 3D destruído e falas pulando.
Ainda não confirmados no aparelho.


### Continuação: ABI de float, slot nulo e rastro do script (v0.0.12 → v0.0.13)

Log da v0.0.12: falas ainda pulando; crash ao começar a primeira batalha, de novo em
`ScriptCmd_ReleaseOrDisableStageEvent → ActorSlot_AddPriorityByIndex(14, -1)`; e um
`call to 00000002` a partir de `NewtonSolveFloat`.

- **ABI de float.** O mwcc passava floats em r0–r3 como inteiros; o Vita é hard-float
  (floats em s0–s15). `NthRootFloat` declarava `NewtonSolveFloat(float, int n, …)`
  contra a definição `(float, float target, …)`: `n` caía em r0, onde a definição lê o
  ponteiro de função. Além disso os dois callbacks (`PowThenAddFloat`,
  `PowDerivativeTimesN`) são soft-float (u32 em r0–r2). `tools/float_abi_fixes.py`
  compara classes float/inteiro de cada declaração com a definição (só nas posições
  que o chamador passa: `Fabs_02022ac4(double x, double y)` lê o mesmo registrador) e
  reescreve `NthRootFloat` com `powf` nativo (raiz real; n ímpar mantém o sinal).
- **Slot nulo.** `ReleaseOrDisableStageEvent` libera o ator e o comando, logo em
  seguida, soma prioridade no mesmo slot, já `NULL`. No DS o `strb` vai para
  `0x0000000b` (espelho do ITCM) sem falhar; aqui a escrita é ignorada e registrada
  uma vez (`ds: ActorSlot_AddPriorityByIndex(14): NULL object …`).
- **Rastro do VM de script** (`platform/core/script_trace.c`). `ScriptVm_RunFrame`
  passa cada handler por `kh_script_run`/`kh_script_resume`: as primeiras 6000
  execuções vão para o log (`script: cmd GG:II len … handler … -> resultado`) e as
  últimas 128 são despejadas em cada FAULT. `tools/symbolize.py` (ELF padrão agora
  `build/native/khrecoded.elf`) dá nome aos handlers. Serve para achar qual espera
  (resultado 0) termina cedo demais nas falas.
- `tools/check_void_returns.py`: rotinas que o decomp define `void` mas cujo original
  deixa um valor em r0 no retorno. 50 casos, nenhum handler de script; a maioria são
  cálculos de bitfield/switch sem uso do resultado.
