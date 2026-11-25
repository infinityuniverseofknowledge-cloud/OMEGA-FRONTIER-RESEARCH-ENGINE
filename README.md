# OMEGA FRONTIER RESEARCH ENGINE — protótipo experimental, ciclos 1–3

Autor: Miqueias B Werlich. Marca editorial: Infinity Universe of Knowledge.

Este é um protótipo experimental offline, não o sistema completo. Não contém 20 livros completos nem 120.000 registros, não comprova P versus NP e não valida hipóteses biológicas. Não altera o projeto PNP-OMEGA existente. Há um primeiro livro em rascunho, laboratórios de SAT, otimização e modelos sintéticos, painel local e experimentos limitados.

## O que funciona

- `omega/mathcore.py`: transformada de diferenças modulares com âncora e inversa, frequências, distância de Hamming, TSP exato Held–Karp e heurística vizinho mais próximo + 2-opt. TSP: matrizes inteiras simétricas não negativas de 1 a 14 vértices. O método exato tem custo exponencial; o limite existe para proteção de recursos.
- `omega/knowledge.py`: banco SQLite com fontes, evidências, 12 cenários sintéticos, buscas e FTS5 opcional. `search_evidence` procura substrings literais em alegações e trechos com casefold Unicode (por exemplo, `ação` encontra `AÇÃO`), independentemente de FTS; não remove acentos nem normaliza Unicode. Ela varre o texto, não usa o índice FTS e pode ficar lenta em bancos grandes. São somente três tabelas, não o esquema integral solicitado. O gerador presente não é uma fábrica validada de 120.000 registros.
- `omega/simulation.py`: simulação ecológica abstrata com seed, parâmetros e bandas de variação sintética. Não foi calibrada com observações e não prevê ecossistemas reais.
- `apps/digit_lab/index.html`: laboratório offline de dígitos. Abra o HTML localmente com JavaScript habilitado. Não depende de servidor nem rede. Esse laboratório ainda não se conecta ao SQLite e não realiza TSP.
- `run_demo.py`: gera uma base SQLite, um relatório reexecutável com hashes e um experimento de transformação, rota e simulação. Não sobrescreve a base existente; resultados são gravados em `results/`.
- `omega/optimization.py`: benchmark limitado com Held–Karp, vizinho mais próximo, 2-opt, simulated annealing, tabu e algoritmo genético; sementes e gaps explícitos.
- `omega/sat.py`: enumeração limitada de CNF, verificadores de certificados, minimalidade por exclusão de cláusulas e resolventes binários; não resolve P versus NP.
- `omega/models.py`: vetores de solo sintéticos e autômato celular 2D sem calibração real.
- `books/index.html`: catálogo offline com o Livro 01 em rascunho e outros 19 ainda não escritos. A revisão editorial permanece pendente.
- `omega/server.py` e `apps/dashboard/`: painel experimental com API limitada a `127.0.0.1` para dígitos, SAT, TSP e modelos sintéticos. Não há autenticação; outros processos locais podem acessá-lo. Não exponha na rede.
- `omega/theorem_graph.py`: grafo curado pequeno, dependências e busca de rotas limitadas; pontuações são editoriais, não provas matemáticas.
- `omega/research_cycle.py`: execução limitada e reproduzível de experimentos com parâmetros e hashes; resultados em `reports/`, sem garantia de imutabilidade.
- `tests/`: testes dos módulos usando somente a biblioteca padrão do Python.

## Como reproduzir

Requer Python 3.10 ou superior. Na pasta do projeto execute `python -m unittest discover -s tests -v`, `python -m omega.research_cycle` e, para o painel, `python -m omega.server`. Abra o endereço local impresso pelo servidor. O antigo laboratório de dígitos abre diretamente sem servidor. O relatório especifica parâmetros, seed e versões; timestamps e caminhos variam. Não é instalado software nem acessada internet.

## Interpretações Y–Delta

1. [ESTABLISHED] Estrela–triângulo: equivalência de redes de três terminais em circuitos; não equivale à transformação de dígitos.
2. [PROPOSED] Representação: diferenças sucessivas modulares de um vetor de dígitos, com âncora. Escolhida pela definição precisa e inversa simples.
3. [PROPOSED] Coordenadas: pares âncora/diferenças representam a mesma sequência; são coordenadas discretas no produto de resíduos, não coordenadas geométricas comuns.
4. [PROPOSED] Operador abstrato: composição de uma representação com uma diferença modular; invertibilidade depende da representação, da âncora e do domínio escolhido.

Para base b ≥ 2, n ≥ 1 e x ∈ {0,…,b−1}^n, defina y₀=x₀ e yᵢ=(xᵢ−xᵢ₋₁) mod b. A inversa é x₀=y₀ e xᵢ=(xᵢ₋₁+yᵢ) mod b. A reconstrução passo a passo demonstra bijetividade para base e comprimento fixos. Os módulos aceitam bases 2–10 e strings, preservando zeros iniciais. A diferença finita é técnica conhecida; não se reivindica originalidade nem compressão apenas pela bijeção. A saída de `modular_difference` omite a âncora: guarde-a separadamente.

[PROPOSED] Linear Digit Path: sequência ordenada de strings de mesmo comprimento, com custo Hamming entre strings consecutivas; é uma escolha operacional inicial, não conceito estabelecido. Uma rota TSP otimiza o custo definido; não prova teorema nem revela por si só significado semântico.

[REFUTED] A soma dos dígitos nunca aumenta: em base 10, `10` transforma-se em `19`, de soma 1 para soma 10. Sem âncora, `00` e `11` geram ambas a diferença `0`: a perda de informação é real, com b pré-imagens para cada sequência de diferenças de comprimento fixo.

## Evidência e limites

Os registros de cenário são hipóteses sintéticas sem alegação de existência natural. Os quantis da simulação só descrevem o ruído arbitrário do modelo, não intervalos de confiança empíricos. Não há validação empírica, análise estatística de dados reais, testes 3-opt, grandes bancos semânticos, geração de tratados completos, pipeline de pesquisa totalmente integrado ou publicação automática. O módulo SAT é deliberadamente pequeno e exaustivo. Não chame os componentes ausentes de concluídos. Não inclua dados sensíveis na base de demonstração.

## Fontes verificadas para fundamentos

- Held, Michael; Karp, Richard M. (1962), “A Dynamic Programming Approach to Sequencing Problems”, Journal of the Society for Industrial and Applied Mathematics 10(1), 196–210, DOI 10.1137/0110015. https://doi.org/10.1137/0110015
- Tse, Chi K., “Equivalence of ‘Star’ (Y) and ‘Delta’ Circuits”, material universitário. https://www.eie.polyu.edu.hk/~cktse/linear_circuits/main/node16.html
- Grimm et al. (2020), “The ODD Protocol for Describing Agent-Based and Other Simulation Models”. https://www.jasss.org/23/2/7.html
- “Finite Difference”, Wolfram MathWorld. https://mathworld.wolfram.com/FiniteDifference.html

## Próximos ciclos

1. Expandir e validar o esquema com proveniência e padrões de interoperabilidade.
2. Benchmark com vários casos, medição de tempo/memória e contraexemplos; TSP com objetivos explícitos e restrições de dependência.
3. Integrar navegador, banco e experimentos sem criar serviço exposto por padrão.
4. Pesquisa bibliográfica revisada e catálogo semanticamente validado, em lotes; não inflar registros para alcançar uma meta numérica.
5. Construir livros individualmente a partir de resultados e fontes auditáveis, com direitos e licença a confirmar. Nenhuma licença de publicação comercial é concedida ou presumida neste pacote.


## Distribuição pública

O livro em rascunho e a base SQLite local não estão incluídos nesta distribuição, pendentes de revisão de direitos e dados. Nenhuma licença de direitos autorais é concedida neste repositório.
