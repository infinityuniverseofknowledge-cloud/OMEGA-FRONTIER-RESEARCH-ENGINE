'use strict';

// Pure functions operate on strings, never numbers representing the full sequence.
function validateDigits(value) {
  return typeof value === 'string' && value.length > 0 && !/[^0-9]/.test(value);
}

function transform(value, mode) {
  if (!validateDigits(value)) throw new Error('A entrada deve conter apenas dígitos ASCII de 0 a 9.');
  if (mode !== 'forward' && mode !== 'inverse') throw new Error('Operação desconhecida.');
  let result = value[0]; // First digit is the anchor.
  let previous = value.charCodeAt(0) - 48;
  for (let i = 1; i < value.length; i += 1) {
    const digit = value.charCodeAt(i) - 48;
    if (mode === 'forward') {
      result += String((digit - previous + 10) % 10);
      previous = digit;
    } else {
      previous = (previous + digit) % 10;
      result += String(previous);
    }
  }
  return result;
}

function frequencies(value) {
  if (!validateDigits(value)) throw new Error('A entrada deve conter apenas dígitos ASCII de 0 a 9.');
  const counts = Array(10).fill(0);
  for (const digit of value) counts[digit.charCodeAt(0) - 48] += 1;
  return counts;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { validateDigits, transform, frequencies };
}

if (typeof document !== 'undefined') {
  const digits = document.getElementById('digits');
  const mode = document.getElementById('mode');
  const error = document.getElementById('error');
  const inputDisplay = document.getElementById('input-display');
  const output = document.getElementById('output');
  const length = document.getElementById('length');
  const status = document.getElementById('result-status');
  const frequency = document.getElementById('frequency');

  function render() {
    const value = digits.value;
    const valid = validateDigits(value);
    const invalid = value.length > 0 && !valid;
    digits.setAttribute('aria-invalid', invalid ? 'true' : 'false');
    error.hidden = !invalid;
    error.textContent = invalid ? 'Entrada inválida. Use somente dígitos ASCII de 0 a 9, sem espaços ou quebras de linha.' : '';
    inputDisplay.textContent = valid ? value : '—';
    output.textContent = '—';
    length.textContent = '—';
    frequency.replaceChildren();
    if (!valid) {
      status.textContent = invalid ? 'Corrija a entrada para calcular o resultado.' : 'Digite uma sequência para começar.';
      return;
    }
    const result = transform(value, mode.value);
    const inputCounts = frequencies(value);
    const outputCounts = frequencies(result);
    output.textContent = result;
    length.textContent = String(value.length);
    status.textContent = mode.value === 'forward' ? 'Transformação direta calculada.' : 'Transformação inversa calculada.';
    for (let i = 0; i < 10; i += 1) {
      const row = document.createElement('tr');
      const heading = document.createElement('th');
      heading.scope = 'row';
      heading.textContent = String(i);
      row.appendChild(heading);
      for (const count of [inputCounts[i], outputCounts[i]]) {
        const cell = document.createElement('td');
        cell.textContent = String(count);
        row.appendChild(cell);
      }
      frequency.appendChild(row);
    }
  }

  digits.addEventListener('input', render);
  mode.addEventListener('change', render);
  document.getElementById('clear').addEventListener('click', () => {
    digits.value = '';
    render();
    digits.focus();
  });
  render();
}
