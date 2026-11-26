# Square in Square：搜索算法演化环境

本分支只保留布局数据、严格几何判别器和最小 LLM 演化环境，不包含旧的遗传退火 baseline。

## 文件

- `record.json`：原始记录，键为 `n`，值为多个候选布局。
- `aim.json`：每个 `n` 取 `s` 最小的一条完整记录；仅供控制器评分，agent 不可读取。
- `puzzles.json`：agent 唯一可读取的公开题目列表，只包含 `n`。
- `weights.json`：146 个子问题的权重，当前全部为 `1.0`。后续可单独提高需要优化的 `n` 的权重。
- `evaluator.py`：布局合法性检查和相对目标的加权评分。
- `run_search.py`：只开放 `search/` 写权限的 Linux sandbox 入口。
- `evolve.py`：调用 DeepSeek、运行候选、评分并保留最优算法的最小演化控制器。
- `search/`：搜索 agent 唯一可修改的目录，接口详见 `search/README.md`。
- `squares_metric/`：复用的十进制解析、高精度重叠判别和包围盒测量。

`record.json` 包含 146 个 `n`（5–2043），所以新接口直接处理 JSON 布局，不受竞赛 CSV 的 `n <= 1000` 限制。原始最佳记录含截断坐标，严格判别器可能发现微小重叠；`aim.json` 是优化目标，不代表其坐标可直接作为合法提交。

## 使用

```bash
uv sync
uv run python run_search.py 10
uv run python evaluator.py --output search/score.json

# 启动最小演化循环（默认 deepseek-flash，支持 DEEPSEEK_BASE_URL 和 DEEPSEEK_MODEL）：
export DEEPSEEK_API_KEY=...
uv run python evolve.py --iterations 10
```

`search/algorithm.py` 是独立的 shrink–shake–relax 基础算法：从普通网格 incumbent 开始，对 `n <= 20` 使用 SciPy L-BFGS-B 松弛边界与 SAT 重叠罚项，不读取任何目标布局。所有候选必须重新通过严格校验，失败或变差时保留 incumbent。`LBFGS_MAX_N`、`ATTEMPTS`、`SHRINK`、`SHAKE` 是可供 LLM 调整的参数。sandbox 会将 `record.json` 和 `aim.json` 屏蔽为空设备。

控制器逐个 n 启动独立 sandbox，每个 n 的 wall-clock 硬预算固定为 10 秒，地址空间默认限制为 2 GiB（`SEARCH_MEMORY_MB` 可调整），并限制 BLAS/OpenMP 为单线程。子进程日志写入临时文件且只读取末尾 2 MB，避免大量输出占用控制器内存。超时终止整个进程组。某个 n 超时后不再执行后续更大的 n；超时及跳过的 n 恢复本轮初始 incumbent，已完成的较小 n 保留，然后正常合并评分，因此部分改进仍可被接受。`--timeout` 仅控制最终评分。不限制源码长度，编译失败会在执行前拒绝。

每轮 LLM 返回完整替换源码；控制器打印 API 状态、源码 diff、编译结果、完整子进程日志、逐 n 分数变化和接受/拒绝原因。算法从自己生成的 `search/incumbents.json` 继续搜索，并按 n 保留严格改进的合法布局。控制器在 `evolution/best_layouts.json` 保存快照；仅在总分严格下降时接受，否则同时恢复 `evolution/best_algorithm.py` 和最佳布局。

每轮搜索后，未产生保留改进的 n 权重乘 `1.01`，有保留改进的 n 重置为 `1.0`；接受判断始终使用更新前权重，更新只影响后续反馈和评分。每 5 轮追加代码审查轮：简化源码必须减少行数、分数不变差且合法题数不下降才接受。审查轮不改变权重。历史写入 `evolution/history.jsonl`，候选保存在 `evolution/candidates/`。

算法输出 `search/result.json`：

```json
{"10": [[x0, y0, angle0], [x1, y1, angle1]]}
```

每个 `n` 必须恰好有 `n` 个三元组，允许缺少某些 `n`，但会按普通网格边长 `ceil(sqrt(n))` 罚分。无效布局也使用网格边长，并保留具体失败原因。

## 评分

对 `aim.json` 中每个 `n`：

```text
gap_n = (algorithm_side_n - aim_side_n) / aim_side_n
total = sum(weight_n * gap_n) / sum(weight_n)
```

总分越低越好；`0` 表示整体达到目标，负值表示超过目标。默认权重归一化后等价于所有 `n` 平权的平均差距。评分输出包含每个 `n` 的合法性、实际边长、目标边长、差距、权重和失败原因。

## 检查

```bash
uv run python -m unittest discover -s tests -v
```
