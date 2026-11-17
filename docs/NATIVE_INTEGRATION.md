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
