# Laboratório SAT finito e limitado

## Escopo

`omega/sat.py` é um experimento offline em Python 3.10+ com biblioteca padrão. Decide por enumeração completa somente CNFs dentro dos limites declarados; não é solver industrial, nem implementação de DPLL/CDCL, nem busca de provas de resolução completa. Não prova P = NP nem P ≠ NP, e nenhum resultado finito determina essas classes. O README anterior ao módulo ainda afirma que não há SAT; este documento e os testes descrevem o módulo novo, sem alterar o README.

## Modelo e limites

Uma fórmula é lista ou tupla de cláusulas, cada uma lista ou tupla de inteiros: `i` é xᵢ, `-i` é ¬xᵢ, i em 1..n. `n` é inteiro exato em 0..12; bool não é aceito como inteiro, nem zero como literal. No máximo 128 cláusulas e 2.048 ocorrências de literais no total. Repetições, tautologias, variáveis declaradas não usadas e cláusulas vazias são preservadas. CNF vazia é verdadeira; cláusula vazia é falsa. Invalidade ou excesso geram `ValueError`.

`solve(n, cnf)` enumera todas as 2ⁿ atribuições, na ordem de inteiros crescentes, com x₁ como bit menos significativo. Para SAT devolve `{'status': 'SAT', 'assignment': (...)}`: tupla de booleanos de comprimento n. Para UNSAT devolve `{'status': 'UNSAT', 'falsified_by': (...)}`: a posição j contém o índice de uma cláusula original falsificada pela atribuição j; são exatamente 2ⁿ posições. Uma busca que encontre SAT pode parar cedo. Um certificado UNSAT só sai depois que todas as atribuições falham.

`verify_certificate(n, cnf, cert)` valida novamente a fórmula e verifica diretamente os dados do certificado: SAT satisfaz todas as cláusulas; UNSAT cobre exatamente cada uma das 2ⁿ atribuições com um índice válido de cláusula efetivamente falsa. Certificado malformado retorna `False`; fórmula inválida gera `ValueError`. Um certificado não identifica a fórmula por hash: deve ser verificado explicitamente contra a fórmula e n pretendidos. A verificação UNSAT também é exponencial, não um certificado sucinto geral. Uma eventual corrupção compartilhada na implementação de geração e verificação não é eliminada pelo próprio verificador; testes confrontam avaliador independente.

`minimal_unsatisfiable(n, cnf)` retorna verdadeiro somente se a fórmula é insatisfatível e a exclusão de cada *ocorrência* individual de cláusula a torna satisfatível. Isso caracteriza minimalidade por inclusão de ocorrências, não mínimo tamanho entre todas as fórmulas ou subconjuntos. CNF vazia não é minimamente insatisfatível; `[[]]` é; `[[], []]` não é. A função rejeita antes da busca se `(m+1)*2**n*max(1, L+m) > 20.000.000`, com m cláusulas e L ocorrências de literais. Nunca transforma interrupção ou excesso de limite em conclusão.

`resolvent(n, first, second, pivot)` realiza uma única resolução binária: escolhe ocorrências de sinais opostos do pivô positivo, remove-as dos respectivos pais e retorna a união de literais ordenada e sem duplicatas. Caso ambas orientações existam, dá preferência ao pivô positivo no primeiro pai. Resultado tautológico é preservado; a cláusula vazia representa contradição. O resolvente é consequência lógica dos dois pais, não uma fórmula equivalente a eles. Não há saturação, prova completa nem alegação de limite de comprimento de provas.

## Exemplos reproduzíveis

```python
from omega.sat import solve, verify_certificate, minimal_unsatisfiable, resolvent
f = [[1, 2], [-1, 2], [1, -2]]
s = solve(2, f)  # {'status': 'SAT', 'assignment': (True, True)}
assert verify_certificate(2, f, s)
u = [[1], [-1]]
c = solve(1, u)  # {'status': 'UNSAT', 'falsified_by': (0, 1)}
assert verify_certificate(1, u, c)
assert minimal_unsatisfiable(1, u)
assert resolvent(1, [1], [-1], 1) == ()
assert resolvent(2, [1, 2], [-1, -2], 1) == (-2, 2)  # tautologia
assert not minimal_unsatisfiable(1, [[1], [-1], [1]])
```

O primeiro exemplo mostra que satisfatibilidade não exige que cada cláusula seja unitária. O segundo e a cláusula vazia são exemplos limitados de insatisfatibilidade; duplicar uma cláusula no segundo preserva UNSAT mas destrói a minimalidade.

## Custos e testes

Com n variáveis, m cláusulas e L literais, `solve` custa no pior caso O(2ⁿ(n + m + L)), incluindo geração das atribuições; o certificado UNSAT ocupa O(2ⁿ), além da representação da fórmula. Verificação UNSAT custa no pior caso O(2ⁿ(n + W)), onde W é a largura máxima das cláusulas selecionadas, e SAT O(n + m + L). Minimalidade executa até m+1 buscas, com limite adicional de trabalho; resolução única é O(L₁+L₂+R log R) para R literais distintos no resultado. São limites para esta implementação, não afirmações gerais sobre a complexidade mínima de SAT.

Executar na raiz do projeto, sem arquivos bytecode: `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_sat.py' -v`. Os testes incluem 256 fórmulas sobre um conjunto fixo de oito cláusulas, 200 fórmulas pseudoaleatórias com seed fixa, verificação independente de semântica, adulteração de certificados, casos degenerados, limites e consequência semântica dos resolventes em todas as atribuições de duas variáveis.
