# Proveniência

A infraestrutura platform/ e os testes/ferramentas foram derivados do checkout
local khdays-vita. docs/days-source-manifest.json registra a origem exata por hash.
Os comentários e atribuições originais foram preservados. Nenhuma nova licença
é atribuída aqui ao código herdado.

platform/compat/stb_image.h: Sean Barrett e colaboradores, domínio público ou MIT,
conforme o texto incluído no próprio arquivo.

A decompilação Re:coded é uma dependência separada: raiz MIT, árvore europeia CC0;
consulte LICENSE, eu/LICENSE e eu/THIRD_PARTY_NOTICES.md no checkout correspondente.
O código de jogo não integra este repositório; setup_decomp.py prepara uma cópia
local ignorada pelo Git. ROM, conteúdo do jogo e marcas pertencem aos titulares.

O header platform/compat/recoded/nnsys/fnd.h foi recuperado do checkout local
khdays-decomp/include/nnsys/fnd.h (árvore CC0). Os headers de compatibilidade
Re:coded e as declarações IRQ recuperam definições da decompilação local;
os caminhos de origem estão registrados nos comentários e na documentação.

As passagens de comandos GX/VRAM e ordenação de dados reutilizam os algoritmos
preservados em reference/days/tools/. Os contratos BIOS e views de arquivos de
áudio/filesystem vêm de eu/docs/library/sdk_bios.md e dos headers internos da
cópia Re:coded EU. As fontes originais permanecem intactas.
