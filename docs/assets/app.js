const DATA_URL = "data/pokemon.json";
const MAX_BASE_STAT = 255;

const state = {
	all: [],
	filtered: [],
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
};

const padId = (id) => String(id).padStart(3, "0");

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

async function bootstrap() {
	try {
		const response = await fetch(DATA_URL, { cache: "no-store" });
		if (!response.ok) {
			throw new Error(`网络错误：${response.status}`);
		}
		const payload = await response.json();
		state.all = payload.pokemon ?? [];
		state.filtered = state.all;
		updateMeta(payload);
		renderCards(state.filtered);
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
	const term = elements.search.value.trim();
	state.filtered = state.all.filter((pokemon) => matchesTerm(pokemon, term));
	const resultMeta = term
		? `${state.filtered.length} / ${state.all.length} 条匹配`
		: `${state.all.length} 条宝可梦记录`;
	elements.count.textContent = resultMeta;
	renderCards(state.filtered);
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
}

wireEvents();
bootstrap();
