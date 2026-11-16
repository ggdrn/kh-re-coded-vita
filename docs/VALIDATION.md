# Validação desta etapa

Executada no Mac com VitaSDK GCC 15.2.0. Nenhum teste em PS Vita físico.

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
stubs. Não existe link do jogo nesta etapa.

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
