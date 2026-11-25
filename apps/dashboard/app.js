'use strict';
const examples = {
  digits: {digits: '001904', base: 10},
  sat: {num_vars: 2, clauses: [[1,2],[-1,2],[1,-2]]},
  tsp: {matrix: [[0,10,15,20],[10,0,35,25],[15,35,0,30],[20,25,30,0]]},
  soil: {first: [0.2,0.5,0.8], second: [0.3,0.7,0.6]},
  cellular: {rows: 10, columns: 10, initial_probability: 0.3, steps: 8, seed: 42}
};
const descriptions = {
  digits: 'Transforma diferenças com âncora e reconstrói a sequência, preservando zeros iniciais. Base 2–10; até 4096 dígitos.',
  sat: 'Enumeração exaustiva limitada a 10 variáveis. O certificado é verificado; isso não resolve P versus NP.',
  tsp: 'Matriz simétrica de 1 a 10 vértices, distâncias inteiras 0–1000. Held–Karp é exato apenas para a instância; 2-opt é heurística.',
  soil: 'Vetores normalizados em [0,1], com 1–32 atributos. Similaridade é uma medida matemática, não diagnóstico ou probabilidade.',
  cellular: 'Regra B3/S23 com borda morta e seed fixa; modelo sintético sem calibração real. Até 25×25, 50 passos e 20.000 atualizações.'
};
const operation = document.getElementById('operation');
const input = document.getElementById('input');
const output = document.getElementById('output');
const status = document.getElementById('status');
const run = document.getElementById('run');
let sequence = 0;
function reset() {
  sequence++;
  input.value = JSON.stringify(examples[operation.value], null, 2);
  document.getElementById('description').textContent = descriptions[operation.value];
  output.textContent = 'Nenhum experimento executado.';
  status.textContent = 'Pronto. Exemplo restaurado.';
  run.disabled = false;
}
operation.addEventListener('change', reset);
document.getElementById('reset').addEventListener('click', reset);
run.addEventListener('click', async () => {
  let data;
  try { data = JSON.parse(input.value); } catch (_) { status.textContent = 'Erro: JSON inválido. Confira a entrada.'; return; }
  const request = ++sequence;
  run.disabled = true;
  status.textContent = 'Executando localmente…';
  output.textContent = '';
  try {
    const response = await fetch('/api/' + operation.value, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    const body = await response.json();
    if (request !== sequence) return;
    if (!response.ok) { status.textContent = 'Erro do servidor (' + response.status + '). Confira os limites e a entrada.'; output.textContent = JSON.stringify(body, null, 2); }
    else { status.textContent = 'Concluído. Resultado local abaixo.'; output.textContent = JSON.stringify(body.result, null, 2); }
  } catch (_) {
    if (request !== sequence) return;
    status.textContent = 'Erro de conexão. Verifique se o servidor local está em execução.';
  } finally { if (request === sequence) run.disabled = false; }
});
reset();
