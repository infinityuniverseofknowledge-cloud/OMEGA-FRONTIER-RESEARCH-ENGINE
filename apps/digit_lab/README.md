# Laboratório de dígitos

Aplicação local e offline para experimentar uma transformação reversível de sequências de dígitos. É uma ferramenta exploratória hipotética, não uma descoberta científica nem uma prova de qualquer hipótese geral.

## Uso

Mantenha `index.html`, `app.js` e `styles.css` juntos. Abra `index.html` em um navegador moderno, inclusive no Android. Não há instalação, servidor, dependências externas, acesso à rede ou armazenamento persistente. A sequência inicial `00137` é apenas um exemplo. Digite ou cole uma sequência não vazia de caracteres ASCII `0` a `9`, sem espaços nem quebras de linha. Altere a operação no seletor para transformar ou recuperar uma sequência de deltas. A saída e a frequência de cada dígito na entrada e na saída são atualizadas automaticamente. O botão Limpar devolve o foco à entrada. Entrada vazia não é calculada; entrada inválida mostra um erro e limpa resultados antigos. Zeros à esquerda são preservados.

## Definição

Para dígitos `x[0], ..., x[n-1]`, a direta é `y[0] = x[0]` (âncora) e `y[i] = (x[i] - x[i-1]) mod 10` para `i >= 1`. A inversa é `x[0] = y[0]` e `x[i] = (x[i-1] + y[i]) mod 10`. Assim, `00137 → 00124 → 00137`. A reversibilidade segue das definições e não implica compressão, padrão relevante ou outras conclusões científicas.

## Verificação básica com Node.js (opcional)

No diretório da aplicação, execute `node --check app.js`. As funções puras também podem ser importadas via `require('./app.js')` para testes independentes da interface; o navegador não precisa de Node.js.
