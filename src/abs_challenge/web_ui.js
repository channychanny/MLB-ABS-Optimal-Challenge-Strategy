const form = document.getElementById('decision-form');
const errorBox = document.getElementById('error');
const submit = document.getElementById('submit');
const getNumber = (id) => Number(document.getElementById(id).value);
const setText = (id, value) => { document.getElementById(id).textContent = value; };
const pct = (value, digits = 1) => value == null ? '—' : `${(value * 100).toFixed(digits)}%`;
const pp = (value, digits = 2) => value == null ? '—' : `${value >= 0 ? '+' : ''}${(value * 100).toFixed(digits)} 個百分點`;
const costPp = (value) => `${(value * 100).toFixed(2)} 個百分點`;
const runs = (value) => value == null ? '—' : `${value.toFixed(3)} 分`;
const runChange = (value) => value == null ? '—' : `${value >= 0 ? '+' : ''}${value.toFixed(3)} 分`;

function thresholdText(threshold) {
  if (threshold.break_even_kind === 'indifferent') return '兩者在此模型下沒有差別';
  if (threshold.break_even_kind === 'never_strictly_challenge') return '沒有值得挑戰的正向門檻';
  return `翻判把握高於約 ${pct(threshold.conditional_break_even_probability, 2)}`;
}

function payload() {
  const customText = document.getElementById('custom-cost').value.trim();
  return {
    pre_pitch_state: {
      inning: getNumber('inning'), half: document.getElementById('half').value,
      outs: getNumber('outs'),
      bases: (document.getElementById('base1').checked ? 1 : 0)
           + (document.getElementById('base2').checked ? 2 : 0)
           + (document.getElementById('base3').checked ? 4 : 0),
      balls: getNumber('balls'), strikes: getNumber('strikes'),
      home_score: getNumber('home_score'), away_score: getNumber('away_score')
    },
    original_call: document.getElementById('original_call').value,
    challenges_remaining: getNumber('budget'),
    custom_failure_cost_pp: customText === '' ? null : Number(customText),
    assume_pure_called_pitch: document.getElementById('pure-call').checked
  };
}

function render(data) {
  document.getElementById('placeholder').hidden = true;
  const result = document.getElementById('result');
  const unsupported = document.getElementById('unsupported');
  const scenarioResult = document.getElementById('scenario-result');
  const reResult = document.getElementById('re-result');
  reResult.hidden = data.re_s0 == null || data.re_s1 == null;
  if (!reResult.hidden) {
    setText('re0', runs(data.re_s0));
    setText('re1', runs(data.re_s1));
    setText('re-delta', runChange(data.delta_re_decision));
    setText('re-perspective', data.decision_side === 'batting'
      ? '進攻方挑戰：正值代表本隊在原半局的預期得分增加。'
      : '防守方挑戰：正值代表對手在原半局的預期得分減少。');
  }
  if (data.status !== 'supported') {
    result.hidden = true;
    scenarioResult.hidden = true;
    unsupported.hidden = false;
    setText('unsupported-reason', `${data.reason || '官方勝率無法估值'}；因此不計算 WP 挑戰門檻。下方 RE 若有數值仍可單獨解讀。原判：${data.s0.missing_reason_code || '—'}；翻判：${data.s1.missing_reason_code || '—'}。`);
    return;
  }
  unsupported.hidden = true;
  result.hidden = false;
  scenarioResult.hidden = false;
  setText('decision-side', data.decision_side === 'batting' ? '進攻方' : '防守方');
  setText('wp0', pct(data.wp_s0));
  setText('wp1', pct(data.wp_s1));
  setText('delta', pp(data.delta_wp_if_overturned));

  const range = data.illustrative_threshold_range;
  setText('threshold-range', range == null
    ? '沒有正向挑戰門檻'
    : `${pct(range.lower, 2)}–${pct(range.upper, 2)}`);
  setText('range-explanation', range == null
    ? '翻判未增加挑戰隊伍勝率；不能因額度成本假設而憑空產生正向建議。'
    : `只對應下方低／高兩個假設成本 ${costPp(range.assumed_cost_lower_wp)} 至 ${costPp(range.assumed_cost_upper_wp)}；不是統計信賴區間。顯示值已四捨五入，嚴格挑戰條件須高於實際門檻。`);
  const container = document.getElementById('sensitivity');
  container.replaceChildren();
  const scenarioNames = {
    immediate_only: '不計保留額度價值',
    small_resource_cost: '假設較低額度成本',
    large_resource_cost: '假設較高額度成本'
  };
  for (const entry of data.illustrative_cost_scenarios) {
    const row = document.createElement('div');
    row.className = 'sensitivity-row';
    const label = document.createElement('span');
    label.textContent = `${scenarioNames[entry.id] || entry.id} · ${costPp(entry.assumed_failure_cost_wp)}`;
    const outcome = document.createElement('strong');
    outcome.textContent = thresholdText(entry.threshold);
    row.append(label, outcome);
    container.append(row);
  }
  const customBox = document.getElementById('custom-result');
  customBox.hidden = data.custom_cost_threshold == null;
  if (!customBox.hidden) {
    customBox.textContent = `改用你指定的失敗額度成本 ${data.custom_cost_pp.toFixed(2)} 個百分點：${thresholdText(data.custom_cost_threshold)}。`;
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  errorBox.hidden = true;
  submit.disabled = true;
  try {
    const response = await fetch('/api/evaluate', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload())
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || '分析失敗，請檢查輸入。');
    render(data);
    document.getElementById('result-title').scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (error) {
    errorBox.textContent = error.message || '無法連線至本機分析服務。';
    errorBox.hidden = false;
  } finally {
    submit.disabled = false;
  }
});
