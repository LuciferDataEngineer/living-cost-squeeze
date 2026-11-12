const pageState = {};

async function main() {
  const response = await fetch("data/dashboard.json");
  const data = await response.json();
  document.getElementById("kicker").textContent = data.banner.kicker;
  document.getElementById("title").textContent = data.banner.title;
  document.getElementById("dek").textContent = data.banner.dek;
  document.getElementById("sources").innerHTML = sourcesHtml(data.sources);
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => show(data, button.dataset.tab));
  });
  show(data, "squeeze");
  try {
    document.getElementById("asof").textContent = sydney(data.generated_at);
  } catch (error) {
    document.getElementById("asof").textContent = "Australian Eastern time";
  }
}

function sydney(iso) {
  const date = new Date(iso);
  const when = new Intl.DateTimeFormat("en-AU", {
    timeZone: "Australia/Sydney",
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
  const zone = new Intl.DateTimeFormat("en-AU", {
    timeZone: "Australia/Sydney",
    timeZoneName: "short",
  })
    .formatToParts(date)
    .find((part) => part.type === "timeZoneName");
  return `${when} ${zone ? zone.value : ""}`.trim();
}

function show(data, id) {
  document.querySelectorAll("[data-tab]").forEach((button) => {
    const on = button.dataset.tab === id;
    button.classList.toggle("active", on);
    button.setAttribute("aria-selected", on ? "true" : "false");
  });
  const page = data.pages[id];
  const root = document.getElementById("page");
  root.replaceChildren();
  root.append(kpis(page.kpis));
  if (page.filters) root.append(pills(data, id, page));
  const view = currentView(page, id);
  root.append(chartCard(view.hero || page.hero));
  (view.supporting || page.supporting || []).forEach((chart) => root.append(chartCard(chart)));
  const means = view.means || page.means;
  if (means) root.append(meansBox(means));
  if (page.exact) root.append(exactBox(page.exact));
}

function currentView(page, id) {
  if (!page.views) return {};
  const key = pageState[id] || page.default_filter;
  return page.views[key] || {};
}

function kpis(items) {
  const wrap = document.createElement("section");
  wrap.className = "kpis";
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = `kpi ${item.tone}`;
    card.innerHTML = `<div class="value"></div><div class="label"></div><div class="takeaway"></div>`;
    card.querySelector(".value").textContent = item.value;
    card.querySelector(".label").textContent = item.label;
    card.querySelector(".takeaway").textContent = item.takeaway;
    wrap.append(card);
  });
  return wrap;
}

function pills(data, id, page) {
  const wrap = document.createElement("div");
  wrap.className = "pills";
  const active = pageState[id] || page.default_filter;
  page.filters.forEach((filter) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = filter.label;
    button.className = filter.id === active ? "active" : "";
    button.setAttribute("aria-pressed", filter.id === active ? "true" : "false");
    button.addEventListener("click", () => {
      pageState[id] = filter.id;
      show(data, id);
    });
    wrap.append(button);
  });
  return wrap;
}

function chartCard(chart) {
  const card = document.createElement("article");
  card.className = "card";
  const title = document.createElement("h2");
  title.textContent = chart.title;
  const sub = document.createElement("p");
  sub.className = "sub";
  sub.textContent = chart.subtitle || "";
  card.append(title, sub);
  const svg = chart.kind === "bar" ? barChart(chart) : chart.kind === "range" ? rangeChart(chart) : lineChart(chart);
  card.append(svg);
  return card;
}

function meansBox(text) {
  const box = document.createElement("section");
  box.className = "means";
  const title = document.createElement("h2");
  title.textContent = "What this means";
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  box.append(title, paragraph);
  return box;
}

function exactBox(exact) {
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = "Exact values";
  const table = document.createElement("table");
  const head = document.createElement("tr");
  exact.columns.forEach((column) => {
    const cell = document.createElement("th");
    cell.textContent = column;
    head.append(cell);
  });
  table.append(head);
  exact.rows.forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      tr.append(cell);
    });
    table.append(tr);
  });
  details.append(summary, table);
  return details;
}

function sourcesHtml(sources) {
  const items = sources
    .map((source) => `<li><strong>${escapeHtml(source.name)}</strong> — ${escapeHtml(source.publisher)}. ${escapeHtml(source.note)}</li>`)
    .join("");
  return `<h2>Sources</h2><ul>${items}</ul>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char]));
}

function finite(values) {
  return values.filter((value) => value !== null && value !== undefined && Number.isFinite(value));
}

function niceTicks(min, max, count = 4) {
  const span = max - min || 1;
  const step = Math.pow(10, Math.floor(Math.log10(span / count)));
  const error = span / count / step;
  const nice = error >= 7 ? 10 : error >= 3 ? 5 : error >= 1.5 ? 2 : 1;
  const size = nice * step;
  const start = Math.ceil(min / size) * size;
  const ticks = [];
  for (let value = start; value <= max + size * 0.01; value += size) ticks.push(Number(value.toFixed(6)));
  return ticks.length ? ticks : [min, max];
}

function spread(labels, minY, maxY, gap) {
  const items = labels.map((label) => ({ ...label })).sort((a, b) => a.y - b.y);
  for (let i = 1; i < items.length; i += 1) {
    if (items[i].y < items[i - 1].y + gap) items[i].y = items[i - 1].y + gap;
  }
  const overflow = items.length ? items[items.length - 1].y - maxY : 0;
  if (overflow > 0) items.forEach((item) => { item.y -= overflow; });
  const under = items.length ? minY - items[0].y : 0;
  if (under > 0) items.forEach((item) => { item.y += under; });
  return items;
}

function svgEl(name, attrs) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  return node;
}

function lineChart(chart) {
  const width = 860;
  const height = 430;
  const left = 48;
  const right = 168;
  const top = 18;
  const bottom = 36;
  const plotW = width - left - right;
  const plotH = height - top - bottom;
  const values = chart.series.flatMap((series) => finite(series.values));
  let min = Math.min(...values);
  let max = Math.max(...values);
  const pad = Math.max((max - min) * 0.12, chart.unit === "%" ? 0.6 : 2);
  min -= pad;
  max += pad;
  const ticks = niceTicks(min, max);
  const yOf = (value) => top + ((max - value) / (max - min)) * plotH;
  const xOf = (index) => left + (chart.x.length === 1 ? plotW / 2 : (index / (chart.x.length - 1)) * plotW);
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": chart.title });
  ticks.forEach((tick) => {
    const y = yOf(tick);
    svg.append(svgEl("line", { x1: left, x2: left + plotW, y1: y, y2: y, class: "grid" }));
    const label = svgEl("text", { x: left - 8, y: y + 4, "text-anchor": "end", class: "axis" });
    label.textContent = formatTick(tick, chart.unit);
    svg.append(label);
  });
  const step = chart.x.length > 12 ? Math.ceil(chart.x.length / 7) : 1;
  let lastTickX = -999;
  chart.x.forEach((label, index) => {
    const last = index === chart.x.length - 1;
    if (index % step !== 0 && !last) return;
    const x = xOf(index);
    if (last && x - lastTickX < 56) return;
    lastTickX = x;
    const anchor = index === 0 ? "start" : last ? "end" : "middle";
    const text = svgEl("text", { x, y: height - 12, "text-anchor": anchor, class: "axis" });
    text.textContent = label;
    svg.append(text);
  });
  const low = chart.series.find((series) => series.band === "low");
  const high = chart.series.find((series) => series.band === "high");
  if (low && high) {
    const points = [];
    high.values.forEach((value, index) => {
      if (value === null || low.values[index] === null) return;
      points.push(`${xOf(index)},${yOf(value)}`);
    });
    for (let index = low.values.length - 1; index >= 0; index -= 1) {
      if (low.values[index] === null || high.values[index] === null) continue;
      points.push(`${xOf(index)},${yOf(low.values[index])}`);
    }
    svg.append(svgEl("polygon", { points: points.join(" "), fill: "#5C6B82", "fill-opacity": "0.28" }));
  }
  const endLabels = [];
  chart.series.filter((series) => !series.band).forEach((series) => {
    const coords = [];
    series.values.forEach((value, index) => {
      if (value === null) return;
      coords.push([xOf(index), yOf(value)]);
    });
    if (!coords.length) return;
    const path = svgEl("path", {
      d: coords.map((point, index) => `${index ? "L" : "M"}${point[0]},${point[1]}`).join(" "),
      fill: "none",
      stroke: series.color,
      "stroke-width": "2.5",
      "stroke-linejoin": "round",
      "stroke-linecap": "round",
    });
    svg.append(path);
    const last = coords[coords.length - 1];
    svg.append(svgEl("circle", { cx: last[0], cy: last[1], r: 3.5, fill: series.color }));
    const lastValue = [...series.values].reverse().find((value) => value !== null);
    endLabels.push({ y: last[1], text: `${series.name} ${formatTick(lastValue, chart.unit)}`, color: series.color });
  });
  spread(endLabels, top + 8, top + plotH - 4, 16).forEach((label) => {
    const text = svgEl("text", { x: left + plotW + 10, y: label.y + 4, fill: label.color, "font-size": "12" });
    text.textContent = label.text;
    svg.append(text);
  });
  return svg;
}

function barChart(chart) {
  const seriesCount = chart.series.length;
  const rowH = seriesCount > 1 ? 18 * seriesCount + 16 : 32;
  const width = 860;
  const left = 188;
  const right = 64;
  const top = 8;
  const height = top + chart.categories.length * rowH + 28;
  const plotW = width - left - right;
  const values = chart.series.flatMap((series) => finite(series.values));
  let min = Math.min(0, ...values);
  let max = Math.max(0, ...values);
  if (min === max) max = min + 1;
  const span = max - min;
  max += span * 0.08;
  if (min < 0) min -= span * 0.08;
  const xOf = (value) => left + ((value - min) / (max - min)) * plotW;
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": chart.title });
  svg.append(svgEl("line", { x1: xOf(0), x2: xOf(0), y1: top, y2: height - 24, class: "grid" }));
  chart.categories.forEach((category, index) => {
    const y = top + index * rowH;
    const label = svgEl("text", { x: left - 10, y: y + rowH / 2 + 4, "text-anchor": "end", "font-size": "13" });
    label.textContent = category;
    svg.append(label);
    chart.series.forEach((series, seriesIndex) => {
      const value = series.values[index];
      if (value === null) return;
      const barH = seriesCount > 1 ? 14 : 16;
      const barY = y + (rowH - barH * seriesCount) / 2 + seriesIndex * (barH + 2);
      const x = xOf(Math.min(0, value));
      const w = Math.max(1, Math.abs(xOf(value) - xOf(0)));
      const color = (series.colors && series.colors[index]) || series.color;
      svg.append(svgEl("rect", { x, y: barY, width: w, height: barH, rx: 3, fill: color }));
      const outsideRight = value >= 0;
      const labelX = outsideRight ? xOf(value) + 6 : xOf(value) - 6;
      const valueText = svgEl("text", {
        x: labelX,
        y: barY + barH - 2,
        "text-anchor": outsideRight ? "start" : "end",
        "font-size": "12",
        fill: "#f3f6fb",
      });
      valueText.textContent = formatTick(value, chart.unit);
      svg.append(valueText);
    });
  });
  return svg;
}

function rangeChart(chart) {
  const rowH = 42;
  const width = 860;
  const left = 210;
  const right = 72;
  const top = 10;
  const height = top + chart.categories.length * rowH + 16;
  const plotW = width - left - right;
  const values = finite([...chart.low, ...chart.high, ...chart.point]);
  let min = Math.min(...values);
  let max = Math.max(...values);
  const pad = Math.max((max - min) * 0.12, 0.4);
  min -= pad;
  max += pad;
  const xOf = (value) => left + ((value - min) / (max - min)) * plotW;
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": chart.title });
  chart.categories.forEach((category, index) => {
    const y = top + index * rowH + rowH / 2;
    const label = svgEl("text", { x: left - 12, y: y + 4, "text-anchor": "end", "font-size": "13" });
    label.textContent = category;
    svg.append(label);
    svg.append(svgEl("line", {
      x1: xOf(chart.low[index]),
      x2: xOf(chart.high[index]),
      y1: y,
      y2: y,
      stroke: chart.colors[index],
      "stroke-width": "6",
      "stroke-linecap": "round",
      opacity: "0.85",
    }));
    svg.append(svgEl("circle", { cx: xOf(chart.point[index]), cy: y, r: 5.5, fill: "#f3f6fb" }));
    const text = svgEl("text", { x: xOf(chart.high[index]) + 10, y: y + 4, "font-size": "12" });
    text.textContent = formatTick(chart.point[index], chart.unit);
    svg.append(text);
  });
  return svg;
}

function formatTick(value, unit) {
  const cents = Math.round(value * 100) / 100;
  const tenths = Math.round(value * 10) / 10;
  let text;
  if (Math.abs(cents - tenths) >= 0.01) text = cents.toFixed(2);
  else text = tenths.toFixed(1);
  if (!unit) return text;
  if (unit === "pts") return `${text} pts`;
  return `${text}${unit}`;
}

main();
