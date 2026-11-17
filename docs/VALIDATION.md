# Validação desta etapa

Validação inicial executada no Mac com VitaSDK GCC 15.2.0.
Depois, os logs fornecidos pelo usuário confirmaram o boot diagnóstico no Vita;
veja NATIVE_INTEGRATION.md e device-tests/. Gameplay ainda não foi validado.

| Verificação | Resultado |
|---|---|
| Dump local `coded.nds` | BK9P, tamanho e SHA-1 iguais ao eu/CONTRIBUTING.md |
| `python3 configure_vita.py && ninja` | ELF, VELF, eboot e VPK diagnóstico gerados |
| `tools/check_elf.py` | ELF diagnóstico passou; referências do jogo ainda não ligadas |
| `bash tools/gx3d_test/run.sh` | `gx3d_test: ok` |
| `bash tools/gpu2d_test/run.sh` | Cenas sintéticas renderizadas em PNG; não é comparação com frames do Re:coded |
| `bash tools/config_test/run.sh` | Limites, persistência, remapeamento e bloqueio de opções Days passaram |
| `bash tools/snd_test/run.sh ../coded.nds 0 1 2` | Banco localizado; 3 sequências processadas sem opcodes desconhecidos |
| `python3 tools/setup_decomp.py` | Cópia isolada do commit fixado criada; origem preservada |

Áudio: banco 42.860.400 bytes, 41 sequências, 465 bancos e 465 wave archives.
Nos trechos de 12 segundos: seq 0 = 204 notas, RMS 9336; seq 1 = 294 notas,
RMS 6078; seq 2 = 453 notas, RMS 6424. Pico de 16 vozes nos três testes.
Esses números mostram que o mixer consumiu os dados reais. Não constituem
comparação bit-exact com DS nem validação do áudio no aparelho.

O teste 2D herdado precisou de um shim de relógio host para o profiler recém
adicionado no Days. O shim só entra no comando de teste; o build Vita usa VitaSDK.

A auditoria completa de compilação grava `build/audit/recoded.json` e logs por
unidade. Fontes são compilados individualmente sem modificações; falhas são
registradas como resultados da investigação, não escondidas nem substituídas por
stubs. Essa auditoria inicial não incluiu link; a integração posterior abaixo
produz um objeto relocável de diagnóstico.

Para aceitar uma build jogável ainda faltam: compilação adaptada, link completo,
boot, primeiro frame, controles/touch, gameplay, save/load, áudio/vídeos, dual-3D
e desempenho no hardware. As opções 3D/áudio do menu são infraestrutura preparada;
no diagnóstico não há gameplay nem renderização de conteúdo 3D do jogo.

Pacote VPK inspecionado: 6 entradas, identidade KHRC00001 e título Re:coded,
sem ROM/save/WAV. O inspetor NitroFS confirmou 986 arquivos e 105 overlays ARM9.

## Auditoria completa Vita GCC

12.330 fontes ativos, nenhum ausente, em 108 módulos. Entre 12.295 unidades C:
**11.836 compilaram e 459 falharam** (96,27% das unidades C compilam sem adaptação).
As outras 35 entradas não foram compiladas pelo probe C. A porcentagem é de
unidades, não bytes de código, progresso do port ou compatibilidade do jogo.

`compile-audit-summary.json` preserva contagens, primeiros erros e lista de falhas;
`build/audit/recoded.json` contém inventário e logs locais completos.

## Integração nativa posterior

Consulte `NATIVE_INTEGRATION.md` e `native-integration-summary.json` para o estado
atual. Os números da primeira auditoria acima são um baseline histórico.

Passaram os asserts ABI no compilador ARM32, as verificações de BSS/DTCM e aliases
compartilhados, o teste do carregador de overlays, o teste dos espelhos de RAM e as rotinas
reais de registro/consulta dos 22 canais de IRQ.
O primeiro link relocável foi produzido sem stubs para funções de jogo ausentes.
O link parcial não certifica um executável nem o boot de NitroMain.


Continuação de 17/11/2026: os testes de temporários, strings MSL, tick, BIOS,
getters de áudio, vínculos FS, ordenação de dados, GX/VRAM e registradores FX
passaram. O link parcial contém 235 nomes pendentes; 1.608 pares disponíveis de
DATA/RODATA mantêm seus deltas DS, com 80 nomes ainda ausentes. Consulte o resumo
JSON atualizado. Nenhum desses testes substitui boot/gameplay no aparelho.


Na continuação, passaram também os testes de memória Re:coded (palavras parciais
e overlap de matrizes), SHA-1 contra hashlib, sort com workspace e casos-limite,
controlador de animação original, layout ARM32 de células/SRT e IDs dos 105 overlays.
Estado: 11.789 compiladas, 149 falhas, 89 backends; link relocável aprovado.
