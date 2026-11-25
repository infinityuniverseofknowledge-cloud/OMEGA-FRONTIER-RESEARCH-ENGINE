# API e painel local OMEGA FRONTIER

## Uso

Python 3.10+, apenas biblioteca padrão. No diretório raiz do projeto:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m omega.server
# endereço exibido: http://127.0.0.1:8765/
# porta alternativa: python -m omega.server --port 9876
# para parar: Ctrl+C
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

O painel é servido pelo próprio processo; não há dependências externas, chamadas para internet, persistência de dados ou publicação. A entrada JSON é editável; um exemplo determinístico acompanha cada operação. Retornos são mostrados como texto, não como HTML. Porta 0 escolhe uma porta livre e exibe a URL. Evite abrir o HTML diretamente via `file:`: o painel usa a API da mesma origem.

Exemplo para cliente local (ajuste a porta):

```sh
curl -s -H 'Content-Type: application/json' \
  -d '{"digits":"001904","base":10}' http://127.0.0.1:8765/api/digits
```

## Contrato

Todas as operações usam POST, `Content-Type: application/json`, `Content-Length` único e corpo com até 16.384 bytes. Não se aceita transfer-encoding. A resposta de sucesso tem `{"ok":true,"result":...}`; erros têm `{"error":"..."}` e status HTTP. Campos extras ou ausentes, chaves JSON duplicadas e constantes NaN/Infinity são rejeitados. Matrizes, vetores e números inválidos também são rejeitados. Rotas e campos:

- `/api/digits`: `{"digits":"001904","base":10}`. Base 2–10, até 4096 dígitos ASCII não vazios. Devolve âncora, diferenças modulares, reconstrução e frequências; não reivindica compressão.
- `/api/sat`: `{"num_vars":2,"clauses":[[1,2],[-1,2],[1,-2]]}`. Até 10 variáveis, 64 cláusulas e 512 literais; literais são inteiros não nulos no intervalo de variáveis. Devolve SAT com atribuição ou UNSAT com certificado de enumeração, mais `certificate_verified`, resultado da verificação independente fornecida pelo módulo. Um resultado limitado não resolve P versus NP.
- `/api/tsp`: `{"matrix":[[0,10,15,20],[10,0,35,25],[15,35,0,30],[20,25,30,0]]}`. Até 10 vértices; matriz simétrica quadrada de inteiros 0–1000 e diagonal zero. Compara Held–Karp exato para a instância com vizinho mais próximo + 2-opt e fornece diferença absoluta. Não executa benchmark de `omega.optimization` nem outras heurísticas.
- `/api/soil`: `{"first":[0.2,0.5,0.8],"second":[0.3,0.7,0.6]}`. Vetores já normalizados no intervalo [0,1], mesmo tamanho, 1–32 atributos. Devolve distância euclidiana e score; não são diagnóstico, probabilidade ou previsão de solo real. A normalização deve ser feita previamente, com unidades e faixas justificadas.
- `/api/cellular`: `{"rows":10,"columns":10,"initial_probability":0.3,"steps":8,"seed":42}`. Até 25×25 células, 50 passos e 20.000 atualizações; probabilidade entre 0 e 1, seed inteira 0–2³²−1. Regra B3/S23 com borda morta. Retorna grades inicial/final e contagens por passo. Trata-se de um modelo sintético, não calibrado.

Integra `omega.mathcore`, `omega.sat` e `omega.models`. Não integra `omega.knowledge` ou SQLite: buscas varrem o banco e não há limite seguro de trabalho para bases arbitrárias. Também não integra simulação ecológica, benchmarks adicionais, grafo, publicação, login ou APIs remotas. Nenhum arquivo de banco é aberto ou alterado pelo servidor.

## Segurança e limites

O servidor vincula explicitamente apenas `127.0.0.1`, sem opção para escutar em todas as interfaces. Exige um único Host exato de loopback e porta, rejeita origens e `Sec-Fetch-Site` incompatíveis, recusa CORS/preflight e requer JSON, mitigando DNS rebinding e requisições de formulários de outros sites. Rotas estáticas são uma lista fixa, sem resolução de caminhos solicitados; CSP restritiva, `nosniff`, ausência de recursos externos e renderização por `textContent` reduzem risco de XSS. Não é um isolamento perfeito contra processos maliciosos locais, extensões de navegador ou acesso remoto que encaminhe a porta. **Não há autenticação:** qualquer processo com acesso ao loopback pode chamar a API. Não colocar dados sensíveis, expor com proxy/túnel/port forwarding, nem usar em servidor multiusuário ou ambiente não confiável.

A execução é síncrona, uma conexão por vez, com timeout de socket de 5 segundos por operação de leitura e limites de payload e cálculo. Não é serviço de produção: conexões lentas/maliciosas podem atrasar ou negar atendimento; não há quotas por cliente, TLS, autenticação, paralelismo, auditoria ou garantia forte de disponibilidade. Encerrar o processo quando não estiver em uso. Comandos e limites refletem esta API, mais restrita que as funções internas.
