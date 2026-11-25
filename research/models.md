# Modelos independentes: vetores de solo e autômato celular

Implementação offline, em Python 3.10+ e apenas biblioteca padrão: `omega/models.py`. Os cenários são **dados inventados**, não observações. Os dois modelos são independentes, sem acoplamento com `simulation.py` ou `mathcore.py`. Não são calibrados nem validados para uso real; não representam previsão agrícola, qualidade de solo, células biológicas ou efeito médico. Não há recomendações ou protocolos de intervenção.

## Vetores de solo: definição

`normalize_soil(values, ranges)` recebe listas ou tuplas numéricas de 1 a 128 componentes e uma lista ou tupla de intervalos `(mínimo, máximo)` correspondentes, de limites inclusivos. Cada componente e seus limites devem usar **a mesma unidade**, e ambos vetores comparados devem usar as mesmas características, ordem, unidades e intervalos. A função calcula `z_i = (x_i - mínimo_i)/(máximo_i - mínimo_i)`; exige mínimo < máximo e valor dentro do intervalo e não recorta dados. Números finitos reais em Python `int` ou `float`, excluindo `bool`, são aceitos no intervalo bruto [-10¹², 10¹²]. Saída é uma tupla de floats em [0,1].

`soil_similarity(first, second)` aceita dois vetores normalizados de mesmo tamanho (1–128), novamente apenas números finitos entre 0 e 1. Calcula `d = sqrt(sum((a_i - b_i)**2))` e `s = 1 - d/sqrt(n)`; retorna `{'distance': d, 'similarity': s, 'features': n}`. Para dimensão fixa, a distância euclidiana matemática é uma métrica, de 0 a √n; a similaridade é apenas um escore de 0 a 1, não uma métrica nem probabilidade. Todos componentes têm peso igual após normalização; os limites escolhidos afetam o resultado. Cálculos são aproximados em ponto flutuante: por arredondamento, um escore pode ser 1 mesmo quando a distância é positiva, e identidades matemáticas são aproximadas numericamente.

No cenário `synthetic_scenarios()` a ordem e unidades **assumidas para a demonstração** são pH (adimensional; escala nominal 0–14 apenas como limite artificial deste exemplo, não limite universal de pH), fração volumétrica de água (m³/m³, 0–1) e fração mássica de matéria orgânica (kg/kg, 0–1). Nenhuma faixa ou valor é medido, típico ou calibrado. É possível usar outras características com outros limites explícitos, mas não há metadados de unidades ou verificações de compatibilidade no vetor: o chamador é responsável por eles.

Exemplo reproduzível:

```python
from omega.models import normalize_soil, soil_similarity
ranges = ((0, 14), (0, 1), (0, 1))
a = normalize_soil((7, .5, .1), ranges)
b = normalize_soil((7, .5, .2), ranges)
print(a, b, soil_similarity(a, b))
# (0.5, 0.5, 0.1) (0.5, 0.5, 0.2)
# {'distance': 0.1, 'similarity': 0.9422649730810374, 'features': 3}
```

O cenário usa referência inventada `(7, 0.5, 0.1)` e quatro amostras, com resultados aproximados (nenhuma é dado observado):

| Vetor bruto | Distância | Similaridade |
|---|---:|---:|
| (7, 0.5, 0.1) | 0 | 1 |
| (7, 0.5, 0.2) | 0.1 | 0.942265 |
| (0, 0, 0) | 0.714143 | 0.587689 |
| (14, 1, 1) | 1.144552 | 0.339192 |

## Autômato celular 2D abstrato

Cada célula tem estado inteiro 0 ou 1; não descreve uma célula viva. Vizinhança de Moore com os oito deslocamentos adjacentes, excluindo o centro; não há conexão periódica. O exterior da grade é fixo em 0. Atualização síncrona: uma célula 0 passa a 1 com exatamente três vizinhos 1; uma célula 1 permanece 1 com dois ou três vizinhos 1; caso contrário, passa a 0 (regra B3/S23). O instante `t=0` é a grade inicial e cada atualização aumenta `t` em 1; tempo em passos abstratos, sem duração física.

- `cellular_step(grid)` valida a grade e devolve a próxima grade como tupla de tuplas.
- `evolve_cellular(grid, steps)` devolve `initial_grid`, `final_grid` e `counts`, este com `{'t': ..., 'active': ...}` em todos os instantes `0..steps`. Aceita grade explícita retangular de listas/tuplas, com inteiros 0 ou 1 (não bool).
- `simulate_cellular(rows, columns, initial_probability, steps, seed=0)` gera inicialmente Bernoulli independente com `random.Random(seed).random() < initial_probability`, em ordem linha por linha, mesmo para probabilidades 0 e 1; devolve parâmetros, seed, grades e contagens. Utiliza gerador local, sem modificar o estado global. Repetir os parâmetros e a seed reproduz o resultado no mesmo ambiente; a implementação usa o gerador da biblioteca padrão, não um formato de sorteio independente de versões/implementações.
- `synthetic_scenarios()` devolve exemplos completos, unidades, intervalos, referência e a simulação celular abaixo, marcados como sintéticos.

Dimensões 1–100 em cada eixo; `steps` inteiro 0–1000; `rows * columns * steps` ≤ 1.000.000; seed inteiro 0–2³²−1; probabilidade finita em [0,1]. `steps=0` retorna somente o instante inicial; `p=0` gera grade vazia; `p=1` gera grade cheia. Entradas inválidas são rejeitadas com `ValueError`.

Exemplo `simulate_cellular(8, 8, 0.3, 5, seed=42)`: número de células 1 nos instantes `t=0,1,2,3,4,5` é `[24, 16, 16, 15, 17, 13]`. São 64 posições e 5 atualizações sintéticas, não tempos ou quantidades biológicas observadas.

## Testes

Na raiz do projeto, execute:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

`tests/test_models.py` verifica exemplos, limites, rejeição de entradas inválidas, zero e extremos, repetibilidade e isolamento do gerador, estabilidade e oscilação conhecidas, bordas mortas, e todas as 512 grades binárias 3×3 contra uma implementação de referência por deslocamentos. Testa propriedades da distância em 729 triplas de vetores 2D discretos, com tolerância numérica para a desigualdade triangular. A suíte completa inclui testes dos demais módulos existentes. Não há inferência científica a partir dos testes.
