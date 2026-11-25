# Ciclo experimental limitado e laboratório de contraexemplos

A implementação `omega/research_cycle.py` usa apenas a biblioteca padrão e módulos locais. Cada execução escreve um JSON novo em `reports/generated_<uuid>.json`, por criação exclusiva; não substitui relatórios anteriores. Não há rede nem publicação. Isso reduz sobrescrita acidental, mas arquivos podem ser editados ou removidos depois; não é um log imutável, assinado ou autenticado.

## Reproduzir

Na raiz do projeto, Python 3.10 ou superior:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m omega.research_cycle
PYTHONDONTWRITEBYTECODE=1 python -m omega.research_cycle --seed 42 --base 10 --max-length 4 --tsp-n 6 --max-weight 100
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Parâmetros: seed inteiro 0..2^64−1; base 2..10; comprimento máximo 1..8; no máximo 20.000 palavras somadas entre comprimentos 1 e o máximo; TSP com 2..8 vértices e pesos inteiros 0..1000. Combinações acima do orçamento são rejeitadas antes da enumeração. `--help` lista as opções. Um erro de execução ou verificação encerra o processo sem gerar relatório de sucesso. Para uma mesma versão de código e Python, os objetos de entrada e saída são determinísticos; data/hora UTC e nome do arquivo variam. Em outros ambientes, compare versões e hashes de fonte antes de esperar resultados idênticos.

## Experimentos e evidências

- **Reconstrução ancorada**: enumera todas as strings de dígitos (inclusive zeros iniciais), por comprimento e em ordem lexicográfica. Calcula diferenças modulares, retém o primeiro dígito como âncora e verifica a inversa de cada entrada. Contagens e hash do fluxo são registrados. O fluxo é uma sequência de objetos JSON canônicos `{word, anchor, differences, decoded}`, cada um seguido de LF; ele é recalculável, mas não é armazenado integralmente.
- **Hipótese refutável**: para cada palavra, a soma de `âncora + diferenças` nunca excede a soma original. Registra o primeiro contraexemplo ou `not_refuted_in_bounded_domain` quando não o encontra; ausência limitada não é demonstração geral. Por exemplo, em base 10, `10 → 19`: somas 1 e 10. O conjunto depende dos parâmetros.
- **SAT**: duas CNFs fixas, uma SAT e outra UNSAT, têm certificados gerados e verificados pelo verificador do módulo local. Para UNSAT, a lista registra uma cláusula falsificada para cada atribuição; é certificação dessa CNF, não das fórmulas em geral.
- **TSP**: matriz inteira simétrica gerada pela seed; Held–Karp é verificado contra enumeração de todas as permutações ancoradas em zero, com validação das rotas e custos. Vizinho mais próximo + 2-opt é comparado ao ótimo apenas para essa instância. Não se presume desigualdade triangular nem garantia geral da heurística.

## Relatório e verificação

`inputs` inclui parâmetros, fórmulas e matriz; `outputs` inclui resultados, status, certificados e evidências. `input_sha256` e `output_sha256` são hashes SHA-256 **separados** dos respectivos objetos JSON serializados com chaves ordenadas, sem espaços extras, UTF-8, `ensure_ascii=False` e `allow_nan=False`. Não incluem timestamp, versões, restrições ou o próprio relatório; não impedem que alguém altere dados e hashes juntos. O relatório também registra versão de Python, implementação, versão de esquema e hashes SHA-256 dos arquivos-fonte dos módulos executados.

Exemplo de verificação local, substituindo o caminho pelo arquivo escolhido:

```sh
PYTHONDONTWRITEBYTECODE=1 python -c 'import json,sys; from omega.research_cycle import verify_hashes; r=json.load(open(sys.argv[1],encoding="utf-8")); print(verify_hashes(r))' reports/generated_EXEMPLO.json
```

Um `True` só confere os dois hashes com o conteúdo presente, não prova correção científica, autenticidade ou integridade dos metadados. Para validar resultados, reexecute com os parâmetros e compare os hashes de saída; confira também certificados e fontes. Os registros não contêm observações biológicas e não estabelecem P=NP nem P≠NP.

## Execução documentada

Em 2026-11-25 17:32:13 UTC, seed 42, base 10, comprimentos 1..4 e TSP de 6 vértices: 11.110 reconstruções conferidas; hipótese refutada por `10 → 19`; certificados SAT e UNSAT verificados; TSP exato e heurística tiveram custo 144, com 120 permutações verificadas. Evidência: `reports/generated_cda7a9f0828d450c881a21d17c3c3e41.json`. Na mesma rodada, a suíte completa passou 56 testes (seis deste módulo). Resultados aplicam-se somente aos domínios e instâncias registrados.
