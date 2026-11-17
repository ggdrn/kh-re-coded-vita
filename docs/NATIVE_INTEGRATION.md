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

## Resultado da recompilação completa

11.685 unidades compiladas, 80 supridas por backends, 279 fontes BSS representadas
pelo layout gerado, 256 falhas C e 30 fontes não C pendentes. Nenhum backend falhou.
O link relocável terminou com 330 nomes ainda indefinidos (inclui provedores Vita/libc).
`native-integration-summary.json` preserva a lista completa e as falhas por fonte.
As contagens medem unidades, não porcentagem de conclusão ou jogabilidade.
