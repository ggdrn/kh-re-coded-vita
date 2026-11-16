# Paralelos Days → Re:coded

## Evidência e limites

Origem: checkout local `khdays-vita`, incluindo arquivos modificados localmente;
commit de referência e hashes estão no manifesto. Foram consultados README,
ARCHITECTURE, resumos de sessões, notas de releases, código platform/, ferramentas
e o patch de decompilação. Na origem Re:coded: README, eu/docs/PORTING_GUIDE.md,
SOURCE_LAYOUT.md, índice de sistemas, configurações e wrappers de fontes EU.

A versão EU reconstrói 108 módulos ARM9 (main, ITCM, DTCM e 105 overlays).
Isso inclui bibliotecas ARM verificadas; não significa que toda essa implementação
já possa ser compilada como C portátil. Não houve nova execução do gate DS nesta
etapa. A própria documentação distingue reconstrução byte-exact e port para host.

| Área | O que o Days já resolveu | Aplicação ao Re:coded / pendência |
|---|---|---|
| ABI | ARM32 little-endian; signed char, enums de 32 bits, wrap de inteiros, sem strict aliasing | Flags preservadas. Auditar interfaces CodeWarrior, retornos em registradores, structs e ponteiros; ARM32 comum não prova ABI idêntica. |
| Hardware | KH_HW, RAM/VRAM/IO, divisão, raiz, DMA e IRQ | Reaproveitar backend; remapear os acessos dos fontes Re:coded e seus símbolos absolutos. |
| Geometria | FIFO GX, matrizes, luz, clipping, cache de texturas | Teste host do GX passou. Conectar funções Nitro e submissão do Re:coded. |
| Rasterização | VitaGL, transparência A3I5/A5I3, profundidade, stencil por ID | Preservada como candidata; ainda sem frame real do Re:coded. |
| Duas telas | Captura, alternância 3D, registros por quadro, layouts | Manter ambas. Não inferir cenas pelo número de overlay do Days. |
| Composição | Anel de texturas, upload do contador só quando muda, filtros 2D | Implementação herdada; apresentação disponível no diagnóstico. |
| Desempenho | 30 fps estáveis via swap interval; interpolação e resolução dinâmica | Manter 60 fps experimental/desligado. Medir novamente em cenas Re:coded; não transferir números de FPS do Days. |
| ROM | Cache de 16 MiB, blocos 64 KiB, leitura antecipada | Leitor preservado; identidade BK9P e hash corretos. Dados em pasta própria. |
| FS/overlays | NitroFS, overlays residentes, reset de DATA/BSS, construtores | Regenerar tabelas e relocações por banco do Re:coded. Não reaproveitar aliases/endereço de Days. |
| Áudio | SSEQ, PCM/ADPCM/PSG, cache ADPCM, mixer por canal, saída Vita | Banco real está em `sd/sound_data.sdat`, e não `snd/`. Testes host com sequências reais já executados. Ponte PXI/ARM7 ainda não conectada ao jogo. |
| Vídeo | Decoder portátil MobiClip e esperas sem busy-loop | Referência preservada. Days usa ov024; Re:coded tem código MobiClip em ov022 e wrappers em outros bancos. Adaptar contratos e validar vídeos. |
| Input | Botões, analógico esquerdo, touch, remapeamento e rear touch | Base preservada. Câmera direita, deck e R-toggle específico desabilitados até mapear funções reais. |
| Saves | Backup em memória, arquivo temporário e flush no suspend | Código preservado. Confirmar chip, capacidade e protocolo no Re:coded antes de ativar; não assumir 64 KiB do Days. |
| HUD/ícones | Substituição de tiles/glifos, parceiros e composição de HUD | Específicos do Days; desativados. Não aplicar offsets, hashes de tiles ou heurísticas de Roxas/Sora. |

## Configuração adotada

Menu com VIDEO, SCREEN, GAMEPLAY, BUTTONS e SYSTEM. Presets de resolução,
filtros, aspecto, organização/ordenação das duas telas, inset, controles gerais,
remapeamento, volume e idioma. Config própria por whitelist: chaves do Days não
ativam funções legadas. Padrão 4:3 e duas telas; widescreen permanece selecionável,
ainda dependente de validação com o jogo. A identidade da aplicação também é nova.

Não há opção de tela única. Os quatro setters de apresentação single-screen
forçam OFF. O código legado de composição permanece como referência técnica,
mas não é ativável pelo menu/configuração.

## Sequência de integração

1. **Inventário e compilação:** usar `eu/config/arm9/**/delinks.txt`, nunca glob de
   `src/` + `eu/src/` juntos. Os wrappers EU fazem aliases e incluem corpos comuns;
   compilar ambos duplicaria símbolos e misturaria regiões. Probe registra falhas
   individuais sem modificar a decompilação.
2. **Bibliotecas e ABI:** mapear substituições Nitro por símbolo/contrato. Tratar
   asm CodeWarrior, `__declspec(value_in_regs)`, headers incompletos e casts que
   dependem do compilador. Não apagar atributos ABI apenas para compilar.
3. **Dados e link:** gerar BSS e aliases interiores com base nos delinks, símbolos
   e relocações EU. Preservar propriedade por overlay, mesmo quando dois bancos
   compartilham endereço DS. Falhar em referências não resolvidas; sem stubs de
   gameplay que deem uma falsa impressão de boot funcional.
4. **Boot:** conectar NitroMain, arenas, scheduler, IRQ, PXI, ROM e reset dos
   overlays. `platform/hw/game.c` ainda é a integração Days, não um game loop
   validado para Re:coded; suas heurísticas precisam ser substituídas.
5. **Primeiro frame:** conectar GX/VRAM e comparar logo/menu com uma referência
   DS, nas duas telas. Só depois validar widescreen, captura e dual-3D.
6. **Gameplay/save:** movimento, combate, câmera, deck, touch e telas por modo.
   Só expor hooks específicos após localizar os contratos Re:coded. Verificar
   save/load e suspensão com backup de um save de teste.
7. **Áudio/vídeos/desempenho:** integrar eventos ARM7, sincronismo e MobiClip;
   medir CPU/GPU, hitches, cache e memória no aparelho antes de otimizar.

## Lições do Days a preservar

- Não colapsar BSS compartilhado em objetos weak independentes.
- Não usar aliases absolutos para endereços relocáveis dentro do ELF Vita.
- Não deixar libc da decomp substituir a newlib e criar recursão em strlen/memcpy.
- Manter propriedades de DATA: ordenação, alinhamento e zeros inicializados.
- Evitar uploads redundantes do overlay/FPS e cópias de textura por quadro.
- Snapshot de registros e fator widescreen pertencem ao quadro/tela correspondente.
- Não portar estado de cena, câmera e HUD por semelhança de nomes/IDs.
- Validar renderização, áudio e desempenho separadamente; compilação não é boot.

## Mapeamento inicial de substituições Nitro

`nitro-adapter-candidates.json` registra as 28 substituições explícitas do Days:
19 possuem nome exato na tabela EU. Endereços e bancos são evidência de localização,
não destinos de ponteiro Vita. Os outros 9 exigem rastrear corpo/callers e aliases.

## Resultado do primeiro compile probe

11.836 / 12.295 unidades C compilam; 459 falham. Há mais 35 entradas fora do
probe C. Entre os primeiros erros: 110 em declarações `__declspec`, 65 em
sintaxe com `void` após asm, 22 por `nnsys/fnd.h` ausente e 21 por
`NNSG2dCharaColorMode` não declarado. A contagem é por primeiro erro de unidade;
resolver um pode revelar outros. Relatório persistido em compile-audit-summary.json.

Prioridade prática: separar bibliotecas substituídas pelo backend (não precisam
compilar como no DS) dos fontes reais de gameplay; fornecer headers compatíveis;
adaptar retornos/callers conjuntamente; então realizar o primeiro link para
inventariar DATA/BSS/relocações ainda sem definição.
