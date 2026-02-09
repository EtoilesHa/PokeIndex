const DATA_URL = "data/pokemon.json";
const MAX_BASE_STAT = 255;

const GENERATION_FILTERS = [
	{ id: "all", label: "全部世代" },
	{ id: "generation-i", label: "第一世代" },
	{ id: "generation-ii", label: "第二世代" },
	{ id: "generation-iii", label: "第三世代" },
	{ id: "generation-iv", label: "第四世代" },
	{ id: "generation-v", label: "第五世代" },
	{ id: "generation-vi", label: "第六世代" },
	{ id: "generation-vii", label: "第七世代" },
	{ id: "generation-viii", label: "第八世代" },
	{ id: "generation-ix", label: "第九世代" },
];

const TYPE_FILTERS = [
	{ id: "normal", label: "一般" },
	{ id: "fire", label: "火" },
	{ id: "water", label: "水" },
	{ id: "electric", label: "电" },
	{ id: "grass", label: "草" },
	{ id: "ice", label: "冰" },
	{ id: "fighting", label: "格斗" },
	{ id: "poison", label: "毒" },
	{ id: "ground", label: "地面" },
	{ id: "flying", label: "飞行" },
	{ id: "psychic", label: "超能" },
	{ id: "bug", label: "虫" },
	{ id: "rock", label: "岩石" },
	{ id: "ghost", label: "幽灵" },
	{ id: "dragon", label: "龙" },
	{ id: "dark", label: "恶" },
	{ id: "steel", label: "钢" },
	{ id: "fairy", label: "妖精" },
];

const state = {
	all: [],
	filtered: [],
	searchTerm: "",
	activeGenerations: [],
	activeTypes: [],
	rangeStart: null,
	rangeEnd: null,
	idBounds: { min: 1, max: 9999 },
};

const elements = {
	grid: document.querySelector("#card-grid"),
	search: document.querySelector("#search-input"),
	reset: document.querySelector("#reset-search"),
	count: document.querySelector("#data-count"),
	updated: document.querySelector("#data-updated"),
	overlay: document.querySelector("#detail-overlay"),
	detailContent: document.querySelector("#detail-content"),
	closeButton: document.querySelector('[data-close]'),
	generationFilter: document.querySelector("#generation-filter"),
	typeFilter: document.querySelector("#type-filter"),
	randomSelect: document.querySelector("#random-generation-select"),
	randomButton: document.querySelector("#random-pokemon-button"),
	randomResult: document.querySelector("#random-result"),
	rangeStartInput: document.querySelector("#range-start"),
	rangeEndInput: document.querySelector("#range-end"),
};

const padId = (id) => String(id).padStart(3, "0");
const clampNumber = (value, min, max) => Math.min(Math.max(value, min), max);

const formatDate = (value) => {
	if (!value) return "";
	const parsed = new Date(value);
	if (Number.isNaN(parsed.getTime())) {
		return value;
	}
	return parsed.toLocaleString("zh-CN", {
		year: "numeric",
		month: "2-digit",
		day: "2-digit",
		hour: "2-digit",
		minute: "2-digit",
	});
};

function renderGenerationFilter() {
	if (!elements.generationFilter) return;
	const fragment = document.createDocumentFragment();
	GENERATION_FILTERS.forEach((filter) => {
		const button = document.createElement("button");
		button.type = "button";
		button.className = "gen-chip";
		button.dataset.gen = filter.id;
		button.textContent = filter.label;
		const isAll = filter.id === "all";
		const isActive = isAll
			? state.activeGenerations.length === 0
			: state.activeGenerations.includes(filter.id);
		button.setAttribute("aria-pressed", isActive ? "true" : "false");
		if (isActive) {
			button.classList.add("is-active");
		}
		fragment.appendChild(button);
	});
	elements.generationFilter.replaceChildren(fragment);
}

function renderTypeFilter() {
	if (!elements.typeFilter) return;
	const fragment = document.createDocumentFragment();
	TYPE_FILTERS.forEach((filter) => {
		const button = document.createElement("button");
		button.type = "button";
		button.className = "gen-chip";
		button.dataset.type = filter.id;
		button.textContent = filter.label;
		const isActive = state.activeTypes.includes(filter.id);
		button.setAttribute("aria-pressed", isActive ? "true" : "false");
		if (isActive) {
			button.classList.add("is-active");
		}
		fragment.appendChild(button);
	});
	elements.typeFilter.replaceChildren(fragment);
}

function renderRandomGenerationSelect() {
	if (!elements.randomSelect) return;
	const fragment = document.createDocumentFragment();
	GENERATION_FILTERS.filter((filter) => filter.id !== "all").forEach((filter) => {
		const option = document.createElement("option");
		option.value = filter.id;
		option.textContent = filter.label;
		fragment.appendChild(option);
	});
	elements.randomSelect.replaceChildren(fragment);
	Array.from(elements.randomSelect.options).forEach((option) => {
		option.selected = true;
	});
}

function updateIdBounds() {
	if (!state.all.length) return;
	const ids = state.all
		.map((entry) => Number(entry.id))
		.filter((value) => Number.isFinite(value));
	if (!ids.length) return;
	state.idBounds.min = Math.min(...ids);
	state.idBounds.max = Math.max(...ids);
	if (elements.rangeStartInput) {
		elements.rangeStartInput.min = state.idBounds.min;
		elements.rangeStartInput.max = state.idBounds.max;
		elements.rangeStartInput.placeholder = `#${padId(state.idBounds.min)}`;
	}
	if (elements.rangeEndInput) {
		elements.rangeEndInput.min = state.idBounds.min;
		elements.rangeEndInput.max = state.idBounds.max;
		elements.rangeEndInput.placeholder = `#${padId(state.idBounds.max)}`;
	}
	syncRangeStateFromInputs();
}

function handleGenerationFilterClick(event) {
	const target = event.target.closest("[data-gen]");
	if (!target) return;
	const gen = target.dataset.gen;
	if (!gen) return;
	if (gen === "all") {
		state.activeGenerations = [];
	} else {
		const exists = state.activeGenerations.includes(gen);
		state.activeGenerations = exists
			? state.activeGenerations.filter((entry) => entry !== gen)
			: [...state.activeGenerations, gen];
	}
	renderGenerationFilter();
	applyFilters();
}

function handleTypeFilterClick(event) {
	const target = event.target.closest("[data-type]");
	if (!target) return;
	const typeId = target.dataset.type;
	if (!typeId) return;
	const exists = state.activeTypes.includes(typeId);
	if (exists) {
		state.activeTypes = state.activeTypes.filter((entry) => entry !== typeId);
	} else {
		state.activeTypes = [...state.activeTypes, typeId];
	}
	renderTypeFilter();
	applyFilters();
}

function getGenerationLabel(id) {
	const match = GENERATION_FILTERS.find((item) => item.id === id);
	return match ? match.label : "";
}

function getTypeLabel(id) {
	const match = TYPE_FILTERS.find((item) => item.id === id);
	return match ? match.label : id;
}

function sanitizeRangeValue(value) {
	if (value === undefined || value === null) {
		return null;
	}
	const trimmed = String(value).trim();
	if (!trimmed) {
		return null;
	}
	const parsed = Number(trimmed);
	if (!Number.isFinite(parsed)) {
		return null;
	}
	const rounded = Math.round(parsed);
	return clampNumber(rounded, state.idBounds.min, state.idBounds.max);
}

function handleRangeInput(event) {
	const target = event.target;
	if (!target) return;
	const sanitized = sanitizeRangeValue(target.value);
	if (target === elements.rangeStartInput) {
		state.rangeStart = sanitized;
	} else if (target === elements.rangeEndInput) {
		state.rangeEnd = sanitized;
	}
	if (sanitized === null && target.value !== "") {
		target.value = "";
	} else if (sanitized !== null) {
		target.value = sanitized;
	}
}

function syncRangeStateFromInputs() {
	if (elements.rangeStartInput) {
		const sanitized = sanitizeRangeValue(elements.rangeStartInput.value);
		state.rangeStart = sanitized;
		if (sanitized === null && elements.rangeStartInput.value !== "") {
			elements.rangeStartInput.value = "";
		} else if (sanitized !== null) {
			elements.rangeStartInput.value = sanitized;
		}
	}
	if (elements.rangeEndInput) {
		const sanitized = sanitizeRangeValue(elements.rangeEndInput.value);
		state.rangeEnd = sanitized;
		if (sanitized === null && elements.rangeEndInput.value !== "") {
			elements.rangeEndInput.value = "";
		} else if (sanitized !== null) {
			elements.rangeEndInput.value = sanitized;
		}
	}
}

function validateRange() {
	const { rangeStart, rangeEnd } = state;
	if (rangeStart !== null && rangeEnd !== null && rangeStart > rangeEnd) {
		return { valid: false, message: "编号范围无效：起始需小于或等于结束编号。" };
	}
	return { valid: true };
}


function matchesGeneration(pokemon, activeGenerations) {
	if (!activeGenerations.length) {
		return true;
	}
	const slug = pokemon.generation?.slug ?? "unknown";
	return activeGenerations.includes(slug);
}

function matchesTypes(pokemon, typesFilter) {
	if (!typesFilter.length) {
		return true;
	}
	const source = pokemon.types ?? [];
	return typesFilter.every((type) => source.includes(type));
}

function matchesRange(pokemon) {
	const id = Number(pokemon.id);
	if (!Number.isFinite(id)) {
		return false;
	}
	if (state.rangeStart !== null && id < state.rangeStart) {
		return false;
	}
	if (state.rangeEnd !== null && id > state.rangeEnd) {
		return false;
	}
	return true;
}

function applyFilters() {
	const term = state.searchTerm;
	const typeFilters = state.activeTypes;
	state.filtered = state.all.filter(
		(pokemon) =>
			matchesTerm(pokemon, term) &&
			matchesGeneration(pokemon, state.activeGenerations) &&
			matchesTypes(pokemon, typeFilters)
	);
	renderCards(state.filtered);
	updateCountDisplay();
}

function updateCountDisplay() {
	if (!elements.count) return;
	const total = state.all.length;
	const filtered = state.filtered.length;
	const hasSearch = Boolean(state.searchTerm);
	const generationActive = state.activeGenerations.length > 0;
	const typeActive = state.activeTypes.length > 0;
	if (!hasSearch && !generationActive && !typeActive) {
		elements.count.textContent = `${total} 条宝可梦记录`;
		return;
	}
	const parts = [];
	if (generationActive) {
		const labels = state.activeGenerations
			.map((slug) => getGenerationLabel(slug) || slug)
			.filter(Boolean);
		if (labels.length) {
			parts.push(labels.join("、"));
		}
	}
	if (typeActive) {
		const labels = state.activeTypes.map(getTypeLabel).join("、");
		parts.push(`属性：${labels}`);
	}
	if (hasSearch) {
		parts.push(`搜索“${state.searchTerm}”`);
	}
	const context = parts.length ? `（${parts.join(" · ")}）` : "";
	elements.count.textContent = `${filtered} / ${total} 条 ${context}`.trim();
}

function getSelectedRandomGenerations() {
	if (!elements.randomSelect) return [];
	return Array.from(elements.randomSelect.selectedOptions).map((option) => option.value);
}

function getRandomPool(selection) {
	const basePool = state.filtered.filter((pokemon) => matchesRange(pokemon));
	if (!selection.length) {
		return basePool;
	}
	return basePool.filter((pokemon) => selection.includes(pokemon.generation?.slug ?? ""));
}

function updateRandomResult(payload) {
	if (!elements.randomResult) return;
	if (typeof payload === "string") {
		elements.randomResult.textContent = payload;
		return;
	}
	const { pokemon } = payload;
	const displayName = pokemon.names?.zh ?? pokemon.names?.en ?? `#${padId(pokemon.id)}`;
	elements.randomResult.innerHTML = `
		<div class="random-result-line">
			<button type="button" class="random-result-link" data-random-id="${pokemon.id}">
				${displayName} · #${padId(pokemon.id)}
			</button>
		</div>
	`;
}

function handleRandomButtonClick() {
	if (!state.all.length) {
		updateRandomResult("图鉴尚未加载，稍后再试。");
		return;
	}
	syncRangeStateFromInputs();
	const rangeValidation = validateRange();
	if (!rangeValidation.valid) {
		updateRandomResult(rangeValidation.message);
		return;
	}
	resetFiltersToDefault({ silent: true, skipScroll: true, keepOverlay: true });
	const selection = getSelectedRandomGenerations();
	if (!state.filtered.length) {
		updateRandomResult("当前筛选没有可供随机的宝可梦。");
		return;
	}
	const pool = getRandomPool(selection);
	if (!pool.length) {
		const message = selection.length ? "所选世代在当前结果中暂无宝可梦。" : "当前没有可供随机的宝可梦。";
		updateRandomResult(message);
		return;
	}
	const choice = pool[Math.floor(Math.random() * pool.length)];
	updateRandomResult({ pokemon: choice, selection });
	if (elements.search) {
		elements.search.value = padId(choice.id);
	}
	handleSearch();
	showDetailById(choice.id);
	scrollCardIntoView(choice.id);
}

function scrollCardIntoView(id) {
	const card = elements.grid.querySelector(`[data-id="${id}"]`);
	if (!card) {
		return;
	}
	card.classList.add("is-highlighted");
	card.scrollIntoView({ behavior: "smooth", block: "center" });
	setTimeout(() => {
		card.classList.remove("is-highlighted");
	}, 1400);
}

function resetFiltersToDefault(options = {}) {
	const { silent = false, skipScroll = false, keepOverlay = false } = options;
	if (!state.all.length) {
		return;
	}
	state.searchTerm = "";
	state.activeGenerations = [];
	state.activeTypes = [];
	if (elements.search) {
		elements.search.value = "";
	}
	renderGenerationFilter();
	renderTypeFilter();
	applyFilters();
	if (!keepOverlay) {
		closeDetailOverlay();
	}
	if (!skipScroll) {
		window.scrollTo({ top: 0, behavior: "smooth" });
	}
	if (!silent) {
		updateRandomResult("筛选已重置，已回到首页。");
	}
}

async function bootstrap() {
	try {
		const response = await fetch(DATA_URL, { cache: "no-store" });
		if (!response.ok) {
			throw new Error(`网络错误：${response.status}`);
		}
		const payload = await response.json();
		state.all = payload.pokemon ?? [];
		state.filtered = state.all;
		updateIdBounds();
		updateMeta(payload);
		renderGenerationFilter();
		renderTypeFilter();
		applyFilters();
	} catch (error) {
		console.error(error);
		elements.grid.innerHTML = `<div class="empty-state">无法加载图鉴：${error.message}</div>`;
	}
}

function updateMeta(payload) {
	const total = payload?.total ?? state.all.length;
	elements.count.textContent = `${total} 条宝可梦记录`;
	const updatedText = formatDate(payload?.generated_at);
	elements.updated.textContent = updatedText ? `导出时间：${updatedText}` : "";
}

function matchesTerm(pokemon, term) {
	if (!term) return true;
	const normalized = term.toLowerCase();
	const names = pokemon.names ?? {};
	return (
		padId(pokemon.id).includes(normalized) ||
		(pokemon.slug ?? "").toLowerCase().includes(normalized) ||
		(names.en ?? "").toLowerCase().includes(normalized) ||
		(names.zh ?? "").toLowerCase().includes(normalized) ||
		(names.ja ?? "").toLowerCase().includes(normalized)
	);
}

function handleSearch() {
	state.searchTerm = elements.search.value.trim();
	applyFilters();
}

function renderCards(list) {
	if (!list.length) {
		elements.grid.innerHTML = `<div class="empty-state">没有找到匹配的宝可梦，换个关键字试试吧。</div>`;
		return;
	}
	const fragment = document.createDocumentFragment();
	list.forEach((pokemon) => {
		const card = document.createElement("button");
		card.type = "button";
		card.className = "pokemon-card";
		card.dataset.id = String(pokemon.id);
		card.innerHTML = `
			<div class="card-main">
				<div class="card-image">
					<img src="${pokemon.sprite}" alt="${pokemon.names?.zh ?? pokemon.names?.en ?? ""}">
				</div>
				<div class="card-body">
					<h3>${pokemon.names?.zh ?? pokemon.names?.en ?? `宝可梦 #${padId(pokemon.id)}`}</h3>
					<p class="subname">${pokemon.names?.ja ?? pokemon.names?.en ?? ""} · ${pokemon.names?.en ?? ""}</p>
					<div class="type-row">
						${renderTypes(pokemon.types)}
					</div>
				</div>
				<div class="card-meta">
					<span class="poke-id">#${padId(pokemon.id)}</span>
				</div>
			</div>
		`;
		fragment.appendChild(card);
	});
	elements.grid.replaceChildren(fragment);
}

function renderTypes(types = []) {
	return types
		.map((type) => `<span class="type-pill type-${type}">${type}</span>`)
		.join("");
}

function showDetailById(id) {
	const pokemon = state.all.find((entry) => entry.id === Number(id));
	if (!pokemon) {
		return;
	}
	const html = `
		<section class="detail-hero">
			<div class="detail-image">
				<img src="${pokemon.sprite}" alt="${pokemon.names?.zh ?? pokemon.names?.en ?? ""}">
			</div>
			<div class="detail-meta">
				<p class="eyebrow">#${padId(pokemon.id)}</p>
				<h1 id="detail-title">${pokemon.names?.zh ?? pokemon.names?.en ?? `宝可梦 #${padId(pokemon.id)}`}</h1>
				<p class="names-line">${pokemon.names?.ja ?? pokemon.names?.en ?? ""} · ${pokemon.names?.en ?? ""}</p>
				<p class="description">${pokemon.description || "暂无图鉴描述。"}</p>
				<div class="meta-grid">
					<div>
						<h4>属性</h4>
						<div class="type-row">${renderTypes(pokemon.types)}</div>
					</div>
					<div>
						<h4>特性</h4>
						<ul>
							${renderAbilities(pokemon.abilities)}
						</ul>
					</div>
					<div>
						<h4>蛋组</h4>
						<p>${(pokemon.egg_groups ?? []).join(' · ') || '—'}</p>
					</div>
					<div>
						<h4>基础数据</h4>
						<p>身高 ${pokemon.height ?? '—'} · 体重 ${pokemon.weight ?? '—'} · 基础经验 ${pokemon.base_experience ?? '—'}</p>
					</div>
				</div>
			</div>
		</section>
		<section class="stats-panel">
			<h2>种族值</h2>
			<ul class="stat-list">${renderStats(pokemon.stats)}</ul>
		</section>
		<section class="evolution-panel">
			<h2>进化链</h2>
			${renderEvolution(pokemon.evolution_chain)}
		</section>
	`;
	elements.detailContent.innerHTML = html;
	openDetailOverlay();
}

function renderAbilities(abilities = []) {
	if (!abilities.length) {
		return "<li>暂无数据</li>";
	}
	return abilities
		.map((ability) => {
			const badge = ability.is_hidden ? '<span class="badge">隐藏</span>' : '';
			return `<li>${ability.name}${badge ? ` ${badge}` : ''}</li>`;
		})
		.join("");
}

function renderStats(stats = []) {
	if (!stats.length) {
		stats = [
			{ label: "HP", base: 0 },
			{ label: "ATTACK", base: 0 },
			{ label: "DEFENSE", base: 0 },
			{ label: "SP ATK", base: 0 },
			{ label: "SP DEF", base: 0 },
			{ label: "SPEED", base: 0 },
		];
	}
	return stats
		.map((stat) => {
			const safeLabel = stat.label ?? "STAT";
			const value = Number(stat.base) || 0;
			const width = Math.min(100, Math.max(0, Math.round((value / MAX_BASE_STAT) * 100)));
			return `
				<li>
					<span>${safeLabel}</span>
					<div class="stat-bar" data-value="${value}">
						<div style="width: ${width}%"></div>
					</div>
					<span class="stat-value">${value}</span>
				</li>
			`;
		})
		.join("");
}

function renderEvolution(chain = []) {
	if (!chain.length) {
		return '<p>暂无进化链数据。</p>';
	}
	const segments = [];
	chain.forEach((stage, index) => {
		segments.push(`
			<div class="evo-stage">
				${stage
					.map(
						(member) => `
							<button type="button" class="evo-card" data-evo-id="${member.id}">
								<p class="eyebrow">阶段 ${index + 1}</p>
								<h3>${member.display_name ?? member.names?.en ?? `#${padId(member.id)}`}</h3>
								<p>${member.names?.ja ?? member.names?.en ?? ''} · ${member.names?.en ?? ''}</p>
							</button>
						`
					)
					.join("")}
			</div>
		`);
		if (index < chain.length - 1) {
			segments.push('<div class="evo-arrow" aria-hidden="true">→</div>');
		}
	});
	return `<div class="evolution-grid">${segments.join("")}</div>`;
}

function openDetailOverlay() {
	elements.overlay.hidden = false;
	document.body.style.overflow = "hidden";
}

function closeDetailOverlay() {
	if (elements.overlay.hidden) return;
	elements.overlay.hidden = true;
	document.body.style.overflow = "";
}

function wireEvents() {
	elements.search.addEventListener("input", handleSearch);
	elements.reset.addEventListener("click", () => {
		elements.search.value = "";
		handleSearch();
		elements.search.focus();
	});
	if (elements.generationFilter) {
		elements.generationFilter.addEventListener("click", handleGenerationFilterClick);
	}
	if (elements.typeFilter) {
		elements.typeFilter.addEventListener("click", handleTypeFilterClick);
	}
	elements.grid.addEventListener("click", (event) => {
		const card = event.target.closest(".pokemon-card");
		if (!card) return;
		showDetailById(card.dataset.id);
	});
	elements.detailContent.addEventListener("click", (event) => {
		const evo = event.target.closest("[data-evo-id]");
		if (evo) {
			showDetailById(evo.dataset.evoId);
		}
	});
	elements.overlay.addEventListener("click", (event) => {
		if (event.target === elements.overlay) {
			closeDetailOverlay();
		}
	});
	elements.closeButton.addEventListener("click", closeDetailOverlay);
	document.addEventListener("keydown", (event) => {
		if (event.key === "Escape") {
			closeDetailOverlay();
		}
	});
	if (elements.randomButton) {
		elements.randomButton.addEventListener("click", handleRandomButtonClick);
	}
	if (elements.randomResult) {
		elements.randomResult.addEventListener("click", (event) => {
			const target = event.target.closest("[data-random-id]");
			if (!target) return;
			showDetailById(target.dataset.randomId);
			scrollCardIntoView(target.dataset.randomId);
		});
	}
	if (elements.rangeStartInput) {
		elements.rangeStartInput.addEventListener("change", handleRangeInput);
	}
	if (elements.rangeEndInput) {
		elements.rangeEndInput.addEventListener("change", handleRangeInput);
	}
}

renderRandomGenerationSelect();
wireEvents();
bootstrap();
