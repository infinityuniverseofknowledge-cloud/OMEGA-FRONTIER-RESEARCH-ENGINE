# Navegador matemático de conceitos e teoremas

## Escopo e fontes

O módulo `omega/theorem_graph.py` é um protótipo local, com biblioteca padrão Python. O conjunto curado contém **seis** entradas de teoria de grafos: grafo simples finito não direcionado, passeio, caminho, conexidade, árvore e o teorema de caracterização da árvore por conexidade e número de arestas. Elas são afirmações matemáticas conhecidas, não descobertas nem demonstrações novas.

Referência associada individualmente a cada entrada: Reinhard Diestel, *Graph Theory*, 5ª edição, Springer, 2017, capítulo 1, DOI [10.1007/978-3-662-53622-3](https://doi.org/10.1007/978-3-662-53622-3). A referência fornece contexto matemático, **não** verifica automaticamente esta implementação, o texto resumido ou as escolhas editoriais. Nenhum conteúdo externo é baixado pelo módulo; conferir o livro e os direitos antes de eventual publicação.

A versão armazenada do teorema inclui explicitamente a hipótese de que o grafo simples finito e não direcionado tenha `n >= 1` vértices: ele é árvore se e somente se é conexo e possui `n - 1` arestas. Não é válido apagar essas hipóteses sem outra convenção ou demonstração.

## Dois tipos distintos de relação

* `(a, b)` em `prerequisites` é seta dirigida de conhecimento recomendado: estude `a` antes de `b`. É uma escolha pedagógica, **não** uma afirmação de necessidade lógica, nem uma demonstração. `preparation_order(target)` devolve o fecho transitivo de pré-requisitos, incluindo o alvo, em ordem topológica determinística. Vários nós prontos são desempacotados pelo menor identificador lexicográfico. Ciclos em qualquer parte do grafo são rejeitados; a mensagem lista nós ainda bloqueados, podendo incluir descendentes do ciclo, não apenas seus membros.
* `(a, b, d)` em `semantic_edges` é uma relação **não direcionada**, com distância inteira positiva editorial. Os valores são atribuídos manualmente, não medidos por dados ou embeddings. Os pesos não alegam ser métrica nem satisfazer desigualdade triangular; o custo de uma rota é sua soma. Percorrer uma relação semântica no sentido inverso não inverte nem cria dependências.

O otimizador de rotas **não impõe** a ordem pedagógica. Se ela for necessária, consulte `preparation_order` separadamente. Uma rota semântica ótima não prova uma implicação, não oferece certificado formal de um teorema e não torna conceitos relacionados equivalentes.

## Metadados H, C, I, P e B

Cada objeto `Concept` tem enunciado, referência e cinco notas inteiras de 0 a 5, exclusivamente ilustrativas e não canônicas:

| Campo | Sentido editorial (0 menor, 5 maior) |
|---|---|
| H | carga percebida de hipóteses explícitas |
| C | complexidade conceitual percebida |
| I | impacto matemático percebido |
| P | esforço percebido de demonstração |
| B | amplitude percebida de aplicação |

Não são medidas calibradas, universais, objetivas ou comparáveis entre disciplinas; P=0 não é certificado de que uma afirmação não precise de demonstração. Não há validação empírica. Escolher peso positivo para I ou B penaliza uma nota alta: isso é uma opção matemática do usuário e **não** implica que grande impacto ou amplitude seja ruim. Por padrão todos os pesos são zero.

## Objetivo, restrições e garantias

`route(start, end, weights=..., max_hops=..., max_distance=..., max_penalty=...)` percorre todos os caminhos sem vértices repetidos possíveis, com poda segura apenas quando uma restrição não negativa já foi excedida ou quando não restam saltos. Para um caminho `v0, ..., vk`:

* `distance = soma das distâncias das k arestas semânticas`;
* `penalty = soma dos pesos de H/C/I/P/B multiplicados pelas notas em **todos** os vértices, incluindo origem e destino`;
* `total = distance + penalty`.

A solução minimiza `total` sujeita às três restrições fornecidas, inclusive os limites. Empates usam a tupla completa de identificadores lexicograficamente menor. O resultado `optimal` é exato **somente para o grafo, as notas e os limites declarados**, não para a matemática em geral. `no_feasible_route` indica busca exaustiva sem caminho viável, seja por desconexão ou por restrições; não distingue essas causas. O resultado inclui `explored_states`, `pruned_states` e `complete_paths_evaluated`: estados visitados, estados descartados (inclusive por limite de saltos) e caminhos completos viáveis avaliados. Os contadores não são números de provas.

Se origem e destino coincidirem, o único caminho simples considerado é o caminho de um vértice, com distância zero e penalidade da origem; ele ainda pode ser inviável pelo limite de penalidade. Erros de formato, nós desconhecidos, duplicação, autoarestas, ciclos de pré-requisitos e parâmetros inválidos levantam `ValueError`; não são resultados `no_feasible_route`.

Limites deliberados: 1–8 conceitos, até 56 setas de pré-requisitos e 28 arestas semânticas não direcionadas, distâncias 1–100, notas 0–5, pesos inteiros 0–10 por campo, saltos 0 a `n-1`, distância máxima 0 a `100*(n-1)` e penalidade máxima 0 a `250*n`. `bool`, floats e valores fora desses intervalos são rejeitados. Mesmo no pior caso de 8 nós e grafo completo há no máximo `sum(P(7,k), k=0..7) = 13.700` estados de caminho parcial; a busca pode terminar ou podar antes. Não aceita entrada transmitida por geradores não limitados. Esses limites não autorizam usar a rotina em grafos maiores.

## Reprodução e exemplos

Na raiz do projeto:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_theorem_graph.py -v
```

```python
from omega.theorem_graph import curated_graph

g = curated_graph()
print(g.preparation_order('tree_edge_theorem'))
r = g.route('graph', 'tree_edge_theorem')
print(r.status, r.path, r.distance, r.penalty, r.total)
print(g.route('graph', 'tree_edge_theorem', max_hops=1).status)
```

Sem penalidades, o caminho selecionado é `graph -> walk -> path -> connected -> tree -> tree_edge_theorem`, distância 8, penalidade 0 e total 8. Com `max_hops=1`, não existe caminho viável para esse par. Os testes também contrastam a busca com um oráculo independente baseado em permutações em **1.350** combinações de pares e restrições num pequeno grafo, verificam desempates, penalidades, invalidação e rejeição de ciclos. Isso verifica tais casos, não demonstra correção de todos os programas nem valida os pesos subjetivos.
