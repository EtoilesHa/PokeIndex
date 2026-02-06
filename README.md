POKEINDEX
=========

借助 `get_poke_index.py` 将 [PokeAPI](https://pokeapi.co/) 上的宝可梦资料同步到本地 SQLite 数据库文件（默认 `pokeindex.db`，位于项目根目录），方便离线查询或做进一步的分析与可视化。

Requirements
------------
- Python 3.10+（已在 Windows 下验证）
- 依赖包：`requests`, `Flask`

```powershell
python -m venv .venv
\.\.venv\Scripts\activate
pip install requests Flask
```

Configuration
-------------
- 默认会在项目根目录生成/更新 `pokeindex.db`。
- 可通过 `--db-path ./data/custom.db` 或 `POKE_DB_PATH` 环境变量自定义数据库位置。

Usage
-----
```powershell
python get_poke_index.py --sleep 0.25 --batch-size 50
```

常用参数：

- `--names pikachu charizard`：只刷新特定宝可梦（可用名称或数字 ID）。
- `--limit 50 --offset 0`：测试时限制抓取数量，避免一次性完整同步。
- `--page-size 150`：调整单次 API 请求的条数（上限 500）。
- `--sleep 0.2`：设置请求之间的延迟，遵守 PokeAPI 的速率限制。
- `--max-retries 5` / `--backoff 0.3`：控制 HTTP 自动重试策略。

Features
--------
- 自动建表：首次运行即会创建 `pokemon` 主表以及能力、属性、招式、持有物等关联表。
- 全量信息：抓取 `/pokemon` 与 `/pokemon-species`，并在主表中保存原始 JSON，以便需要时反序列化更多字段。
- 幂等写入：使用 UPSERT + 逐表重建的方式，重复执行脚本也不会产生重复数据。
- 容错：请求失败会自动重试，某一只宝可梦写入失败会记录日志并继续处理后续条目。

Tips
----
- 首次完整同步数据量较大，建议把 `--sleep` 设置在 0.2~0.3 秒之间，避免触发 PokeAPI 限流。
- 如果想把数据放到别的目录，记得用 `--db-path` 指向目标位置（需要可写权限）。

Web UI
------
同步完 `pokeindex.db` 之后，可通过内置 Flask 应用浏览图鉴：

```powershell
set FLASK_APP=app.py
flask run --reload
```

或直接运行 `python app.py`（开发模式）。页面提供搜索、卡片列表以及单体宝可梦详情，并从同一个 SQLite 数据库读取中文/日文/英文名称、属性、特性、蛋组、种族值与进化链信息。