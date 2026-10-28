// Telegram WebApp Initialization
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  if (tg.initDataUnsafe?.user) {
    const u = tg.initDataUnsafe.user;
    const name = u.first_name || u.username || 'Пользователь';
    document.getElementById('userName').textContent = `Привет, ${name}!`;
    document.getElementById('userAvatar').textContent = name.charAt(0).toUpperCase();
  }
}

// State
let currentStyle = 'general';
let currencyData = null;

// Tab Switching
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    btn.classList.add('active');
    const tabId = `tab-${btn.dataset.tab}`;
    document.getElementById(tabId).classList.add('active');

    if (btn.dataset.tab === 'currency' && !currencyData) {
      loadCurrencyData();
    }
  });
});

// Style chips selection (Translator)
document.querySelectorAll('.style-chips .chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.style-chips .chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    currentStyle = chip.dataset.style;
  });
});

// 1. Нутрициолог: Загрузка фото
const foodPhotoInput = document.getElementById('foodPhotoInput');
const dropZone = document.getElementById('dropZone');
const uploadIdle = document.getElementById('uploadIdle');
const uploadPreview = document.getElementById('uploadPreview');
const previewImage = document.getElementById('previewImage');
const loadingSpinner = document.getElementById('loadingSpinner');
const nutritionResult = document.getElementById('nutritionResult');

foodPhotoInput.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = async (event) => {
    previewImage.src = event.target.result;
    uploadIdle.classList.add('hidden');
    uploadPreview.classList.remove('hidden');
    loadingSpinner.classList.remove('hidden');
    nutritionResult.classList.add('hidden');

    try {
      const response = await fetch('/api/analyze-food', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_base64: event.target.result.split(',')[1] })
      });
      const data = await response.json();
      renderNutritionResult(data);
    } catch (err) {
      alert('Ошибка анализа: ' + err.message);
    } finally {
      loadingSpinner.classList.add('hidden');
    }
  };
  reader.readAsDataURL(file);
});

// Текстовый анализ блюда
document.getElementById('btnAnalyzeText').addEventListener('click', async () => {
  const text = document.getElementById('foodTextInput').value.trim();
  if (!text) return;

  const btn = document.getElementById('btnAnalyzeText');
  btn.textContent = '...';
  btn.disabled = true;

  try {
    const response = await fetch('/api/analyze-food', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text })
    });
    const data = await response.json();
    renderNutritionResult(data);
  } catch (err) {
    alert('Ошибка: ' + err.message);
  } finally {
    btn.textContent = 'Рассчитать';
    btn.disabled = false;
  }
});

function renderNutritionResult(data) {
  nutritionResult.classList.remove('hidden');

  if (!data.is_food) {
    document.getElementById('resDishName').textContent = '⚠️ Не еда';
    document.getElementById('resPortionMeta').textContent = '';
    document.getElementById('resAdviceText').textContent = data.nutritionist_advice || 'На фото не найдено блюда.';
    document.getElementById('resAdviceBox').classList.remove('hidden');
    document.getElementById('resIngredientsBlock').classList.add('hidden');
    return;
  }

  document.getElementById('resDishName').textContent = data.dish_name || 'Блюдо';
  document.getElementById('resConfidence').textContent = `🎯 ${data.confidence_score || 95}% точность`;
  document.getElementById('resPortionMeta').textContent = `Вес: ~${data.estimated_weight_g || 0} г • ${data.cooking_method || 'Готовое блюдо'}`;

  document.getElementById('resCalories').textContent = data.total_calories || 0;
  document.getElementById('resProteins').textContent = (data.total_proteins || 0) + 'г';
  document.getElementById('resFats').textContent = (data.total_fats || 0) + 'г';
  document.getElementById('resCarbs').textContent = (data.total_carbs || 0) + 'г';

  // Скрытые калории
  const alertEl = document.getElementById('resHiddenAlert');
  if (data.hidden_calories_alert && !data.hidden_calories_alert.toLowerCase().includes('не обнаружено')) {
    alertEl.textContent = '⚠️ ' + data.hidden_calories_alert;
    alertEl.classList.remove('hidden');
  } else {
    alertEl.classList.add('hidden');
  }

  // Ингредиенты
  const ingList = document.getElementById('resIngredientsList');
  ingList.innerHTML = '';
  if (data.ingredients && data.ingredients.length > 0) {
    data.ingredients.forEach(i => {
      const li = document.createElement('li');
      li.innerHTML = `<span>${i.name} (${i.weight_g}г)</span> <b>${i.calories} ккал</b>`;
      ingList.appendChild(li);
    });
    document.getElementById('resIngredientsBlock').classList.remove('hidden');
  } else {
    document.getElementById('resIngredientsBlock').classList.add('hidden');
  }

  // Совет
  document.getElementById('resAdviceText').textContent = data.nutritionist_advice || 'Приятного аппетита!';
}

// 2. Переводчик
document.getElementById('btnTranslate').addEventListener('click', async () => {
  const text = document.getElementById('translateInput').value.trim();
  if (!text) return;

  const btn = document.getElementById('btnTranslate');
  const targetLang = document.getElementById('targetLangSelect').value;
  btn.textContent = 'Перевожу...';
  btn.disabled = true;

  try {
    const response = await fetch('/api/translate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: text,
        target_lang: targetLang,
        style: currentStyle
      })
    });
    const res = await response.json();
    document.getElementById('translateOutputText').textContent = res.translated_text || '';
    document.getElementById('translateOutputBox').classList.remove('hidden');
  } catch (err) {
    alert('Ошибка перевода: ' + err.message);
  } finally {
    btn.textContent = 'Перевести (0.3с)';
    btn.disabled = false;
  }
});

document.getElementById('btnCopyTranslation').addEventListener('click', () => {
  const text = document.getElementById('translateOutputText').textContent;
  navigator.clipboard.writeText(text);
  if (tg?.HapticFeedback) {
    tg.HapticFeedback.notificationOccurred('success');
  }
  const btn = document.getElementById('btnCopyTranslation');
  btn.textContent = '✅ Скопировано!';
  setTimeout(() => btn.textContent = '📋 Копировать', 2000);
});

// 3. Валютчик
async function loadCurrencyData() {
  try {
    const response = await fetch('/api/currency');
    const data = await response.json();
    currencyData = data;

    // ЦБ РУз
    const cbu = data.cbu;
    document.getElementById('cbuDate').textContent = cbu.usd.date || 'Сегодня';
    document.getElementById('cbuUsdRate').textContent = cbu.usd.rate.toLocaleString('ru-RU', {minimumFractionDigits: 2});
    
    const diffSign = cbu.usd.diff >= 0 ? '+' : '';
    const diffEl = document.getElementById('cbuUsdDiff');
    diffEl.textContent = `${diffSign}${cbu.usd.diff.toFixed(2)}`;
    diffEl.className = 'diff ' + (cbu.usd.diff >= 0 ? 'positive' : 'negative');

    document.getElementById('cbuEurRate').textContent = cbu.eur.rate.toLocaleString('ru-RU', {minimumFractionDigits: 2});
    document.getElementById('cbuRubRate').textContent = cbu.rub.rate.toLocaleString('ru-RU', {minimumFractionDigits: 2});

    // Таблица банков
    const tbody = document.getElementById('banksTableBody');
    tbody.innerHTML = '';
    const bestBuy = data.best_buy;
    const bestSell = data.best_sell;

    data.banks.forEach(b => {
      const tr = document.createElement('tr');
      const buyBadge = b.buy === bestBuy ? '<span class="badge-top-buy">ТОП</span> ' : '';
      const sellBadge = b.sell === bestSell ? '<span class="badge-top-sell">ТОП</span> ' : '';

      tr.innerHTML = `
        <td><b>${b.name}</b></td>
        <td class="text-right">${buyBadge}<b>${b.buy.toLocaleString('ru-RU')}</b></td>
        <td class="text-right">${sellBadge}<b>${b.sell.toLocaleString('ru-RU')}</b></td>
      `;
      tbody.appendChild(tr);
    });

    calcCurrency();
  } catch (err) {
    console.error('Ошибка загрузки курсов:', err);
  }
}

document.getElementById('btnRefreshRates').addEventListener('click', () => {
  currencyData = null;
  loadCurrencyData();
});

// Калькулятор валют
const inputUsd = document.getElementById('inputUsd');
const inputUzs = document.getElementById('inputUzs');

function calcCurrency() {
  if (!currencyData) return;
  const val = parseFloat(inputUsd.value) || 0;
  const total = Math.round(val * currencyData.best_buy);
  inputUzs.value = total.toLocaleString('ru-RU') + ' UZS';
  document.getElementById('converterHint').textContent = `По лучшему курсу покупки (${currencyData.best_buy.toLocaleString('ru-RU')} UZS за $1)`;
}

inputUsd.addEventListener('input', calcCurrency);

// Загружаем курсы при старте
loadCurrencyData();

