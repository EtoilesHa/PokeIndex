POKEINDEX
=========
【python -m http.server --directory docs 8080】

离线同步 [PokeAPI](https://pokeapi.co/) 数据到 `pokeindex.db`，再把内容导出为静态 JSON，最终由 GitHub Pages 托管的前端通过 JavaScript 读取完成搜索与详情展示。整个部署无需服务器或 Flask 进程。

Workflow
--------
1. **同步数据库**：
	```powershell
	python get_poke_index.py --sleep 0.25 --batch-size 50
	```
	常用参数（`--names`, `--limit`, `--page-size`, `--sleep`, `--max-retries` 等）与之前保持一致，依旧写入项目根目录的 `pokeindex.db`。可用 `--db-path` 或 `POKE_DB_PATH` 指向其他位置。

2. **导出静态数据**：
	```powershell
	python export_static_data.py --db-path pokeindex.db --output docs/data/pokemon.json
	```
	该脚本会把所有宝可梦的基本信息、属性、特性、种族值与进化链全面压平到一个 JSON 文件中（UTF-8、保留多语言字符），供前端直接 `fetch` 使用。

3. **本地预览静态站点**：
	```powershell
	python -m http.server --directory docs 8080
	```
	然后打开 <http://localhost:8080/>。前端位于 `docs/`，包含 `index.html`、`assets/styles.css` 和 `assets/app.js`，默认会读取 `docs/data/pokemon.json`。

4. **部署到 GitHub Pages**：
	- 在仓库设置中将 Pages Source 设为 `Deploy from a branch` + `main` 分支的 `/docs` 目录。
	- 每次重新同步数据库后运行导出脚本即可更新静态 JSON，推送变更后 Pages 会自动刷新。

Project Layout
--------------
- `get_poke_index.py`：抓取 PokeAPI 并写入 SQLite。
- `export_static_data.py`：把数据库拍平为静态 JSON，含所有渲染所需字段。
- `docs/`：纯前端静态站点，可直接由 GitHub Pages 或任何静态服务器托管。
- `pokeindex.db`：本地缓存的完整宝可梦数据源，不需要随仓库发布。

Notes
-----
- 静态 JSON 中含多种语言字符串与进化链拓扑，页面加载一次即可完成所有查询，搜索逻辑完全在浏览器端执行。
- 如果 JSON 体积较大，可考虑在 `export_static_data.py` 内增加按代分片或精简字段的逻辑，再对应修改前端读取策略。
- 由于现在是完全静态方案，`.gitignore` 里已经忽略数据库文件；发布时只需关注 `docs/` 及脚本源码。