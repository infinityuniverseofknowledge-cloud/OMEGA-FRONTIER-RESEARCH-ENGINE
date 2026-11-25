# Benchmark offline: TSP simétrico limitado

## Escopo e execução

Experimento reproduzível sobre matrizes completas, simétricas, com diagonal zero e pesos inteiros não negativos. Não exige desigualdade triangular. Não é uma prova sobre P versus NP nem um estudo suficiente para afirmar superioridade geral de qualquer algoritmo. Sem dependências externas.

Na raiz do workspace:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m omega.optimization
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

O primeiro comando imprime JSON com cada rota, custo, validade, semente, tempo e gaps; o segundo executa todos os testes existentes. A amostra usa `random_matrix(8, 42, 100)`, três sementes dos algoritmos `(0, 1, 2)`, 200 iterações/gerações e Held–Karp ativado. A matriz é gerada com `random.Random(42)` e pesos uniformes independentes em 0..100 para cada aresta não direcionada. Dependência da versão/implementação de Python e tempos do computador devem ser considerados ao reproduzir; o tempo não é determinístico.

## API

- `random_matrix(n, seed, max_weight=100)` gera a matriz; `route_cost(matrix, route)` valida a rota e calcula seu custo.
- `nearest_neighbor_cycle(matrix)` começa em 0 e resolve empates pelo menor vértice. `omega.mathcore.nearest_neighbor_2opt_cycle(matrix)` acrescenta o 2-opt de primeira melhoria determinístico já existente. `omega.mathcore.held_karp_cycle(matrix)` fornece o ótimo exato.
- `simulated_annealing_cycle(matrix, seed, iterations=200)` parte de permutação aleatória, usa reversões, aceitação de Metropolis e resfriamento geométrico; devolve a melhor rota visitada.
- `tabu_search_cycle(matrix, seed, iterations=200)` parte de permutação aleatória, explora reversões 2-opt, proíbe por cinco movimentos os pares de rótulos dos extremos, usa aspiração por melhora do melhor global e sorteia empates. Pode parar antes se nenhum movimento for admissível.
- `genetic_cycle(matrix, seed, iterations=200)` usa população 16, elitismo, torneio de três amostras, crossover que preserva um segmento e ordem restante, e mutação de troca com probabilidade 0,3. Uma iteração é uma geração; devolve o melhor da população final, preservado pelo elitismo.
- `benchmark(matrix, seeds=(0,1,2), iterations=200, exact=True)` executa cada método na **mesma matriz**. Retorna `n`, `iterations`, `exact_cost` e `records`: `algorithm`, `seed` (`None` para determinísticos), `route`, `valid`, `cost`, `runtime_seconds`, `absolute_gap`, `relative_gap`. A validação independente da rota e do custo ocorre após a medição e falha em vez de registrar um resultado inválido. Os tempos incluem a execução e validação interna dos solvers, mas não a pós-validação ou cálculo de gap.

Todos os métodos usam ciclo ancorado em 0 e uma única visita a cada vértice; n=1 devolve `(0, 0)` e n=2 atravessa a mesma aresta duas vezes. A diferença absoluta é `custo - ótimo` e a relativa é uma `Fraction` exata `(custo - ótimo)/ótimo`. Ótimo zero e custo zero produz zero; ótimo zero e custo positivo produz `None` (indefinido). Se `exact=False`, ambos os gaps são `None` (não medidos); o JSON converte `Fraction` em numerador e denominador. Nomes de método e parâmetros são documentados; fixar entradas e sementes reproduz rotas e custos, não os tempos.

## Limites e comparação justa

A validação de `mathcore` limita a 1..14 vértices. Aqui pesos são adicionalmente limitados a 10^9; sementes inteiras de 0 a 2^64-1, no máximo dez sementes por benchmark e iterações de 1 a 1000. Booleanos, matrizes assimétricas, valores negativos e não inteiros são rejeitados. Held–Karp é exponencial e pode ser desativado (`exact=False`), mesmo no limite permitido.

O mesmo problema e as mesmas sementes identificáveis são usados em cada método estocástico. Isso **não iguala custo computacional**: uma iteração de simulated annealing testa uma reversão; tabu examina a vizinhança; uma geração genética cria 15 descendentes. Tempos de relógio são medições pontuais, não comparações controladas; devem ser replicados, inclusive em múltiplas matrizes/tamanhos, antes de qualquer conclusão. As heurísticas não garantem o ótimo. Não há implementações de 3-opt, ACO ou outras técnicas além das explicitamente identificadas aqui.

## Uma execução observada

A seguir, uma execução local da amostra descrita acima. `valid` foi verdadeiro em todos os registros. As rotas listadas incluem o retorno a 0. Tempos são segundos e apenas ilustrativos; em outras execuções variam. Os gaps relativos são frações exatas.

| Método | Semente | Rota | Custo | Tempo (s) | Gap absoluto | Gap relativo |
|---|---:|---|---:|---:|---:|---:|
| Held–Karp | — | 0-4-3-5-6-1-2-7-0 | 155 | 0.001374 | 0 | 0 |
| Vizinho mais próximo | — | 0-2-1-6-3-5-4-7-0 | 207 | 0.000029 | 52 | 52/155 |
| Vizinho + 2-opt | — | 0-4-3-5-6-1-2-7-0 | 155 | 0.000033 | 0 | 0 |
| Annealing | 0 | 0-4-3-5-6-1-2-7-0 | 155 | 0.000698 | 0 | 0 |
| Tabu | 0 | 0-4-3-5-6-1-2-7-0 | 155 | 0.007750 | 0 | 0 |
| Genético | 0 | 0-4-3-5-6-1-2-7-0 | 155 | 0.035478 | 0 | 0 |
| Annealing | 1 | 0-4-3-5-6-1-2-7-0 | 155 | 0.000680 | 0 | 0 |
| Tabu | 1 | 0-7-2-1-6-5-3-4-0 | 155 | 0.007685 | 0 | 0 |
| Genético | 1 | 0-7-2-1-6-5-3-4-0 | 155 | 0.034591 | 0 | 0 |
| Annealing | 2 | 0-7-4-3-5-6-1-2-0 | 163 | 0.000674 | 8 | 8/155 |
| Tabu | 2 | 0-4-3-5-6-1-2-7-0 | 155 | 0.007714 | 0 | 0 |
| Genético | 2 | 0-4-1-6-5-3-7-2-0 | 177 | 0.034498 | 22 | 22/155 |

Este resultado refere-se somente a uma matriz sintética. Os testes também verificam validade, determinismo por semente, melhora em uma instância específica, rejeição de entradas inválidas e comparação do ótimo com força bruta em uma instância conhecida.
